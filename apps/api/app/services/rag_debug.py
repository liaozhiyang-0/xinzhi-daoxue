from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import UTC, datetime
from time import monotonic, perf_counter
from typing import Any
from uuid import uuid4

from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, AgentResult, Intent, RetrievalResult, Scene
from app.core.config import Settings
from app.core.errors import AppError
from app.providers.base import AgentProvider
from app.providers.xingchen import build_workflow_payload
from app.services.citation_validator import CitationValidator
from app.services.knowledge_qa_service import KnowledgeQAService
from app.services.rag_retrieval import RAGRetrievalService
from app.services.retrieval_context import RetrievalContextService
from app.services.task_runner import TaskRunner


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


class DebugTraceStore:
    def __init__(self, max_records: int, ttl_seconds: float) -> None:
        self.max_records = max_records
        self.ttl_seconds = ttl_seconds
        self._records: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()

    def put(self, trace: dict[str, Any]) -> None:
        self._prune()
        trace_id = str(trace["trace_id"])
        self._records[trace_id] = (monotonic(), trace)
        self._records.move_to_end(trace_id)
        while len(self._records) > self.max_records:
            self._records.popitem(last=False)

    def get(self, trace_id: str) -> dict[str, Any] | None:
        self._prune()
        item = self._records.get(trace_id)
        if item is None:
            return None
        self._records.move_to_end(trace_id)
        return item[1]

    def _prune(self) -> None:
        now = monotonic()
        expired = [
            key
            for key, (created, _trace) in self._records.items()
            if now - created > self.ttl_seconds
        ]
        for key in expired:
            self._records.pop(key, None)


class RAGDebugService:
    def __init__(
        self,
        settings: Settings,
        router: TaskRouter,
        registry: AgentRegistry,
        provider: AgentProvider,
        rag: RAGRetrievalService,
        context_service: RetrievalContextService,
        knowledge_qa: KnowledgeQAService,
    ) -> None:
        self.settings = settings
        self.router = router
        self.registry = registry
        self.provider = provider
        self.rag = rag
        self.context_service = context_service
        self.knowledge_qa = knowledge_qa
        self.citations = CitationValidator()
        self.store = DebugTraceStore(
            settings.rag_debug_trace_max_records,
            settings.rag_debug_trace_ttl_seconds,
        )

    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        request_id = str(payload.get("request_id") or f"debug_{uuid4().hex}")
        trace_id = f"debug_rag_{uuid4().hex}"
        stages: list[dict[str, Any]] = []

        def stage(
            name: str,
            status: str,
            stage_started: float,
            *,
            input_count: int = 0,
            output_count: int = 0,
            summary: str = "",
            warnings: list[str] | None = None,
        ) -> None:
            stages.append(
                {
                    "name": name,
                    "status": status,
                    "latency_ms": int((perf_counter() - stage_started) * 1000),
                    "input_count": input_count,
                    "output_count": output_count,
                    "summary": summary,
                    "warnings": warnings or [],
                }
            )

        accepted = perf_counter()
        question = str(payload.get("question", "")).strip()
        course_id = str(payload.get("course_id", "CT")).upper()
        intent = Intent(str(payload.get("intent", "explain_concept")))
        request = AgentRequest(
            task_id=request_id,
            session_id="debug-session",
            user_id="debug-user",
            scene=Scene.LEARNING,
            course_id=course_id,
            intent=intent,
            canonical_input={"question": question},
            options={
                "request_id": request_id,
                "response_depth": str(payload.get("response_depth", "standard")),
                "conversation_summary": str(payload.get("conversation_summary", "")),
                "previous_answer_summary": str(
                    payload.get("previous_answer_summary", "")
                ),
                "include_images": bool(payload.get("include_images", False)),
                "use_reranker": bool(payload.get("use_reranker", False)),
                "allow_cloud": bool(payload.get("allow_cloud", False)),
            },
        )
        stage("request_received", "success", accepted, input_count=1)

        route_started = perf_counter()
        decision = self.router.route(request)
        stage(
            "route",
            "success" if decision.route_status == "selected" else "failed",
            route_started,
            input_count=1,
            output_count=1,
            summary=f"{decision.agent_id} via {decision.route_source}",
        )

        retrieval: RetrievalResult | None = None
        packet = None
        if bool(payload.get("use_rag", True)):
            retrieval_started = perf_counter()
            target_agent = decision.original_agent_id or decision.agent_id
            retrieval = await asyncio.to_thread(
                self.rag.search,
                query_text=question,
                course_id=course_id,
                intent=intent.value,
                target_agent_id=target_agent,
                top_k=self.settings.knowledge_default_top_k,
                include_images=bool(payload.get("include_images", False)),
                session_context=str(payload.get("conversation_summary", "")),
                use_reranker=bool(payload.get("use_reranker", False)),
            )
            stage(
                "retrieval",
                retrieval.rag_status,
                retrieval_started,
                input_count=1,
                output_count=len(retrieval.hits) + len(retrieval.image_hits),
                summary=(
                    f"BM25={retrieval.trace.get('sparse_candidates', 0)}, "
                    f"Dense={retrieval.trace.get('dense_candidates', 0)}, "
                    f"Final={len(retrieval.hits)}"
                ),
                warnings=retrieval.warnings,
            )
            # Keep the end-to-end retrieval latency above while exposing the
            # individual production retrieval phases as first-class timeline
            # entries. Their detailed scores remain in ``retrieval.trace``.
            trace = retrieval.trace
            rewrite_rules = trace.get("query_rewrite_rules")
            rewrite_summary = (
                ", ".join(str(item) for item in rewrite_rules)
                if isinstance(rewrite_rules, list)
                else ""
            )

            def trace_count(name: str) -> int:
                value = trace.get(name, 0)
                return int(value) if isinstance(value, (int, float)) else 0

            for name, input_count, output_count, summary in (
                (
                    "query_normalization",
                    1,
                    1,
                    rewrite_summary or "unchanged",
                ),
                (
                    "bm25_retrieval",
                    1,
                    trace_count("sparse_candidates"),
                    "sparse lexical candidates",
                ),
                (
                    "dense_retrieval",
                    1,
                    trace_count("dense_candidates"),
                    "BGE dense candidates",
                ),
                (
                    "image_retrieval",
                    1 if payload.get("include_images", False) else 0,
                    trace_count("image_candidates"),
                    "enabled"
                    if payload.get("include_images", False)
                    else "skipped by policy",
                ),
                (
                    "rrf_fusion",
                    trace_count("sparse_candidates")
                    + trace_count("dense_candidates")
                    + trace_count("image_candidates"),
                    trace_count("fusion_candidates"),
                    str(trace.get("policy_name", "default")),
                ),
                (
                    "rerank",
                    trace_count("fusion_candidates"),
                    trace_count("reranked_candidates"),
                    "enabled"
                    if payload.get("use_reranker", False)
                    else "skipped by policy",
                ),
            ):
                phase_started = perf_counter()
                stage(
                    name,
                    "success",
                    phase_started,
                    input_count=input_count,
                    output_count=output_count,
                    summary=summary,
                )
            context_started = perf_counter()
            packet = self.context_service.build(
                retrieval, course_id=course_id, intent=intent.value
            )
            stage(
                "context",
                packet.evidence_status,
                context_started,
                input_count=len(retrieval.hits),
                output_count=len(packet.evidence),
                summary=f"retrieved_context={len(packet.to_retrieved_context())} chars",
                warnings=packet.warnings,
            )

        cloud: dict[str, Any] = {"status": "not_run"}
        citation: dict[str, Any] = {"status": "not_run"}
        fallback_used = decision.fallback_used
        fallback_reason = "route_cloud_unavailable" if decision.fallback_used else ""
        result = None
        selected_definition = self.registry.get(decision.agent_id)
        allow_cloud = bool(payload.get("allow_cloud", False))
        if (
            allow_cloud
            and selected_definition.provider == "xingchen"
            and self.registry.is_runtime_available(decision.agent_id, self.settings)
        ):
            provider_request = (
                TaskRunner._with_learning_context(request, packet)
                if packet is not None
                else request
            )
            cloud_started = perf_counter()
            definition = self.registry.get(decision.agent_id)
            redacted_payload = build_workflow_payload(
                self.settings,
                provider_request,
                definition=definition,
                flow_id="[configured]",
            )
            redacted_payload["uid"] = "[redacted]"
            try:
                result = await self.provider.run(
                    decision.agent_id, provider_request, stream=False
                )
                cloud_latency = int((perf_counter() - cloud_started) * 1000)
                cloud = {
                    "status": str(result.structured_result.get("status", "completed")),
                    "request": redacted_payload,
                    "response": result.structured_result,
                    "source_references": result.structured_result.get(
                        "source_references", []
                    ),
                    "latency_ms": cloud_latency,
                }
                stage("cloud", "success", cloud_started, input_count=1, output_count=1)
                if (
                    str(result.structured_result.get("status", "")).casefold()
                    == "failed"
                ):
                    result = None
                    fallback_used = True
                    fallback_reason = "cloud_failed_status"
            except AppError as exc:
                fallback_used = True
                fallback_reason = exc.code
                cloud = {
                    "status": "cloud_failed",
                    "request": redacted_payload,
                    "error_code": exc.code,
                    "latency_ms": int((perf_counter() - cloud_started) * 1000),
                }
                stage("cloud", "failed", cloud_started, warnings=[exc.code])

        if (
            result is not None
            and packet is not None
            and str(result.structured_result.get("status", "")).casefold()
            != "misrouted"
        ):
            citation_started = perf_counter()
            declared = result.structured_result.get("source_references", [])
            validation = self.citations.validate(
                result.answer,
                packet,
                declared_references=declared if isinstance(declared, list) else [],
            )
            source_by_id = {
                evidence.evidence_id: evidence.source_ref
                for evidence in packet.evidence
            }
            result.citations = [
                source_by_id[item]
                for item in validation.valid_ids
                if item in source_by_id
            ]
            citation = {
                "status": "passed" if validation.valid else "failed",
                "cloud_references": list(validation.referenced_ids),
                "valid_references": list(validation.valid_ids),
                "invalid_references": list(validation.invalid_ids),
                "removed_references": list(validation.invalid_ids),
                "final_citations": result.citations,
                "warnings": list(validation.warnings),
            }
            stage(
                "citation_validation",
                citation["status"],
                citation_started,
                input_count=len(validation.referenced_ids),
                output_count=len(validation.valid_ids),
                warnings=list(validation.warnings),
            )

        if result is None:
            fallback_started = perf_counter()
            use_rag = bool(payload.get("use_rag", True))
            if retrieval is None and not use_rag:
                result = AgentResult(
                    agent_id=decision.agent_id,
                    provider="not_run",
                    answer=(
                        "本次对比已关闭 RAG，且未允许云端调用，因此没有生成回答。"
                        "开启云端后可执行真正的无 RAG 云端对照。"
                    ),
                    structured_result={"status": "no_rag_no_cloud"},
                    warnings=["no_rag_no_cloud"],
                )
                fallback_used = False
                fallback_reason = ""
                stage(
                    "no_rag_no_cloud",
                    "not_run",
                    fallback_started,
                    summary="comparison branch intentionally did not retrieve",
                )
            else:
                fallback_used = (
                    fallback_used
                    or allow_cloud
                    or (selected_definition.provider == "xingchen")
                )
                fallback_reason = fallback_reason or (
                    "cloud_disabled_for_debug"
                    if not allow_cloud
                    else "cloud_unavailable"
                )
            if retrieval is None and result is None:
                retrieval = await asyncio.to_thread(
                    self.rag.search,
                    query_text=question,
                    course_id=course_id,
                    intent=intent.value,
                    target_agent_id="LEARN_01_LOCAL_RETRIEVAL_V1",
                    include_images=False,
                    use_reranker=False,
                )
            if result is None:
                assert retrieval is not None
                execution = self.knowledge_qa.from_retrieval(
                    "LEARN_01_LOCAL_RETRIEVAL_V1", request, retrieval
                )
                result = execution.result
                packet = execution.context
                stage(
                    "local_fallback",
                    "success",
                    fallback_started,
                    output_count=len(result.citations),
                    summary=fallback_reason,
                )

        final = {
            "answer_text": result.answer,
            "citations": result.citations,
            "related_images": result.related_images,
            "provider": result.provider,
            "selected_agent_id": decision.agent_id,
            "rag_status": retrieval.rag_status if retrieval else "disabled",
            "evidence_status": packet.evidence_status if packet else "insufficient",
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "warnings": list(dict.fromkeys(result.warnings)),
            "total_latency_ms": int((perf_counter() - started) * 1000),
        }
        stage("final", "success", started, output_count=1)
        trace = {
            "trace_id": trace_id,
            "request_id": request_id,
            "started_at": utc_iso(),
            "stages": stages,
            "route": decision.model_dump(mode="json"),
            "retrieval": retrieval.model_dump(mode="json") if retrieval else {},
            "context": packet.model_dump(mode="json") if packet else {},
            "retrieved_context": packet.to_retrieved_context() if packet else "",
            "cloud": cloud,
            "citation_validation": citation,
            "final": final,
        }
        self.store.put(trace)
        return trace
