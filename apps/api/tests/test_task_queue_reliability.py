from __future__ import annotations

import asyncio

from app.services.task_queue import InMemoryTaskQueue
from app.services.task_worker import TaskWorker


async def test_in_memory_queue_rejects_until_dead_letter() -> None:
    queue = InMemoryTaskQueue(dead_letter_max_attempts=2)

    await queue.publish("task-1")
    assert await queue.receive(timeout_seconds=0) == "task-1"
    assert await queue.metrics() == {"pending": 0, "dead_letter": 0, "attempts": 1}

    # First rejection is requeued because the attempt limit is 2.
    await queue.reject("task-1", "dispatch_rejected")
    assert await queue.receive(timeout_seconds=0) == "task-1"
    assert await queue.metrics() == {"pending": 0, "dead_letter": 0, "attempts": 2}

    # Second rejection moves the task to the dead-letter list.
    await queue.reject("task-1", "dispatch_rejected")
    assert await queue.metrics() == {"pending": 0, "dead_letter": 1, "attempts": 0}


async def test_in_memory_queue_ack_clears_attempts() -> None:
    queue = InMemoryTaskQueue(dead_letter_max_attempts=2)

    await queue.publish("task-1")
    assert await queue.receive(timeout_seconds=0) == "task-1"
    assert await queue.metrics()["attempts"] == 1

    await queue.ack("task-1")
    assert await queue.metrics() == {"pending": 0, "dead_letter": 0, "attempts": 0}


class RejectingDispatcher:
    async def submit(self, task_id: str) -> bool:
        return False

    async def recover(self) -> int:
        return 0


class RaisingDispatcher:
    async def submit(self, task_id: str) -> bool:
        raise RuntimeError("boom")

    async def recover(self) -> int:
        return 0


async def test_task_worker_acks_rejected_dispatch() -> None:
    queue = InMemoryTaskQueue(dead_letter_max_attempts=2)
    worker = TaskWorker(
        RejectingDispatcher(),
        queue,
        block_timeout_seconds=0,
        recovery_interval_seconds=60,
    )
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(worker.run(stop_event=stop_event))

    try:
        await queue.publish("task-rejected")
        for _ in range(50):
            metrics = await queue.metrics()
            if metrics["attempts"] == 0 and metrics["pending"] == 0:
                break
            await asyncio.sleep(0.01)
        assert await queue.metrics() == {"pending": 0, "dead_letter": 0, "attempts": 0}
    finally:
        stop_event.set()
        await asyncio.wait_for(worker_task, timeout=2)


async def test_task_worker_dead_letters_dispatch_exception() -> None:
    queue = InMemoryTaskQueue(dead_letter_max_attempts=2)
    worker = TaskWorker(
        RaisingDispatcher(),
        queue,
        block_timeout_seconds=0,
        recovery_interval_seconds=60,
    )
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(worker.run(stop_event=stop_event))

    try:
        await queue.publish("task-error")
        for _ in range(50):
            metrics = await queue.metrics()
            if metrics["dead_letter"] == 1:
                break
            await asyncio.sleep(0.01)
        assert await queue.metrics() == {"pending": 0, "dead_letter": 1, "attempts": 0}
    finally:
        stop_event.set()
        await asyncio.wait_for(worker_task, timeout=2)
