from __future__ import annotations

from typing import Protocol


class TaskExecutionEngine(Protocol):
    """Business execution boundary used by the task coordinator.

    Scheduling, recovery, and process shutdown belong to the coordinator.
    Implementations only execute one claimed task and close resources owned by
    the business execution pipeline.
    """

    execution_owner: str

    async def execute(self, task_id: str) -> None: ...

    def prepare_shutdown(self) -> None: ...

    async def shutdown(self) -> None: ...

