from __future__ import annotations

from typing import Protocol

from app.services.task_queue import TaskQueue
from app.services.task_runner import TaskRunner


class TaskExecutor(Protocol):
    """Stable dispatch boundary for local execution or a queue worker."""

    async def submit(self, task_id: str) -> bool: ...

    async def recover(self) -> int: ...

    async def shutdown(self) -> None: ...


class LocalTaskExecutor:
    def __init__(self, runner: TaskRunner) -> None:
        self.runner = runner

    async def submit(self, task_id: str) -> bool:
        return self.runner.submit(task_id)

    async def recover(self) -> int:
        return await self.runner.recover_pending_tasks()

    async def shutdown(self) -> None:
        await self.runner.shutdown()


class QueueTaskExecutor:
    """API-side executor that only publishes task IDs for an external worker."""

    def __init__(self, queue: TaskQueue) -> None:
        self.queue = queue

    async def submit(self, task_id: str) -> bool:
        await self.queue.publish(task_id)
        return True

    async def recover(self) -> int:
        # Recovery is owned by the worker because it has the TaskRunner and
        # can claim database leases before dispatching. The API still pings
        # Redis here so a misconfigured queue fails during startup, not on the
        # first user request.
        await self.queue.ping()
        return 0

    async def shutdown(self) -> None:
        await self.queue.close()
