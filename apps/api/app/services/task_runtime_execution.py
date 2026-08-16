from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter

from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentValidationResult,
    ExternalRetrievalResult,
)
from app.core.errors import NotConfiguredError
from app.runtime import RuntimeRunStatus
from app.services.research_frontier_service import ResearchFrontierService
from app.services.runtime_execution_boundary import RuntimeExecutionBoundary
from app.services.runtime_persistence_hooks import RuntimePersistenceHooks
from app.services.runtime_result_pipeline import RuntimeResultPipeline
from app.services.task_post_processing import TaskPostProcessingService
from app.services.task_progress import TaskProgressReporter
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
    ) -> None:
        self.runtime_boundary = runtime_boundary
        self.runtime_hooks = runtime_hooks
        self.result_pipeline = result_pipeline
        self.progress = progress
        self.post_processing = post_processing
        self.plan_proposals_enabled = plan_proposals_enabled

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
        if (
            result is None
            or prepared.runtime_run.status != RuntimeRunStatus.COMPLETED
        ):
            raise NotConfiguredError(
                "registered Agent did not complete through Runtime"
            )
        if prepared.agent_id == ResearchFrontierService.agent_id:
            self._schedule_research_ingest(request, result)

        validation_started = perf_counter()
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
