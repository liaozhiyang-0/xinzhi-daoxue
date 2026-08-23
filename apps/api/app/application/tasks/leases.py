from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts import AgentEventType
from app.core.config import Settings
from app.models import TaskModel, TaskStatus
from app.repositories import TaskRepository
from app.services.event_service import append_task_event

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskLeaseManager:
    """Own database lease acquisition, recovery, and heartbeat renewal."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        *,
        execution_owner: str | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.execution_owner = execution_owner or f"local-{uuid4().hex[:12]}"

    def can_start(self, task: TaskModel, now: datetime) -> bool:
        return not (
            task.execution_owner is not None
            and task.execution_owner != self.execution_owner
            and task.lease_expires_at is not None
            and task.lease_expires_at > now
        )

    async def mark_running(
        self,
        db: AsyncSession,
        task: TaskModel,
        *,
        started_at: datetime,
        active_provider: str,
    ) -> None:
        task.status = TaskStatus.RUNNING
        task.started_at = started_at
        task.updated_at = started_at
        task.execution_owner = self.execution_owner
        task.heartbeat_at = started_at
        task.lease_expires_at = started_at + timedelta(
            seconds=self.settings.task_lease_seconds
        )
        await append_task_event(
            db,
            task.id,
            AgentEventType.TASK_RUNNING,
            agent_id=task.agent_id,
            data={"attempt": task.attempt},
        )
        await append_task_event(
            db,
            task.id,
            AgentEventType.AGENT_STARTED,
            agent_id=task.agent_id,
            data={"provider": active_provider},
        )

    async def heartbeat(self, task_id: str) -> None:
        lease_seconds = self.settings.task_lease_seconds
        interval = max(5.0, min(30.0, lease_seconds / 3))
        while True:
            await asyncio.sleep(interval)
            now = _utc_now()
            async with self.session_factory() as db:
                task = await TaskRepository(db).get(task_id, for_update=True)
                if (
                    task is None
                    or task.status != TaskStatus.RUNNING
                    or task.execution_owner != self.execution_owner
                ):
                    return
                task.heartbeat_at = now
                task.lease_expires_at = now + timedelta(seconds=lease_seconds)
                task.updated_at = now
                await db.commit()

    async def recover(self) -> list[str]:
        recovery = asyncio.create_task(
            self._recover_once(),
            name="xzd-task-lease-recovery",
        )
        try:
            return await asyncio.shield(recovery)
        except asyncio.CancelledError:
            # Let an in-flight aiosqlite connect/close finish before the
            # lifespan tears down the event loop.
            await recovery
            raise

    async def _recover_once(self) -> list[str]:
        if not self.settings.task_recovery_enabled:
            return []
        now = _utc_now()
        task_ids: list[str] = []
        async with self.session_factory() as db:
            repository = TaskRepository(db)
            try:
                tasks = await repository.list_recoverable(now, for_update=True)
            except OperationalError as exc:
                message = str(exc).casefold()
                if "no such table" not in message and "does not exist" not in message:
                    raise
                await db.rollback()
                logger.warning(
                    "task_recovery_skipped_database_unavailable error_type=%s",
                    type(exc).__name__,
                )
                return []

            lease_expires_at = now + timedelta(
                seconds=self.settings.task_lease_seconds
            )
            for task in tasks:
                previous_status = task.status.value
                was_running = task.status == TaskStatus.RUNNING
                if was_running:
                    task.status = TaskStatus.QUEUED
                task.execution_owner = self.execution_owner
                task.heartbeat_at = now
                task.lease_expires_at = lease_expires_at
                task.updated_at = now
                if was_running:
                    await append_task_event(
                        db,
                        task.id,
                        AgentEventType.TASK_QUEUED,
                        agent_id=task.agent_id,
                        data={
                            "recovered": True,
                            "previous_status": previous_status,
                        },
                    )
                task_ids.append(task.id)
            await db.commit()
        return task_ids
