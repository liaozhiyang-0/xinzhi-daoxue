from __future__ import annotations

import asyncio

from app.application.tasks.contracts import TaskExecutionEngine
from app.application.tasks.leases import TaskLeaseManager
from app.core.config import Settings


class TaskExecutionCoordinator:
    """Own task dispatch, bounded concurrency, recovery, and shutdown.

    The coordinator deliberately knows nothing about Agent routing, RAG,
    providers, Runtime plans, fallback policy, or result presentation. Those
    are business execution concerns behind ``TaskExecutionEngine``.
    """

    def __init__(
        self,
        settings: Settings,
        engine: TaskExecutionEngine,
        leases: TaskLeaseManager,
    ) -> None:
        self.settings = settings
        self.engine = engine
        self.leases = leases
        self.execution_owner = leases.execution_owner
        self._capacity = asyncio.Semaphore(settings.task_max_concurrency)
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._deferred_submissions: set[str] = set()
        self._shutting_down = False

    def submit(self, task_id: str) -> bool:
        if self._shutting_down:
            return False
        existing = self._tasks.get(task_id)
        if existing is not None and not existing.done():
            self._deferred_submissions.add(task_id)
            return False
        background = asyncio.create_task(
            self._execute_bounded(task_id),
            name=f"xzd-task-{task_id}",
        )
        self._tasks[task_id] = background
        background.add_done_callback(
            lambda completed: self._on_task_finished(task_id, completed)
        )
        return True

    async def recover(self) -> int:
        """Claim and dispatch queued tasks or tasks with expired leases."""

        task_ids = await self.leases.recover()
        for task_id in task_ids:
            self.submit(task_id)
        return len(task_ids)

    async def shutdown(self) -> None:
        self._shutting_down = True
        self.engine.prepare_shutdown()
        active = [task for task in self._tasks.values() if not task.done()]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        self._tasks.clear()
        self._deferred_submissions.clear()
        await self.engine.shutdown()

    async def _execute_bounded(self, task_id: str) -> None:
        async with self._capacity:
            await self.engine.execute(task_id)

    def _on_task_finished(
        self,
        task_id: str,
        completed: asyncio.Task[None],
    ) -> None:
        if self._tasks.get(task_id) is completed:
            self._tasks.pop(task_id, None)
        if self._shutting_down:
            self._deferred_submissions.discard(task_id)
            return
        if task_id not in self._deferred_submissions:
            return
        self._deferred_submissions.remove(task_id)
        self.submit(task_id)
