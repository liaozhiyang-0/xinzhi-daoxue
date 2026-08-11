from __future__ import annotations

import asyncio
import logging

from app.services.task_queue import TaskQueue
from app.services.task_runner import TaskRunner

logger = logging.getLogger(__name__)


class TaskWorker:
    """Consume task IDs and execute them through the shared TaskRunner."""

    def __init__(
        self,
        runner: TaskRunner,
        queue: TaskQueue,
        *,
        block_timeout_seconds: int,
        recovery_interval_seconds: int,
    ) -> None:
        self.runner = runner
        self.queue = queue
        self.block_timeout_seconds = block_timeout_seconds
        self.recovery_interval_seconds = recovery_interval_seconds

    async def run(self, *, stop_event: asyncio.Event | None = None) -> None:
        stop_event = stop_event or asyncio.Event()
        async with self.queue.worker_lease() as acquired:
            if not acquired:
                raise RuntimeError(
                    "another task worker already owns the Redis worker lease"
                )
            logger.info("task_worker_started")
            await self.runner.recover_pending_tasks()
            recovery_task = asyncio.create_task(
                self._recovery_loop(stop_event),
                name="xzd-task-worker-recovery",
            )
            try:
                while not stop_event.is_set():
                    task_id = await self.queue.receive(
                        timeout_seconds=self.block_timeout_seconds
                    )
                    if not self.queue.worker_lease_valid:
                        raise RuntimeError("task worker Redis lease was lost")
                    if task_id is None:
                        continue
                    accepted = self.runner.submit(task_id)
                    logger.info(
                        "task_worker_dispatched task_id=%s accepted=%s",
                        task_id,
                        accepted,
                    )
            finally:
                recovery_task.cancel()
                await asyncio.gather(recovery_task, return_exceptions=True)

    async def _recovery_loop(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                recovered = await self.runner.recover_pending_tasks()
                if recovered:
                    logger.info("task_worker_recovered count=%s", recovered)
            except Exception:
                logger.exception("task_worker_recovery_failed")
            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=self.recovery_interval_seconds
                )
            except TimeoutError:
                continue
