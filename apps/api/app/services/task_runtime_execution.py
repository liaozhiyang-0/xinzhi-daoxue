from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter

from app.application.tasks.progress import TaskProgressReporter
from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentValidationResult,
    ExternalRetrievalResult,
)
from app.core.errors import NotConfiguredError, ProviderCancelledError
from app.observability import ModelCallRecord, ModelTracer, RuntimeTimingTrace
from app.runtime import (
    RuntimeNodeError,
    RuntimeRunStatus,
    normalize_runtime_error_code,
)
from app.services.circuit_visualization import project_circuit_artifact
from app.services.reflection_service import ReflectionService
from app.services.research_frontier_service import ResearchFrontierService
from app.services.runtime_execution_boundary import RuntimeExecutionBoundary
from app.services.runtime_persistence_hooks import RuntimePersistenceHooks
from app.services.runtime_result_pipeline import RuntimeResultPipeline
from app.services.task_post_processing import TaskPostProcessingService
from app.services.task_runtime_preparation import PreparedRuntimeTask

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RuntimeExecutionOutcome:
    request: AgentRequest
    result: AgentResult
    validation: AgentValidationResult
    routing: dict[str, object]
    provider_latency_ms: int


class TaskRuntimeExecutionService:
    """Execute and govern one prepared Runtime run."""

    def __init__(
        self,
        runtime_boundary: RuntimeExecutionBoundary,
        runtime_hooks: RuntimePersistenceHooks,
        result_pipeline: RuntimeResultPipeline,
        progress: TaskProgressReporter,
        post_processing: TaskPostProcessingService,
        *,
        plan_proposals_enabled: bool,
        reflection: ReflectionService | None = None,
        model_tracer: ModelTracer | None = None,
    ) -> None:
        self.runtime_boundary = runtime_boundary
        self.runtime_hooks = runtime_hooks
        self.result_pipeline = result_pipeline
        self.progress = progress
        self.post_processing = post_processing
        self.plan_proposals_enabled = plan_proposals_enabled
        self.reflection = reflection
        self.model_tracer = model_tracer

    async def execute(
        self,
        prepared: PreparedRuntimeTask,
        *,
        runner_started: float,
    ) -> RuntimeExecutionOutcome:
        if not prepared.launch_decision.should_execute:
            raise NotConfiguredError(
                "registered Agent Runtime execution was disabled"
            )
        request = self._with_upstream_elapsed(prepared.request, runner_started)
        RuntimeTimingTrace.mark(request.options, "runtime_execute_start")
        runtime_started = perf_counter()
        result = await self.runtime_boundary.execute(
            prepared.agent_id,
            request,
            prepared.runtime_run,
            context=None,
            checkpoint_hook=self.runtime_hooks.checkpoint,
            event_hook=self.runtime_hooks.append_node_event,
            control_provider=self.runtime_hooks.control,
            decision_event_hook=self.runtime_hooks.append_decision_event,
            plan_proposal_provider=(
                self.runtime_hooks.propose_plan
                if self.plan_proposals_enabled
                else None
            ),
        )
        RuntimeTimingTrace.observe(
            request.options,
            "runtime_execute",
            (perf_counter() - runtime_started) * 1000,
        )
        if prepared.runtime_run.status == RuntimeRunStatus.CANCELLED:
            # Keep Runtime cancellation on the task cancellation path instead
            # of turning it into a generic configuration failure.
            raise ProviderCancelledError("任务已取消")
        if (
            result is None
            or prepared.runtime_run.status != RuntimeRunStatus.COMPLETED
        ):
            error_code = self._runtime_failure_code(prepared.runtime_run)
            if error_code == "cancelled":
                raise ProviderCancelledError("任务已取消")
            raise RuntimeNodeError(
                error_code,
                "registered Agent Runtime did not complete "
                f"(status={prepared.runtime_run.status.value})",
            )
        result = result.model_copy(
            update={
                "task_id": request.task_id,
                "course_id": request.course_id,
            }
        )
        circuit_started = perf_counter()
        result = project_circuit_artifact(result, prepared.runtime_run)
        circuit_elapsed_ms = (perf_counter() - circuit_started) * 1000
        RuntimeTimingTrace.observe(
            request.options, "circuit_render", circuit_elapsed_ms
        )
        RuntimeTimingTrace.record_tool_nodes(request.options, prepared.runtime_run)
        knowledge_payload = result.structured_result.get("knowledge", {})
        knowledge_hits = (
            knowledge_payload.get("hits", [])
            if isinstance(knowledge_payload, dict)
            else []
        )
        rag_chars = sum(
            len(str(hit.get("content", "")))
            for hit in knowledge_hits
            if isinstance(hit, dict)
        )
        tool_chars = sum(
            len(str(call.get("result", "")))
            for call in result.structured_result.get("tool_verification", [])
            if isinstance(call, dict)
        )
        RuntimeTimingTrace.record_context_usage(
            request.options,
            rag_chars=rag_chars,
            tool_chars=tool_chars,
        )
        RuntimeTimingTrace.fingerprint(
            request.options,
            "rag_query_hash",
            request.input_text(),
        )
        RuntimeTimingTrace.fingerprint(
            request.options,
            "evidence_ids_hash",
            result.citations
            or result.structured_result.get("verified_evidence_ids", []),
        )
        model_records = self._model_records(request)
        recorded_model_count = RuntimeTimingTrace.record_model_calls(
            request.options, model_records
        )
        if recorded_model_count == 0:
            RuntimeTimingTrace.increment(
                request.options, "model_call_count", result.metrics.model_calls
            )
            RuntimeTimingTrace.observe(
                request.options,
                "model",
                result.metrics.provider_latency_ms
                or result.metrics.model_latency_ms
                or 0,
            )
        else:
            RuntimeTimingTrace.observe(
                request.options,
                "model",
                sum(int(item.elapsed_ms) for item in model_records),
            )
        RuntimeTimingTrace.increment(
            request.options, "tool_call_count", result.metrics.tool_calls
        )
        RuntimeTimingTrace.increment(
            request.options, "rag_call_count", result.metrics.retrieval_calls
        )
        if recorded_model_count == 0:
            RuntimeTimingTrace.increment(
                request.options, "retry_count", result.metrics.retry_count
            )
            RuntimeTimingTrace.increment(
                request.options,
                "fallback_count",
                result.metrics.fallback_count + int(result.fallback_used),
            )
        RuntimeTimingTrace.observe(
            request.options,
            "rag",
            result.metrics.retrieval_latency_ms or result.retrieval_latency_ms,
        )
        validation_started = perf_counter()
        RuntimeTimingTrace.mark(request.options, "quality_gate_start")
        await self.progress.append(
            request.task_id,
            prepared.agent_id,
            stage_id="result_validation",
            status="started",
            label="正在校验 Runtime 结果",
            progress=0.86,
        )
        governed = self.result_pipeline.process(
            definition=prepared.agent_definition,
            agent_id=prepared.agent_id,
            request=request,
            result=result,
            execution_plan=prepared.execution_plan,
            intent_plan=prepared.intent_plan,
            overall_route_metadata=prepared.route_metadata,
        )
        RuntimeTimingTrace.observe(
            request.options,
            "result_validation",
            (perf_counter() - validation_started) * 1000,
        )
        answer_before_reflection = governed.result.answer
        answer_changed = False
        if self.reflection is not None:
            reflection_started = perf_counter()
            RuntimeTimingTrace.mark(request.options, "reflection_start")
            reflected = await self.reflection.apply(
                agent_id=prepared.agent_id,
                request=request,
                result=governed.result,
                validation=governed.validation,
                reverify=lambda revised: self.result_pipeline.reverify(
                    definition=prepared.agent_definition,
                    agent_id=prepared.agent_id,
                    request=request,
                    result=revised,
                ),
            )
            governed = governed.__class__(
                reflected.result,
                reflected.validation,
                governed.routing,
            )
            answer_changed = governed.result.answer != answer_before_reflection
            RuntimeTimingTrace.observe(
                request.options,
                "reflection",
                (perf_counter() - reflection_started) * 1000,
            )
        RuntimeTimingTrace.observe(
            request.options,
            "quality_gate",
            (perf_counter() - validation_started) * 1000,
        )
        RuntimeTimingTrace.mark(
            request.options,
            "quality_gate_decision",
            details={
                "result_status": governed.validation.result_status,
                "response_usable": governed.validation.response_usable,
                "answer_changed": answer_changed,
            },
        )
        RuntimeTimingTrace.fingerprint(
            request.options,
            "quality_gate_input_hash",
            {
                "agent_id": prepared.agent_id,
                "validation": governed.validation.model_dump(mode="json"),
                "status": governed.result.status.value,
            },
        )
        await self.progress.append(
            request.task_id,
            prepared.agent_id,
            stage_id="result_validation",
            status="completed" if governed.validation.response_usable else "failed",
            label="Runtime 结果校验完成",
            progress=0.94,
            elapsed_ms=int((perf_counter() - validation_started) * 1000),
            detail=governed.validation.result_status,
        )
        if not governed.validation.response_usable:
            # A completed Runtime is not enough to publish an answer: the
            # cross-Agent contract must also accept the result.  Fail before
            # post-processing or terminal Task commit so invalid output cannot
            # leak into session memory or appear as a successful turn.
            raise RuntimeNodeError(
                "runtime_result_validation_failed",
                "Runtime result did not pass the output contract",
            )
        if prepared.agent_id == ResearchFrontierService.agent_id:
            self._schedule_research_ingest(request, result)
        provider_latency_ms = (
            governed.result.metrics.provider_latency_ms
            or governed.result.metrics.model_latency_ms
            or 0
        )
        return RuntimeExecutionOutcome(
            request=request,
            result=governed.result,
            validation=governed.validation,
            routing=dict(governed.routing),
            provider_latency_ms=provider_latency_ms,
        )

    @staticmethod
    def _runtime_failure_code(runtime_run: object) -> str:
        """Preserve the most specific durable node failure for task handling."""

        nodes = getattr(runtime_run, "nodes", {})
        if isinstance(nodes, dict):
            for state in nodes.values():
                if getattr(state, "status", None) != "failed":
                    continue
                error_code = str(getattr(state, "error_code", "")).strip()
                if error_code:
                    return normalize_runtime_error_code(error_code)
            for state in nodes.values():
                if getattr(state, "status", None) != "partial":
                    continue
                observation = getattr(state, "observation", None)
                facts = getattr(observation, "facts", {})
                if isinstance(facts, dict):
                    reason_code = str(facts.get("reason_code", "")).strip()
                    if reason_code:
                        return normalize_runtime_error_code(reason_code)
        if getattr(runtime_run, "status", None) == RuntimeRunStatus.FAILED:
            return "runtime_execution_failed"
        return "runtime_result_missing"

    def _schedule_research_ingest(
        self,
        request: AgentRequest,
        result: AgentResult,
    ) -> None:
        raw_external = result.structured_result.get("external_retrieval")
        if not isinstance(raw_external, dict) or not raw_external:
            return
        try:
            external_result = ExternalRetrievalResult.model_validate(raw_external)
        except ValueError:
            logger.warning(
                "research_external_result_sync_failed task_id=%s",
                request.task_id,
                exc_info=True,
            )
            return
        self.post_processing.schedule_research_ingest(
            external_result,
            query=request.input_text(),
            task_id=request.task_id,
        )

    @staticmethod
    def _with_upstream_elapsed(
        request: AgentRequest,
        runner_started: float,
    ) -> AgentRequest:
        options = dict(request.options)
        options["_upstream_elapsed_seconds"] = max(
            0.0,
            perf_counter() - runner_started,
        )
        return request.model_copy(update={"options": options})

    def _model_records(self, request: AgentRequest) -> list[ModelCallRecord]:
        if self.model_tracer is None:
            return []
        trace_id = str(
            request.options.get("request_id")
            or request.options.get("trace_id")
            or ""
        )
        if not trace_id:
            return []
        return [
            record
            for record in self.model_tracer.list()
            if record.request_id == trace_id
        ]
