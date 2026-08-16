from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories import TaskRepository
from app.services.task_failure_service import TaskFailureService
from app.services.task_observability import elapsed_ms
from app.services.task_post_processing import TaskPostProcessingService
from app.services.task_runtime_execution import RuntimeExecutionOutcome
from app.services.task_runtime_preparation import PreparedRuntimeTask
from app.services.task_terminal_boundary import TaskTerminalBoundary


class TaskCompletionService:
    """Commit the single successful terminal transition for a Runtime task."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        terminal_boundary: TaskTerminalBoundary,
        task_failures: TaskFailureService,
        post_processing: TaskPostProcessingService,
    ) -> None:
        self.session_factory = session_factory
        self.terminal_boundary = terminal_boundary
        self.task_failures = task_failures
        self.post_processing = post_processing

    async def commit(
        self,
        task_id: str,
        prepared: PreparedRuntimeTask,
        outcome: RuntimeExecutionOutcome,
        *,
        started_at: datetime,
        completed_at: datetime,
    ) -> None:
        async with self.session_factory() as db:
            task = await TaskRepository(db).get(task_id, for_update=True)
            if task is None:
                return
            if task.cancellation_requested:
                await self.task_failures.mark_cancelled(
                    db,
                    task_id,
                    "任务在 Runtime 返回前收到取消请求",
                )
                return
            result = outcome.result
            total_latency_ms = elapsed_ms(started_at, completed_at)
            result.metrics.latency_ms = total_latency_ms
            result.metrics.queue_latency_ms = elapsed_ms(
                task.created_at,
                started_at,
            )
            result.metrics.provider_latency_ms = outcome.provider_latency_ms
            result.metrics.total_latency_ms = total_latency_ms
            result.metrics.route_latency_ms = prepared.route_latency_ms
            result.metrics.model_calls += (
                self._optional_int(prepared.route_metadata.get("model_calls", 0))
                or 0
            )
            result.metrics.input_tokens = self._sum_optional_metrics(
                result.metrics.input_tokens,
                self._optional_int(prepared.route_metadata.get("input_tokens")),
            )
            result.metrics.output_tokens = self._sum_optional_metrics(
                result.metrics.output_tokens,
                self._optional_int(prepared.route_metadata.get("output_tokens")),
            )
            result.metrics.retrieval_latency_ms = result.retrieval_latency_ms
            result.metrics.context_latency_ms = 0
            result.metrics.citation_latency_ms = 0
            result.metrics.model_latency_ms = outcome.provider_latency_ms
            result.metrics.verification_latency_ms = int(
                outcome.validation.latency_ms
            )
            result.metrics.retry_count = max(0, task.attempt - 1)
            result.metrics.provider_used = result.provider
            result.metrics.fallback_used = result.fallback_used
            result.metrics.degraded_reason = result.fallback_reason
            quality_gate = result.structured_result.get("quality_gate", {})
            result.metrics.quality_status = (
                str(quality_gate.get("status", "not_checked"))
                if isinstance(quality_gate, dict)
                else "not_checked"
            )
            result.metrics.final_confidence = result.confidence
            timings = {
                "route_ms": prepared.route_latency_ms,
                "retrieval_ms": result.retrieval_latency_ms,
                "context_ms": 0,
                "cloud_ms": outcome.provider_latency_ms,
                "model_ms": outcome.provider_latency_ms,
                "citation_ms": 0,
                "validation_ms": int(outcome.validation.latency_ms),
                "total_ms": total_latency_ms,
            }
            result.timings = timings
            await self.terminal_boundary.commit(
                db,
                task=task,
                agent_id=prepared.agent_id,
                agent_definition=prepared.agent_definition,
                request=outcome.request,
                routing=dict(outcome.routing),
                result=result,
                runtime_run=prepared.runtime_run,
                conversation_bundle=prepared.conversation_bundle,
                workflow_bundle=None,
                timings=timings,
                validation=outcome.validation,
                started_at=started_at,
                completed_at=completed_at,
                total_latency_ms=total_latency_ms,
            )
            await self.task_failures.cleanup_evaluation_attachments(db, task.id)
            await db.commit()
            self.post_processing.schedule_memory_summary(task.id, task.session_id)

    @staticmethod
    def _sum_optional_metrics(
        first: int | None,
        second: int | None,
    ) -> int | None:
        if first is None and second is None:
            return None
        return (first or 0) + (second or 0)

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float, str)):
            try:
                return int(value)
            except ValueError:
                return None
        return None
