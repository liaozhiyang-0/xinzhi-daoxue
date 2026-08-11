from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest
from app.services.task_queue import InMemoryTaskQueue
from app.services.task_worker import TaskWorker


@pytest.mark.asyncio
async def test_worker_dispatches_queue_ids_to_runner() -> None:
    queue = InMemoryTaskQueue()
    stop_event = asyncio.Event()
    submitted: list[str] = []
    recovery_calls = 0

    class Runner:
        async def recover_pending_tasks(self) -> int:
            nonlocal recovery_calls
            recovery_calls += 1
            return 0

        def submit(self, task_id: str) -> bool:
            submitted.append(task_id)
            stop_event.set()
            return True

    await queue.publish("task-123")
    worker = TaskWorker(
        Runner(),  # type: ignore[arg-type]
        queue,
        block_timeout_seconds=1,
        recovery_interval_seconds=5,
    )

    await asyncio.wait_for(worker.run(stop_event=stop_event), timeout=2)

    assert submitted == ["task-123"]
    assert recovery_calls >= 1


@pytest.mark.asyncio
async def test_worker_refuses_a_second_owner() -> None:
    class UnavailableQueue(InMemoryTaskQueue):
        @asynccontextmanager
        async def worker_lease(self):
            yield False

    class Runner:
        async def recover_pending_tasks(self) -> int:
            return 0

        def submit(self, task_id: str) -> bool:
            return True

    worker = TaskWorker(
        Runner(),  # type: ignore[arg-type]
        UnavailableQueue(),
        block_timeout_seconds=1,
        recovery_interval_seconds=5,
    )

    with pytest.raises(RuntimeError, match="already owns"):
        await worker.run(stop_event=asyncio.Event())
