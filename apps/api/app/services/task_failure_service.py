from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts import AgentEventType
from app.contracts.conversation import MessageStatus
from app.core.config import Settings
from app.models import AgentRunModel, TaskStatus
from app.repositories import TaskRepository
from app.runtime import RuntimeRunStatus
from app.services.conversation_message_service import ConversationMessageService
from app.services.evaluation_attachment_cleanup import (
    cleanup_evaluation_attachments,
)
from app.services.event_service import append_task_event
from app.services.runtime_execution_boundary import RuntimeExecutionBoundary
from app.services.task_audit import (
    audit_for_terminal,
    audit_from_task_input,
    replace_task_audit,
    terminal_event_data,
)
from app.services.task_observability import elapsed_ms

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskFailureService:
    """Own cancellation, failure, and recoverable shutdown transitions."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        runtime_boundary: RuntimeExecutionBoundary,
        *,
        provider_name: str,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.runtime_boundary = runtime_boundary
        self.provider_name = provider_name

    async def mark_cancelled(
        self,
        db: AsyncSession,
        task_id: str,
        reason: str,
    ) -> None:
        task = await TaskRepository(db).get(task_id, for_update=True)
        if task is None or task.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }:
            return
        now = _utc_now()
        task.status = TaskStatus.CANCELLED
        task.completed_at = now
        task.updated_at = now
        task.error_message = reason
        task.failure_category = "cancelled"
        task.execution_owner = None
        task.heartbeat_at = now
        task.lease_expires_at = None
        audit = audit_from_task_input(task.input_content)
        metrics_data = None
        if audit:
            audit = audit_for_terminal(audit, TaskStatus.CANCELLED.value, "cancelled")
            task.input_content = replace_task_audit(task.input_content, audit)
            metrics_data = {"audit": audit}
        runtime_finalized = await self.runtime_boundary.finalize(
            db,
            task_id=task.id,
            status=RuntimeRunStatus.CANCELLED,
            provider=self.provider_name,
            latency_ms=elapsed_ms(task.started_at, now) if task.started_at else None,
            error_code="cancelled",
            terminal_reason=reason,
            metrics_data=metrics_data,
        )
        if task.started_at and runtime_finalized is None:
            db.add(
                AgentRunModel(
                    task_id=task.id,
                    agent_id=task.agent_id,
                    provider=self.provider_name,
                    status=TaskStatus.CANCELLED.value,
                    latency_ms=elapsed_ms(task.started_at, now),
                    started_at=task.started_at,
                    completed_at=now,
                    metrics_data=metrics_data or {},
                )
            )
        await append_task_event(
            db,
            task_id,
            AgentEventType.TASK_CANCELLED,
            agent_id=task.agent_id,
            data=terminal_event_data(
                status=TaskStatus.CANCELLED.value,
                failure_category="cancelled",
                error_code="cancelled",
                error_message=reason,
                runtime_run_id=(
                    str(getattr(runtime_finalized, "run_id", ""))
                    if runtime_finalized is not None
                    else str((audit or {}).get("runtime_run_id", ""))
                ),
                reason=reason,
            ),
        )
        message = await ConversationMessageService(db).append_terminal_failure(
            task,
            status=MessageStatus.CANCELLED,
            reason="任务已取消。",
        )
        task.assistant_message_id = message.id if message is not None else None
        await self.cleanup_evaluation_attachments(db, task_id)
        await db.commit()

    async def cancel(self, task_id: str, reason: str) -> None:
        async with self.session_factory() as db:
            await self.mark_cancelled(db, task_id, reason)

    async def requeue_after_shutdown(self, task_id: str) -> None:
        async with self.session_factory() as db:
            task = await TaskRepository(db).get(task_id, for_update=True)
            if task is None or task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                return
            if task.cancellation_requested:
                await self.mark_cancelled(
                    db,
                    task_id,
                    "任务在应用关闭前已收到取消请求。",
                )
                return
            previous_status = task.status.value
            now = _utc_now()
            task.status = TaskStatus.QUEUED
            task.error_message = None
            task.failure_category = None
            task.completed_at = None
            task.execution_owner = None
            task.heartbeat_at = None
            task.lease_expires_at = None
            task.updated_at = now
            await append_task_event(
                db,
                task.id,
                AgentEventType.TASK_QUEUED,
                agent_id=task.agent_id,
                data={
                    "reason": "application_shutdown",
                    "recoverable": True,
                    "previous_status": previous_status,
                },
            )
            await db.commit()
            logger.info(
                "task_requeued_after_shutdown task_id=%s previous_status=%s",
                task_id,
                previous_status,
            )

    async def fail(self, task_id: str, message: str, code: str) -> None:
        async with self.session_factory() as db:
            task = await TaskRepository(db).get(task_id, for_update=True)
            if task is None or task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                return
            if task.cancellation_requested:
                await self.mark_cancelled(
                    db,
                    task_id,
                    "任务在后台异常发生前已收到取消请求。",
                )
                return
            now = _utc_now()
            task.status = TaskStatus.FAILED
            task.error_message = message
            task.failure_category = code
            task.completed_at = now
            task.updated_at = now
            task.heartbeat_at = now
            task.execution_owner = None
            task.lease_expires_at = None
            audit = audit_from_task_input(task.input_content)
            metrics_data = None
            if audit:
                audit = audit_for_terminal(audit, TaskStatus.FAILED.value, code)
                task.input_content = replace_task_audit(task.input_content, audit)
                metrics_data = {"audit": audit}
            runtime_finalized = await self.runtime_boundary.finalize(
                db,
                task_id=task.id,
                status=RuntimeRunStatus.FAILED,
                provider=self.provider_name,
                latency_ms=(
                    elapsed_ms(task.started_at, now) if task.started_at else None
                ),
                error_code=code,
                terminal_reason=message,
                metrics_data=metrics_data,
            )
            if runtime_finalized is None:
                db.add(
                    AgentRunModel(
                        task_id=task.id,
                        agent_id=task.agent_id,
                        provider=self.provider_name,
                        status=TaskStatus.FAILED.value,
                        latency_ms=(
                            elapsed_ms(task.started_at, now)
                            if task.started_at
                            else None
                        ),
                        started_at=task.started_at,
                        completed_at=now,
                        metrics_data=metrics_data or {},
                    )
                )
            await append_task_event(
                db,
                task.id,
                AgentEventType.TASK_FAILED,
                agent_id=task.agent_id,
                data=terminal_event_data(
                    status=TaskStatus.FAILED.value,
                    failure_category=code,
                    error_code=code,
                    error_message=message,
                    runtime_run_id=(
                        str(getattr(runtime_finalized, "run_id", ""))
                        if runtime_finalized is not None
                        else str((audit or {}).get("runtime_run_id", ""))
                    ),
                ),
            )
            message_model = await ConversationMessageService(
                db
            ).append_terminal_failure(
                task,
                status=MessageStatus.FAILED,
                reason=message,
            )
            task.assistant_message_id = (
                message_model.id if message_model is not None else None
            )
            await self.cleanup_evaluation_attachments(db, task_id)
            await db.commit()
            logger.warning(
                "task_terminal_after_exception task_id=%s session_id=%s "
                "agent_id=%s provider=%s attempt=%s error_code=%s",
                task.id,
                task.session_id,
                task.agent_id,
                self.provider_name,
                task.attempt,
                code,
            )

    async def cleanup_evaluation_attachments(
        self,
        db: AsyncSession,
        task_id: str,
    ) -> None:
        try:
            async with db.begin_nested():
                await cleanup_evaluation_attachments(
                    db,
                    self.settings,
                    task_id=task_id,
                )
        except Exception:
            logger.warning(
                "evaluation_attachment_terminal_cleanup_failed task_id=%s",
                task_id,
                exc_info=True,
            )
