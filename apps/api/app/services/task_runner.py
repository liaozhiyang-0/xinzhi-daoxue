from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents import AgentDefinition, AgentRegistry, TaskRouter
from app.contracts import (
    AgentEventType,
    AgentExecutionPlan,
    AgentRequest,
    AgentResult,
    Artifact,
    KnowledgeHit,
    RetrievalContextPacket,
    RetrievalResult,
    RouteDecision,
)
from app.core.errors import AppError, NotConfiguredError, ProviderCancelledError
from app.models import AgentRunModel, ArtifactModel, TaskStatus
from app.providers.base import AgentProvider
from app.repositories import SessionRepository, TaskRepository
from app.services.agent_runtime import AgentExecutionPlanner
from app.services.citation_validator import CitationValidator
from app.services.event_service import append_task_event
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_qa_service import (
    KnowledgeQAExecution,
    KnowledgeQAService,
)
from app.services.rag_retrieval import RAGRetrievalService
from app.services.session_context import SessionContextService
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def elapsed_ms(started: datetime, completed: datetime) -> int:
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=UTC)
    return max(0, int((completed - started).total_seconds() * 1000))


class TaskRunner:
    """In-process runner with a submit API that a future worker can replace."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: AgentProvider,
        knowledge_base: KnowledgeBaseService,
        agent_registry: AgentRegistry,
        knowledge_qa: KnowledgeQAService,
        rag_retrieval: RAGRetrievalService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self.knowledge_base = knowledge_base
        self.agent_registry = agent_registry
        self.knowledge_qa = knowledge_qa
        self.rag_retrieval = rag_retrieval
        self.citation_validator = CitationValidator()
        self.execution_planner = AgentExecutionPlanner(
            agent_registry, knowledge_base.settings
        )
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def submit(self, task_id: str) -> bool:
        existing = self._tasks.get(task_id)
        if existing is not None and not existing.done():
            return False
        background = asyncio.create_task(self.run(task_id), name=f"xzd-task-{task_id}")
        self._tasks[task_id] = background
        background.add_done_callback(lambda _: self._tasks.pop(task_id, None))
        return True

    async def shutdown(self) -> None:
        active = [task for task in self._tasks.values() if not task.done()]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        if self.rag_retrieval is not None:
            await asyncio.to_thread(self.rag_retrieval.close)

    async def run(self, task_id: str) -> None:
        request: AgentRequest
        started_at = utc_now()
        try:
            async with self.session_factory() as db:
                repository = TaskRepository(db)
                task = await repository.get(task_id, for_update=True)
                if task is None or task.status != TaskStatus.QUEUED:
                    return
                if task.cancellation_requested:
                    await self._mark_cancelled(db, task_id, "任务在执行前已取消")
                    return
                agent_id = task.agent_id
                agent_definition = self.agent_registry.get(agent_id)
                active_provider = (
                    "local"
                    if agent_definition.mode == "retrieval_only"
                    else self.provider.provider_name
                )
                task.status = TaskStatus.RUNNING
                task.started_at = started_at
                task.updated_at = started_at
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.TASK_RUNNING,
                    agent_id=task.agent_id,
                    data={"attempt": task.attempt},
                )
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.AGENT_STARTED,
                    agent_id=task.agent_id,
                    data={"provider": active_provider},
                )
                request = AgentRequest.model_validate(task.input_content)
                decision = RouteDecision.model_validate(
                    request.options.get("_routing", {})
                )
                execution_plan = self.execution_planner.build(decision, request)
                request = self._with_execution_plan(request, execution_plan)
                await db.commit()

            knowledge_hits: list[KnowledgeHit] = []
            retrieval_result: RetrievalResult | None = None
            retrieval_attempted = False
            retrieval_packet: RetrievalContextPacket | None = None
            provider_latency_ms = 0
            if agent_definition.mode == "routing_only":
                dispatch_started = perf_counter()
                dispatch_result = await self.provider.run(
                    agent_id, request, stream=False
                )
                provider_latency_ms += int((perf_counter() - dispatch_started) * 1000)
                decision = TaskRouter(
                    self.agent_registry, self.knowledge_base.settings
                ).route_cloud_response(dispatch_result.answer, request)
                agent_id = decision.agent_id
                agent_definition = self.agent_registry.get(agent_id)
                options = dict(request.options)
                options["_routing"] = decision.model_dump(mode="json")
                request = request.model_copy(update={"options": options})
                await self._append_cloud_route_event(task_id, decision)
                execution_plan = self.execution_planner.build(decision, request)
                request = self._with_execution_plan(request, execution_plan)

            if agent_definition.mode == "retrieval_only":
                execution = await asyncio.to_thread(
                    self.knowledge_qa.run, agent_id, request
                )
                await self._append_local_knowledge_events(task_id, agent_id, execution)
                result = execution.result
            else:
                if self.knowledge_base.settings.xingchen_use_local_kb_context:
                    (
                        retrieval_result,
                        retrieval_attempted,
                    ) = await self._retrieve_knowledge(
                        request, agent_definition, execution_plan
                    )
                    knowledge_hits = (
                        retrieval_result.hits if retrieval_result is not None else []
                    )
                if retrieval_attempted:
                    await self._append_retrieval_event(
                        task_id, agent_id, request.course_id, len(knowledge_hits)
                    )
                provider_started = perf_counter()
                provider_request = request
                if (
                    self.provider.provider_name == "xingchen"
                    and retrieval_result is not None
                    and agent_definition.retrieval_policy.generation_injection
                ):
                    retrieval_packet = self.knowledge_qa.context_service.build(
                        retrieval_result,
                        course_id=request.course_id,
                        intent=request.intent.value,
                    )
                    provider_request = self._with_learning_context(
                        request, retrieval_packet
                    )
                cloud_error: AppError | None = None
                cloud_response_failed = False
                try:
                    if (
                        self.provider.provider_name == "xingchen"
                        and agent_definition.provider == "xingchen"
                        and not execution_plan.configured
                    ):
                        raise NotConfiguredError(
                            "Agent Flow 或星辰凭据未配置，未发送云端请求"
                        )
                    result = await self.provider.run(
                        agent_id, provider_request, stream=False
                    )
                except AppError as exc:
                    fallback_trigger = self._fallback_trigger(exc.code)
                    if (
                        agent_definition.fallback.handler == "no_fallback"
                        or fallback_trigger not in agent_definition.fallback.trigger_on
                    ):
                        raise
                    cloud_error = exc
                    fallback = self.agent_registry.resolve_fallback(agent_id)
                    if self._uses_local_retrieval_fallback(agent_definition):
                        if fallback is None or fallback.mode != "retrieval_only":
                            raise
                        execution = await asyncio.to_thread(
                            self.knowledge_qa.run, fallback.agent_id, request
                        )
                        await self._append_local_knowledge_events(
                            task_id, fallback.agent_id, execution
                        )
                        result = execution.result
                        result.warnings.append(
                            f"云端工作流失败，已降级到本地检索回答: {exc.code}"
                        )
                    else:
                        result = self._non_cloud_fallback_result(
                            agent_definition,
                            request,
                            reason=exc.code,
                        )
                    routing = dict(request.options.get("_routing", {}))
                    routing.update(
                        {
                            "fallback_used": True,
                            "fallback_reason": exc.code,
                            "original_agent_id": agent_id,
                            "cloud_status": "cloud_failed",
                        }
                    )
                    options = dict(request.options)
                    options["_routing"] = routing
                    request = request.model_copy(update={"options": options})
                    if fallback is not None and fallback.mode == "retrieval_only":
                        agent_id = fallback.agent_id
                        agent_definition = fallback
                if cloud_error is None:
                    upstream_status = str(
                        result.structured_result.get("status", "success")
                    ).casefold()
                    routing = dict(request.options.get("_routing", {}))
                    routing["cloud_status"] = f"cloud_{upstream_status}"
                    options = dict(request.options)
                    options["_routing"] = routing
                    request = request.model_copy(update={"options": options})
                    if upstream_status == "failed" and (
                        agent_definition.fallback.handler != "no_fallback"
                    ):
                        fallback = self.agent_registry.resolve_fallback(agent_id)
                        if (
                            self._uses_local_retrieval_fallback(agent_definition)
                            and fallback is not None
                            and fallback.mode == "retrieval_only"
                        ):
                            execution = await asyncio.to_thread(
                                self.knowledge_qa.run, fallback.agent_id, request
                            )
                            await self._append_local_knowledge_events(
                                task_id, fallback.agent_id, execution
                            )
                            result = execution.result
                            result.warnings.append(
                                "云端LEARN返回failed，已明确降级到本地检索回答"
                            )
                            routing.update(
                                {
                                    "fallback_used": True,
                                    "fallback_reason": "cloud_failed_status",
                                    "original_agent_id": agent_id,
                                    "cloud_status": "cloud_failed",
                                }
                            )
                            options["_routing"] = routing
                            request = request.model_copy(update={"options": options})
                            agent_id = fallback.agent_id
                            agent_definition = fallback
                            cloud_response_failed = True
                        elif not self._uses_local_retrieval_fallback(agent_definition):
                            result = self._non_cloud_fallback_result(
                                agent_definition,
                                request,
                                reason="cloud_failed_status",
                            )
                            routing.update(
                                {
                                    "fallback_used": True,
                                    "fallback_reason": "cloud_failed_status",
                                    "original_agent_id": agent_id,
                                    "cloud_status": "cloud_failed",
                                }
                            )
                            options["_routing"] = routing
                            request = request.model_copy(update={"options": options})
                            cloud_response_failed = True
                provider_latency_ms += int((perf_counter() - provider_started) * 1000)
                if retrieval_attempted:
                    result.metrics.retrieval_calls += 1
                if (
                    retrieval_packet is not None
                    and cloud_error is None
                    and not cloud_response_failed
                    and str(result.structured_result.get("status", "")).casefold()
                    != "misrouted"
                ):
                    declared_refs = result.structured_result.get(
                        "source_references", []
                    )
                    validation = self.citation_validator.validate(
                        result.answer,
                        retrieval_packet,
                        declared_references=(
                            declared_refs if isinstance(declared_refs, list) else []
                        ),
                    )
                    result.structured_result["citation_validation"] = {
                        "status": "passed" if validation.valid else "failed",
                        "referenced_ids": list(validation.referenced_ids),
                        "valid_ids": list(validation.valid_ids),
                        "invalid_ids": list(validation.invalid_ids),
                        "missing": validation.missing,
                    }
                    source_by_id = {
                        item.evidence_id: item.source_ref
                        for item in retrieval_packet.evidence
                    }
                    result.citations = [
                        source_by_id[item]
                        for item in validation.valid_ids
                        if item in source_by_id
                    ]
                    if not validation.valid:
                        result.warnings.extend(validation.warnings)
                        for invalid_id in validation.invalid_ids:
                            result.answer = result.answer.replace(
                                f"[{invalid_id}]", "[引用无效]"
                            )
            if retrieval_result is not None:
                hit_payloads = [hit.model_dump(mode="json") for hit in knowledge_hits]
                result.structured_result["knowledge"] = {
                    "mode": retrieval_result.retrieval_mode,
                    "hits": hit_payloads,
                    "images": [
                        item.model_dump(mode="json")
                        for item in retrieval_result.image_hits
                    ],
                    "trace": retrieval_result.trace,
                }
                result.rag_status = retrieval_result.rag_status
                result.evidence_status = (
                    retrieval_packet.evidence_status
                    if retrieval_packet is not None
                    else (
                        "partial"
                        if retrieval_result.hits or retrieval_result.image_hits
                        else "insufficient"
                    )
                )
                result.related_images = [
                    item.model_dump(mode="json") for item in retrieval_result.image_hits
                ]
                result.retrieval_trace_id = retrieval_result.retrieval_trace_id
                result.retrieval_latency_ms = retrieval_result.latency_ms
                result.index_version = retrieval_result.index_version
            if knowledge_hits and (
                retrieval_packet is None or agent_definition.mode == "retrieval_only"
            ):
                result.citations = list(
                    dict.fromkeys(
                        [*result.citations, *(hit.source_ref for hit in knowledge_hits)]
                    )
                )
                for artifact in result.artifacts:
                    artifact.source_refs = list(
                        dict.fromkeys(
                            [
                                *artifact.source_refs,
                                *(hit.source_ref for hit in knowledge_hits),
                            ]
                        )
                    )
                    artifact.content["knowledge_sources"] = artifact.source_refs

            routing = request.options.get("_routing", {})
            result.structured_result.update(
                {
                    "scene": agent_definition.scene,
                    "mode": agent_definition.mode,
                    "course": request.course_id,
                    "intent": request.intent.value,
                    "route_source": routing.get("route_source", "local_fast"),
                    "route_confidence": routing.get("route_confidence", 1.0),
                    "target_agent_id": agent_id,
                    "flow_configured": bool(
                        self.agent_registry.resolve_flow_id(
                            agent_id, self.knowledge_base.settings
                        )
                    ),
                    "knowledge_hit_count": len(knowledge_hits),
                    "rag_status": result.rag_status,
                    "evidence_status": result.evidence_status,
                    "related_images": result.related_images,
                    "retrieval_trace_id": result.retrieval_trace_id,
                    "retrieval_latency_ms": result.retrieval_latency_ms,
                    "index_version": result.index_version,
                    "solver_rag_generation_injection": (
                        agent_definition.retrieval_policy.generation_injection
                        and retrieval_packet is not None
                    ),
                    "execution_plan": execution_plan.model_dump(mode="json"),
                    "fallback_used": routing.get("fallback_used", False),
                    "fallback_reason": routing.get("fallback_reason", ""),
                    "cloud_status": routing.get(
                        "cloud_status",
                        (
                            "local_fallback"
                            if agent_definition.mode == "retrieval_only"
                            else "cloud_success"
                        ),
                    ),
                    "original_agent_id": routing.get("original_agent_id"),
                }
            )

            async with self.session_factory() as db:
                repository = TaskRepository(db)
                task = await repository.get(task_id, for_update=True)
                if task is None:
                    return
                if task.cancellation_requested:
                    await self._mark_cancelled(
                        db, task_id, "任务在 Provider 返回前收到取消请求"
                    )
                    return

                completed_at = utc_now()
                total_latency_ms = elapsed_ms(started_at, completed_at)
                result.metrics.latency_ms = total_latency_ms
                result.metrics.queue_latency_ms = elapsed_ms(
                    task.created_at, started_at
                )
                result.metrics.provider_latency_ms = provider_latency_ms
                task.result_content = result.model_dump(mode="json")
                task.agent_id = agent_id
                task.provider = result.provider
                task.status = TaskStatus.COMPLETED
                task.completed_at = completed_at
                task.updated_at = completed_at
                session = await SessionRepository(db).get(task.session_id)
                if session is not None:
                    SessionContextService(self.knowledge_base.settings).update(
                        session, request, result
                    )

                for artifact in result.artifacts:
                    db.add(
                        ArtifactModel(
                            id=artifact.artifact_id,
                            task_id=task.id,
                            artifact_type=artifact.artifact_type.value,
                            version=artifact.version,
                            content=artifact.content,
                            confidence=artifact.confidence,
                            created_at=artifact.created_at,
                        )
                    )
                    await append_task_event(
                        db,
                        task.id,
                        AgentEventType.ARTIFACT_CREATED,
                        agent_id=task.agent_id,
                        data={"artifact_id": artifact.artifact_id},
                    )

                db.add(
                    AgentRunModel(
                        task_id=task.id,
                        agent_id=task.agent_id,
                        provider=result.provider,
                        status=result.status.value,
                        latency_ms=total_latency_ms,
                        model_calls=result.metrics.model_calls,
                        tool_calls=result.metrics.tool_calls,
                        retrieval_calls=result.metrics.retrieval_calls,
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                )
                await append_task_event(
                    db,
                    task.id,
                    AgentEventType.AGENT_OUTPUT,
                    agent_id=task.agent_id,
                    data={
                        "provider": result.provider,
                        "mock": result.provider == "mock",
                        "scene": agent_definition.scene,
                        "mode": agent_definition.mode,
                        "course": request.course_id,
                        "intent": request.intent.value,
                        "route_source": routing.get("route_source", "local_fast"),
                        "route_confidence": routing.get("route_confidence", 1.0),
                        "target_agent_id": agent_id,
                        "fallback_used": routing.get("fallback_used", False),
                    },
                )
                await append_task_event(
                    db,
                    task.id,
                    AgentEventType.TASK_COMPLETED,
                    agent_id=task.agent_id,
                    data={
                        "artifact_count": len(result.artifacts),
                        "latency_ms": total_latency_ms,
                    },
                )
                await db.commit()
        except ProviderCancelledError as exc:
            await self._cancel_after_exception(task_id, exc.message)
        except asyncio.CancelledError:
            await self._fail_after_exception(
                task_id, "进程内任务因应用关闭而中断", "runner_shutdown"
            )
            raise
        except Exception as exc:
            message = exc.message if isinstance(exc, AppError) else "后台任务执行失败"
            code = exc.code if isinstance(exc, AppError) else "background_task_error"
            await self._fail_after_exception(task_id, message, code)

    async def _retrieve_knowledge(
        self,
        request: AgentRequest,
        agent_definition: AgentDefinition,
        execution_plan: AgentExecutionPlan,
    ) -> tuple[RetrievalResult | None, bool]:
        if not self.knowledge_base.settings.knowledge_enabled:
            return None, False
        query = self._knowledge_query(request)
        if not query and not request.attachments:
            return None, False
        plan = execution_plan
        if not plan.use_rag:
            return None, False
        top_k = agent_definition.retrieval_policy.text_top_k
        if top_k <= 0:
            return None, False
        try:
            content_types = agent_definition.knowledge_content_types
            image: bytes | None = None
            if request.attachments:
                attachment = request.attachments[0]
                if attachment.content_type.startswith("image/"):
                    image = await StorageService(self.knowledge_base.settings).read(
                        attachment.storage_key
                    )
            if self.rag_retrieval is not None:
                result = await asyncio.to_thread(
                    self.rag_retrieval.search,
                    query_text=query,
                    query_image=image,
                    course_id=request.course_id,
                    intent=request.intent.value,
                    target_agent_id=agent_definition.agent_id,
                    top_k=top_k,
                    content_types=tuple(content_types),
                    include_images=plan.use_images,
                    session_context=str(
                        request.options.get("conversation_summary", "")
                    ),
                    use_reranker=plan.reranker_mode,
                    policy_name=agent_definition.retrieval_policy.policy_name,
                    image_top_k=agent_definition.retrieval_policy.image_top_k,
                    allow_generation_injection=(
                        agent_definition.retrieval_policy.generation_injection
                    ),
                    local_budget_ms=plan.budget.retrieval_p95_target_ms,
                )
                return result, True
            return (
                await asyncio.to_thread(
                    self.knowledge_base.search_result,
                    query,
                    [request.course_id],
                    top_k * 3 if content_types else top_k,
                ),
                True,
            )
        except Exception as exc:
            logger.warning(
                "knowledge_retrieval_failed task_id=%s session_id=%s "
                "course_id=%s error=%s",
                request.task_id,
                request.session_id,
                request.course_id,
                type(exc).__name__,
            )
            return None, True

    @staticmethod
    def _uses_local_retrieval_fallback(
        definition: AgentDefinition,
    ) -> bool:
        return definition.fallback.handler == "local_retrieval_answer"

    @staticmethod
    def _fallback_trigger(error_code: str) -> str:
        return {
            "xingchen_timeout": "cloud_timeout",
            "provider_timeout": "cloud_timeout",
            "xingchen_response_parse_error": "cloud_parse_error",
            "provider_circuit_open": "open_circuit",
            "not_configured": "not_configured",
        }.get(error_code, "cloud_http_error")

    @staticmethod
    def _non_cloud_fallback_result(
        definition: AgentDefinition,
        request: AgentRequest,
        *,
        reason: str,
    ) -> AgentResult:
        messages = {
            "static_template": "云端工作流暂不可用，已返回本地结构化模板。",
            "planned_response": "该工作流尚未发布，当前仅提供规划状态。",
            "manual_review": "该请求需要人工复核，未自动生成业务结论。",
        }
        answer = messages.get(
            definition.fallback.handler,
            "当前工作流不可用，且未配置自动降级回答。",
        )
        artifact = Artifact(
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content={
                "answer": answer,
                "fallback_handler": definition.fallback.handler,
                "fallback_reason": reason,
            },
        )
        return AgentResult(
            agent_id=definition.agent_id,
            agent_version=definition.version,
            provider="local",
            course_id=request.course_id,
            intent=request.intent.value,
            answer=answer,
            structured_result={
                "status": "partial",
                "business_data": {},
                "fallback_handler": definition.fallback.handler,
            },
            artifacts=[artifact],
            warnings=[f"fallback_used:{definition.fallback.handler}:{reason}"],
            fallback_used=True,
            fallback_reason=reason,
            cloud_status="cloud_failed",
            request_id=str(request.options.get("request_id", request.task_id)),
            task_id=request.task_id,
        )

    @staticmethod
    def _with_execution_plan(
        request: AgentRequest, plan: AgentExecutionPlan
    ) -> AgentRequest:
        options = dict(request.options)
        options["_execution_plan"] = plan.model_dump(mode="json")
        return request.model_copy(update={"options": options})

    @staticmethod
    def _knowledge_query(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @classmethod
    def _with_xingchen_context(
        cls, request: AgentRequest, hits: list[KnowledgeHit]
    ) -> AgentRequest:
        question = cls._knowledge_query(request)
        prefix = f"【用户题目】\n{question}\n\n【本地知识库方法参考】\n"
        suffix = (
            "\n【使用约束】\n"
            "本地知识库仅用于方法参考。\n"
            "题目参数、电路连接和参考方向以用户输入为准。\n"
            "不得使用知识库内容覆盖题目事实。\n"
            "信息不足时请条件化作答，并明确说明假设。"
        )
        context_limit = 2000
        blocks: list[str] = []
        used = 0
        limit = int(request.options.get("_knowledge_top_k", 3))
        for index, hit in enumerate(hits[:limit], start=1):
            block = f"{index}. {hit.content.strip()}\n来源：{hit.source_ref}\n\n"
            available = context_limit - used
            if available <= 0:
                break
            blocks.append(block[:available])
            used += min(len(block), available)
        augmented = prefix + "".join(blocks) + suffix
        canonical_input = dict(request.canonical_input)
        for field in ("text", "question", "problem", "query", "prompt"):
            value = canonical_input.get(field)
            if isinstance(value, str) and value.strip():
                canonical_input[field] = augmented
                break
        options = dict(request.options)
        options["xingchen_knowledge_sources"] = [hit.source_ref for hit in hits[:limit]]
        return request.model_copy(
            update={"canonical_input": canonical_input, "options": options}
        )

    @classmethod
    def _with_learning_context(
        cls, request: AgentRequest, packet: RetrievalContextPacket
    ) -> AgentRequest:
        context = packet.to_retrieved_context()
        options = dict(request.options)
        packet_payload = packet.model_dump(mode="json")
        packet_payload["formatted_context"] = context
        options["retrieval_context_packet"] = packet_payload
        options["retrieved_context"] = context
        options.setdefault("request_id", request.task_id)
        options["xingchen_knowledge_sources"] = packet.source_refs
        return request.model_copy(update={"options": options})

    async def _append_retrieval_event(
        self, task_id: str, agent_id: str, course_id: str, hit_count: int
    ) -> None:
        async with self.session_factory() as db:
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_RETRIEVED,
                agent_id=agent_id,
                data={"course_id": course_id, "hit_count": hit_count},
            )
            await db.commit()

    async def _append_cloud_route_event(
        self, task_id: str, decision: RouteDecision
    ) -> None:
        async with self.session_factory() as db:
            await append_task_event(
                db,
                task_id,
                AgentEventType.ROUTE_SELECTED,
                agent_id=decision.agent_id,
                data=decision.model_dump(mode="json"),
            )
            await db.commit()

    async def _append_local_knowledge_events(
        self,
        task_id: str,
        agent_id: str,
        execution: KnowledgeQAExecution,
    ) -> None:
        async with self.session_factory() as db:
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_QUERY_NORMALIZED,
                agent_id=agent_id,
                data={"normalized_query": execution.retrieval.normalized_query},
            )
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_RETRIEVED,
                agent_id=agent_id,
                data={
                    "course_id": execution.context.course_id,
                    "hit_count": len(execution.retrieval.hits),
                    "confidence": execution.retrieval.confidence,
                    "retrieval_mode": execution.retrieval.retrieval_mode,
                },
            )
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_CONTEXT_BUILT,
                agent_id=agent_id,
                data={
                    "evidence_count": len(execution.context.evidence),
                    "evidence_status": execution.context.evidence_status,
                    "source_refs": execution.context.source_refs,
                },
            )
            if execution.context.evidence_status in {"insufficient", "failed"}:
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.KNOWLEDGE_INSUFFICIENT,
                    agent_id=agent_id,
                    data={"warnings": execution.context.warnings},
                )
            await append_task_event(
                db,
                task_id,
                AgentEventType.ANSWER_RETRIEVAL_ONLY_CREATED,
                agent_id=agent_id,
                data={"mode": "retrieval_only"},
            )
            await db.commit()

    async def _mark_cancelled(
        self, db: AsyncSession, task_id: str, reason: str
    ) -> None:
        task = await TaskRepository(db).get(task_id, for_update=True)
        if task is None:
            return
        now = utc_now()
        task.status = TaskStatus.CANCELLED
        task.completed_at = now
        task.updated_at = now
        task.error_message = reason
        if task.started_at:
            db.add(
                AgentRunModel(
                    task_id=task.id,
                    agent_id=task.agent_id,
                    provider=self.provider.provider_name,
                    status=TaskStatus.CANCELLED.value,
                    latency_ms=elapsed_ms(task.started_at, now),
                    started_at=task.started_at,
                    completed_at=now,
                )
            )
        await append_task_event(
            db,
            task_id,
            AgentEventType.TASK_CANCELLED,
            agent_id=task.agent_id,
            data={"reason": reason},
        )
        await db.commit()

    async def _cancel_after_exception(self, task_id: str, reason: str) -> None:
        async with self.session_factory() as db:
            await self._mark_cancelled(db, task_id, reason)

    async def _fail_after_exception(
        self, task_id: str, message: str, code: str
    ) -> None:
        async with self.session_factory() as db:
            task = await TaskRepository(db).get(task_id, for_update=True)
            if task is None or task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
            }:
                return
            if task.cancellation_requested:
                await self._mark_cancelled(
                    db,
                    task_id,
                    "任务在后台异常发生前已收到取消请求",
                )
                return
            now = utc_now()
            task.status = TaskStatus.FAILED
            task.error_message = message
            task.completed_at = now
            task.updated_at = now
            db.add(
                AgentRunModel(
                    task_id=task.id,
                    agent_id=task.agent_id,
                    provider=self.provider.provider_name,
                    status=TaskStatus.FAILED.value,
                    latency_ms=(
                        elapsed_ms(task.started_at, now) if task.started_at else None
                    ),
                    started_at=task.started_at,
                    completed_at=now,
                )
            )
            await append_task_event(
                db,
                task.id,
                AgentEventType.TASK_FAILED,
                agent_id=task.agent_id,
                data={"error_code": code},
            )
            await db.commit()
            logger.warning(
                "task_failed task_id=%s session_id=%s agent_id=%s "
                "provider=%s attempt=%s error_code=%s",
                task.id,
                task.session_id,
                task.agent_id,
                self.provider.provider_name,
                task.attempt,
                code,
            )
