from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentEventType, AgentRequest, new_id
from app.core.errors import ConflictError, NotFoundError
from app.models import TaskModel, TaskStatus
from app.providers.base import AgentProvider
from app.repositories import TaskRepository
from app.services.event_service import append_task_event
from app.services.task_creation_service import TaskCreationService

RETRYABLE_STATUSES = {TaskStatus.FAILED, TaskStatus.CANCELLED}
TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}


class TaskControlService:
    def __init__(self, db: AsyncSession, provider: AgentProvider) -> None:
        self.db = db
        self.provider = provider
        self.repository = TaskRepository(db)

    async def retry(self, task_id: str) -> TaskModel:
        original = await self.repository.get(task_id, for_update=True)
        if original is None:
            raise NotFoundError("任务不存在", details={"task_id": task_id})
        if original.status not in RETRYABLE_STATUSES:
            raise ConflictError(
                "只有 failed 或 cancelled 任务可以重试",
                details={"status": original.status.value},
            )

        payload = dict(original.input_content)
        payload["task_id"] = new_id("task")
        request = AgentRequest.model_validate(payload)
        new_task = await TaskCreationService(
            self.db, self.provider.provider_name
        ).create_queued(
            request,
            agent_id=original.agent_id,
            parent_task_id=original.id,
            attempt=original.attempt + 1,
        )
        await append_task_event(
            self.db,
            original.id,
            AgentEventType.TASK_RETRY_CREATED,
            agent_id=original.agent_id,
            data={"retry_task_id": new_task.id, "attempt": new_task.attempt},
        )
        await self.db.commit()
        return new_task

    async def cancel(self, task_id: str) -> TaskModel:
        task = await self.repository.get(task_id, for_update=True)
        if task is None:
            raise NotFoundError("任务不存在", details={"task_id": task_id})
        if task.status in TERMINAL_STATUSES:
            raise ConflictError(
                "终态任务不可取消",
                details={"status": task.status.value},
            )
        if not task.cancellation_requested:
            task.cancellation_requested = True
            await append_task_event(
                self.db,
                task.id,
                AgentEventType.CANCEL_REQUESTED,
                agent_id=task.agent_id,
            )
        if task.status == TaskStatus.QUEUED:
            task.status = TaskStatus.CANCELLED
            now = datetime.now(UTC)
            task.completed_at = now
            task.updated_at = now
            await append_task_event(
                self.db,
                task.id,
                AgentEventType.TASK_CANCELLED,
                agent_id=task.agent_id,
                data={"reason": "queued task cancelled"},
            )
        await self.provider.cancel(task.id)
        await self.db.commit()
        return task
