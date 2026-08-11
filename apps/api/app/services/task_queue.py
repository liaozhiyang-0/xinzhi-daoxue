from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class TaskQueue:
    """Durable task-id transport used between the API and a worker process."""

    async def publish(self, task_id: str) -> None:
        raise NotImplementedError

    async def receive(self, *, timeout_seconds: int) -> str | None:
        raise NotImplementedError

    async def ping(self) -> None:
        raise NotImplementedError

    @asynccontextmanager
    async def worker_lease(self) -> AsyncIterator[bool]:
        raise NotImplementedError
        yield False

    async def close(self) -> None:
        raise NotImplementedError

    @property
    def worker_lease_valid(self) -> bool:
        return True


class RedisTaskQueue(TaskQueue):
    """At-least-once Redis list transport with a renewable worker lease.

    The database task lease remains the source of truth. A Redis message is
    only a dispatch hint, so a worker crash cannot permanently lose a task:
    startup and periodic database recovery re-enqueue expired work.
    """

    _REFRESH_LOCK_SCRIPT = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end"
    )
    _RELEASE_LOCK_SCRIPT = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) else return 0 end"
    )

    def __init__(
        self,
        redis_url: str,
        *,
        queue_name: str,
        worker_lock_ttl_seconds: int,
    ) -> None:
        self.queue_name = queue_name
        self.worker_lock_name = f"{queue_name}:worker-lock"
        self.worker_lock_ttl_seconds = worker_lock_ttl_seconds
        self._client: Any = Redis.from_url(redis_url, decode_responses=True)
        self._worker_lease_valid = False

    async def publish(self, task_id: str) -> None:
        await self._client.rpush(self.queue_name, task_id)

    async def receive(self, *, timeout_seconds: int) -> str | None:
        item = await self._client.blpop([self.queue_name], timeout=timeout_seconds)
        if item is None:
            return None
        _, task_id = item
        return task_id

    async def ping(self) -> None:
        await self._client.ping()

    async def acquire_worker_lease(self) -> str | None:
        token = uuid4().hex
        acquired = await self._client.set(
            self.worker_lock_name,
            token,
            nx=True,
            ex=self.worker_lock_ttl_seconds,
        )
        self._worker_lease_valid = bool(acquired)
        return token if acquired else None

    @property
    def worker_lease_valid(self) -> bool:
        return self._worker_lease_valid

    async def refresh_worker_lease(self, token: str) -> bool:
        result = await self._client.eval(
            self._REFRESH_LOCK_SCRIPT,
            1,
            self.worker_lock_name,
            token,
            str(self.worker_lock_ttl_seconds),
        )
        self._worker_lease_valid = bool(result)
        return self._worker_lease_valid

    async def release_worker_lease(self, token: str) -> None:
        self._worker_lease_valid = False
        await self._client.eval(
            self._RELEASE_LOCK_SCRIPT,
            1,
            self.worker_lock_name,
            token,
        )

    @asynccontextmanager
    async def worker_lease(self) -> AsyncIterator[bool]:
        token = await self.acquire_worker_lease()
        if token is None:
            yield False
            return
        refresh_task = asyncio.create_task(
            self._refresh_worker_lease_loop(token),
            name="xzd-worker-lease-refresh",
        )
        try:
            yield True
        finally:
            refresh_task.cancel()
            await asyncio.gather(refresh_task, return_exceptions=True)
            await self.release_worker_lease(token)

    async def _refresh_worker_lease_loop(self, token: str) -> None:
        interval = max(1, self.worker_lock_ttl_seconds // 3)
        while True:
            await asyncio.sleep(interval)
            if not await self.refresh_worker_lease(token):
                logger.error("task_worker_lease_lost")
                return

    async def close(self) -> None:
        self._worker_lease_valid = False
        await self._client.aclose()


class InMemoryTaskQueue(TaskQueue):
    """Deterministic queue for unit tests; never used by production settings."""

    def __init__(self) -> None:
        self._items: asyncio.Queue[str] = asyncio.Queue()
        self.published: list[str] = []
        self.closed = False

    async def publish(self, task_id: str) -> None:
        if self.closed:
            raise RuntimeError("task queue is closed")
        self.published.append(task_id)
        await self._items.put(task_id)

    async def receive(self, *, timeout_seconds: int) -> str | None:
        try:
            return await asyncio.wait_for(self._items.get(), timeout_seconds)
        except TimeoutError:
            return None

    async def ping(self) -> None:
        if self.closed:
            raise RuntimeError("task queue is closed")

    @asynccontextmanager
    async def worker_lease(self) -> AsyncIterator[bool]:
        if self.closed:
            raise RuntimeError("task queue is closed")
        yield True

    async def close(self) -> None:
        self.closed = True
