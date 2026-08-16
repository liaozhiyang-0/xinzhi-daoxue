from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AgentDefinition
from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentValidationResult,
    WorkflowContextBundle,
)
from app.contracts.conversation import ConversationContextBundle
from app.models import TaskModel, TaskStatus
from app.runtime import AgentRun
from app.services.task_result_commit import (
    TaskResultCommitService,
    ensure_terminal_success,
)
from app.services.task_result_presentation import TaskResultPresentationService
from app.services.task_session_commit import TaskSessionCommitService


class TaskTerminalBoundary:
    """Own the Task/SSE terminal protocol for successful Runtime execution."""

    def __init__(
        self,
        presentation: TaskResultPresentationService,
        session_commit: TaskSessionCommitService,
        result_commit: TaskResultCommitService,
    ) -> None:
        self.presentation = presentation
        self.session_commit = session_commit
        self.result_commit = result_commit

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
        conversation_bundle: ConversationContextBundle | None,
        workflow_bundle: WorkflowContextBundle | None,
        timings: dict[str, int],
        validation: AgentValidationResult,
        started_at: datetime,
        completed_at: datetime,
        total_latency_ms: int,
    ) -> AgentResult:
        # Guard before presentation, Task status, session messages, or any
        # other terminal side effect. The commit service repeats this check
        # at its own write boundary for direct callers and defense in depth.
        ensure_terminal_success(result=result, runtime_run=runtime_run)
        result = self.presentation.apply(
            definition=agent_definition,
            result=result,
            request=request,
            bundle=workflow_bundle,
            routing=dict(routing),
            timings=dict(timings),
            validation=validation,
        )
        task.agent_id = agent_id
        task.provider = result.provider
        task.status = TaskStatus.COMPLETED
        task.completed_at = completed_at
        task.updated_at = completed_at
        task.heartbeat_at = completed_at
        task.lease_expires_at = None
        context_usage = await self.session_commit.commit(
            db,
            task=task,
            request=request,
            result=result,
            conversation_bundle=conversation_bundle,
        )
        await self.result_commit.commit(
            db,
            task=task,
            agent_id=agent_id,
            agent_definition=agent_definition,
            request=request,
            routing=dict(routing),
            result=result,
            runtime_run=runtime_run,
            started_at=started_at,
            completed_at=completed_at,
            total_latency_ms=total_latency_ms,
            context_usage=context_usage,
        )
        return result
