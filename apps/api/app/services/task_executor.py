from __future__ import annotations

from typing import Protocol

from app.services.task_runner import TaskRunner


class TaskExecutor(Protocol):
    """Stable dispatch boundary for local execution or a future queue worker."""

    def submit(self, task_id: str) -> bool: ...

    async def shutdown(self) -> None: ...


class LocalTaskExecutor:
    def __init__(self, runner: TaskRunner) -> None:
        self.runner = runner

    def submit(self, task_id: str) -> bool:
        return self.runner.submit(task_id)

    async def shutdown(self) -> None:
        await self.runner.shutdown()


class QueueTaskExecutor:
    """Explicit extension point; it never silently falls back to local execution."""

    def submit(self, task_id: str) -> bool:
        raise RuntimeError("QueueTaskExecutor 尚未配置消息队列后端")

    async def shutdown(self) -> None:
        return None
