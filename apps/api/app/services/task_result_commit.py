from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AgentDefinition
from app.contracts import (
    AgentEventType,
    AgentRequest,
    AgentResult,
    AgentResultStatus,
)
from app.core.errors import ConflictError
from app.models import AgentRunModel, ArtifactModel, TaskModel
from app.runtime import AgentRun, RuntimeRunStatus
from app.services.event_service import append_task_event
from app.services.runtime_execution_boundary import RuntimeExecutionBoundary


class TaskTerminalCommitError(ConflictError):
    """Raised when a non-successful result reaches the terminal boundary."""

    code = "task_terminal_commit_rejected"


def ensure_terminal_success(
    *, result: AgentResult, runtime_run: AgentRun | None
) -> None:
    """Reject terminal success unless both result and Runtime are complete.

    This guard is intentionally side-effect free so callers can invoke it
    before mutating the Task or opening the terminal side-effect group.
    """

    if result.status != AgentResultStatus.COMPLETED:
        raise TaskTerminalCommitError(
            "only completed AgentResult values may enter terminal commit",
            details={"result_status": result.status.value},
        )
    if not result.answer.strip():
        raise TaskTerminalCommitError(
            "empty AgentResult answer cannot enter terminal commit",
            details={"result_status": result.status.value, "reason": "empty_answer"},
        )
    if runtime_run is not None and runtime_run.status in {
        RuntimeRunStatus.FAILED,
        RuntimeRunStatus.CANCELLED,
    }:
        raise TaskTerminalCommitError(
            "failed or cancelled Runtime Run cannot enter terminal commit",
            details={"runtime_status": runtime_run.status.value},
        )


class TaskResultCommitService:
    """Persist a terminal Runtime result through the Task/SSE API."""

    def __init__(self, runtime_boundary: RuntimeExecutionBoundary) -> None:
        self.runtime_boundary = runtime_boundary

    async def commit(
        self,
        db: AsyncSession,
        *,
        task: TaskModel,
        agent_id: str,
        agent_definition: AgentDefinition,
        request: AgentRequest,
        routing: dict[str, object],
        result: AgentResult,
        runtime_run: AgentRun | None,
        started_at: datetime,
        completed_at: datetime,
        total_latency_ms: int,
        context_usage: dict[str, object],
    ) -> None:
        """Write the terminal result, run record, artifacts, and completion events."""
        ensure_terminal_success(result=result, runtime_run=runtime_run)
        result_payload = result.model_dump(mode="json")
        if context_usage:
            result_payload["context_usage"] = context_usage
        task.result_content = result_payload

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

        if runtime_run is not None:
            await self.runtime_boundary.finalize(
                db,
                task_id=task.id,
                status=result.status.value,
                provider=result.provider,
                latency_ms=total_latency_ms,
                trace_id=result.trace_id or result.request_id or None,
                metrics_data=result.metrics.model_dump(mode="json"),
                artifact_ids=(artifact.artifact_id for artifact in result.artifacts),
                run=runtime_run,
            )
        else:
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
                    trace_id=result.trace_id or result.request_id or None,
                    metrics_data=result.metrics.model_dump(mode="json"),
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
