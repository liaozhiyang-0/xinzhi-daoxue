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

    async def receive(self, *, timeout_seconds: float) -> str | None:
        raise NotImplementedError

    async def ping(self) -> None:
        raise NotImplementedError

    async def reject(self, task_id: str, reason: str) -> None:
        """Reject a received task after a dispatch failure.

        Implementations may retry the task up to a configured attempt limit and
        then move it to a dead-letter queue. The database lease remains the
        durable source of truth, so a crash before this call is still recovered
        by the periodic DB recovery scan.
        """

        raise NotImplementedError

    async def ack(self, task_id: str) -> None:
        """Acknowledge a successful dispatch.

        This is not a business-result ack; the database task status is the only
        authoritative completion record. It clears transport-level attempt
        tracking so successful dispatches do not accumulate in monitoring.
        """

        raise NotImplementedError

    async def metrics(self) -> dict[str, int]:
        """Return transport-level metrics for monitoring.

        Keys are intentionally generic so callers do not depend on Redis list
        details: ``pending``, ``dead_letter``, and ``attempts``.
        """

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
        dead_letter_max_attempts: int = 3,
        dead_letter_enabled: bool = True,
    ) -> None:
        self.queue_name = queue_name
        self.worker_lock_name = f"{queue_name}:worker-lock"
        self.worker_lock_ttl_seconds = worker_lock_ttl_seconds
        self.dead_letter_name = f"{queue_name}:dead-letter"
        self.attempts_name = f"{queue_name}:attempts"
        self.dead_letter_max_attempts = max(1, dead_letter_max_attempts)
        self.dead_letter_enabled = dead_letter_enabled
        self._client: Any = Redis.from_url(redis_url, decode_responses=True)
        self._worker_lease_valid = False

    async def publish(self, task_id: str) -> None:
        await self._client.rpush(self.queue_name, task_id)

    async def receive(self, *, timeout_seconds: float) -> str | None:
        item = await self._client.blpop([self.queue_name], timeout=timeout_seconds)
        if item is None:
            return None
        _, task_id = item
        await self._client.hincrby(self.attempts_name, task_id, 1)
        return task_id

    async def reject(self, task_id: str, reason: str) -> None:
        """Requeue a task until the attempt limit, then dead-letter it.

        The database lease is still authoritative for crash recovery; this
        method only protects against poison dispatch messages that would
        otherwise bounce in a tight loop between the API and worker.
        """

        attempt = int(await self._client.hget(self.attempts_name, task_id) or 0)
        if not self.dead_letter_enabled or attempt < self.dead_letter_max_attempts:
            await self._client.lpush(self.queue_name, task_id)
            return
        await self._client.rpush(self.dead_letter_name, task_id)
        await self._client.hset(
            f"{self.attempts_name}:reasons",
            task_id,
            reason,
        )
        await self._client.hdel(self.attempts_name, task_id)
        logger.warning(
            "task_queue_dead_letter task_id=%s reason=%s attempts=%s",
            task_id,
            reason,
            attempt,
        )

    async def ack(self, task_id: str) -> None:
        await self._client.hdel(self.attempts_name, task_id)

    async def metrics(self) -> dict[str, int]:
        pending, dead_letter, attempts = await asyncio.gather(
            self._client.llen(self.queue_name),
            self._client.llen(self.dead_letter_name),
            self._client.hlen(self.attempts_name),
        )
        return {
            "pending": int(pending or 0),
            "dead_letter": int(dead_letter or 0),
            "attempts": int(attempts or 0),
        }

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

    def __init__(self, *, dead_letter_max_attempts: int = 3) -> None:
        self._items: asyncio.Queue[str] = asyncio.Queue()
        self.published: list[str] = []
        self.dead_letter: list[str] = []
        self.attempts: dict[str, int] = {}
        self.dead_letter_max_attempts = max(1, dead_letter_max_attempts)
        self.closed = False

    async def publish(self, task_id: str) -> None:
        if self.closed:
            raise RuntimeError("task queue is closed")
        self.published.append(task_id)
        await self._items.put(task_id)

    async def receive(self, *, timeout_seconds: float) -> str | None:
        if timeout_seconds <= 0:
            await asyncio.sleep(0)
            try:
                task_id = self._items.get_nowait()
            except asyncio.QueueEmpty:
                return None
        else:
            try:
                task_id = await asyncio.wait_for(self._items.get(), timeout_seconds)
            except TimeoutError:
                return None
        self.attempts[task_id] = self.attempts.get(task_id, 0) + 1
        return task_id

    async def ping(self) -> None:
        if self.closed:
            raise RuntimeError("task queue is closed")

    async def reject(self, task_id: str, reason: str) -> None:
        if self.closed:
            raise RuntimeError("task queue is closed")
        attempt = self.attempts.get(task_id, 0)
        if attempt < self.dead_letter_max_attempts:
            await self._items.put(task_id)
            return
        self.dead_letter.append(task_id)
        self.attempts.pop(task_id, None)

    async def ack(self, task_id: str) -> None:
        self.attempts.pop(task_id, None)

    async def metrics(self) -> dict[str, int]:
        return {
            "pending": self._items.qsize(),
            "dead_letter": len(self.dead_letter),
            "attempts": len(self.attempts),
        }

    @asynccontextmanager
    async def worker_lease(self) -> AsyncIterator[bool]:
        if self.closed:
            raise RuntimeError("task queue is closed")
        yield True

    async def close(self) -> None:
        self.closed = True
