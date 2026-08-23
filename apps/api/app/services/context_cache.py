from __future__ import annotations

import asyncio
import json
from collections import OrderedDict
from time import monotonic
from typing import Any

from redis.asyncio import Redis

from app.contracts.conversation import ConversationContextBundle
from app.core.config import Settings


class ContextAssemblyCache:
    """Redis-first cache with a bounded in-process fallback."""

    def __init__(self, settings: Settings) -> None:
        self.ttl = settings.context_cache_ttl_seconds
        self.max_entries = settings.context_cache_max_entries
        self._memory: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.05,
            socket_timeout=0.05,
        )
        self._redis_available: bool | None = None

    async def get(
        self, key: str
    ) -> tuple[ConversationContextBundle | None, str]:
        if self._redis_available is not False:
            try:
                raw = await asyncio.wait_for(self._redis.get(key), timeout=0.1)
                self._redis_available = True
                if raw:
                    return ConversationContextBundle.model_validate_json(raw), "redis"
            except Exception:
                self._redis_available = False
        cached = self._memory.get(key)
        if cached is None:
            return None, "memory"
        expires_at, raw = cached
        if expires_at <= monotonic():
            self._memory.pop(key, None)
            return None, "memory"
        self._memory.move_to_end(key)
        return ConversationContextBundle.model_validate_json(raw), "memory"

    async def set(self, key: str, bundle: ConversationContextBundle) -> str:
        raw = bundle.model_dump_json()
        if self._redis_available is not False:
            try:
                await asyncio.wait_for(
                    self._redis.set(key, raw, ex=self.ttl), timeout=0.1
                )
                self._redis_available = True
                return "redis"
            except Exception:
                self._redis_available = False
        self._memory[key] = (monotonic() + self.ttl, raw)
        self._memory.move_to_end(key)
        while len(self._memory) > self.max_entries:
            self._memory.popitem(last=False)
        return "memory"

    async def invalidate_session(self, session_id: str) -> None:
        marker = f":{session_id}:"
        for key in [item for item in self._memory if marker in item]:
            self._memory.pop(key, None)
        if self._redis_available is not False:
            try:
                pattern = f"xzd:context:{session_id}:*"
                async for key in self._redis.scan_iter(match=pattern):
                    await self._redis.delete(key)
                self._redis_available = True
            except Exception:
                self._redis_available = False

    @staticmethod
    def key(parts: dict[str, Any]) -> str:
        stable = json.dumps(
            parts, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        return f"xzd:context:{parts['session_id']}:{stable}"

    async def close(self) -> None:
        await self._redis.aclose()
