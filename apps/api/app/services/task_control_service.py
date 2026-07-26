from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import (
    AgentEventType,
    AgentRequest,
    RouteDecision,
    RouteStatus,
    new_id,
)
from app.contracts.conversation import MessageStatus
from app.core.errors import ConflictError, NotFoundError
from app.models import TaskModel, TaskStatus
from app.providers.base import AgentProvider
from app.repositories import TaskRepository
from app.services.conversation_message_service import ConversationMessageService
from app.services.event_service import append_task_event
from app.services.task_creation_service import TaskCreationService

RETRYABLE_FAILURES = {
    "background_task_error",
    "model_provider_error",
    "provider_error",
    "provider_timeout",
    "runner_shutdown",
    "xingchen_connection_error",
    "xingchen_timeout",
}
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
        if original.status != TaskStatus.FAILED:
            raise ConflictError(
                "只有可重试失败任务可以重试",
                details={"status": original.status.value},
            )
        if original.failure_category not in RETRYABLE_FAILURES:
            raise ConflictError(
                "该错误类别不可重试",
                details={"failure_category": original.failure_category},
            )
        if original.attempt >= original.max_attempts:
            raise ConflictError(
                "任务已达到最大尝试次数",
                details={
                    "attempt": original.attempt,
                    "max_attempts": original.max_attempts,
                },
            )

        payload = dict(original.input_content)
        payload["task_id"] = new_id("task")
        options = dict(payload.get("options") or {})
        options.pop("idempotency_key", None)
        options["max_attempts"] = original.max_attempts
        payload["options"] = options
        request = AgentRequest.model_validate(payload)
        route_context = request.options.get("_routing", {})
        new_task = await TaskCreationService(
            self.db, self.provider.provider_name
        ).create_queued(
            request,
            route=RouteDecision(
                agent_id=original.agent_id,
                scene=request.scene.value,
                course_id=original.course_id,
                intent=original.intent,
                route_status=RouteStatus(original.route_status),
                reason=f"retry preserves route from task {original.id}",
                retrieval_required=bool(route_context.get("retrieval_required", False)),
                provider_required=bool(route_context.get("provider_required", False)),
                route_source=str(route_context.get("route_source", "local_degraded")),
                route_confidence=float(route_context.get("route_confidence", 1.0)),
                fallback_used=bool(route_context.get("fallback_used", False)),
                original_agent_id=route_context.get("original_agent_id"),
            ),
            parent_task_id=original.id,
            attempt=original.attempt + 1,
            existing_user_message_id=original.user_message_id,
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
            task.cancel_requested_at = datetime.now(UTC)
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
            message = await ConversationMessageService(
                self.db
            ).append_terminal_failure(
                task,
                status=MessageStatus.CANCELLED,
                reason="任务已取消。",
            )
            task.assistant_message_id = message.id if message is not None else None
        await self.provider.cancel(task.id)
        await self.db.commit()
        return task
