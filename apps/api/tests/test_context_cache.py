from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.services.context_cache import ContextAssemblyCache


class _FakeRedis:
    def __init__(self, keys: set[str]) -> None:
        self.keys = keys

    async def scan_iter(self, *, match: str) -> AsyncIterator[str]:
        prefix = match.removesuffix("*")
        for key in list(self.keys):
            if key.startswith(prefix):
                yield key

    async def delete(self, key: str) -> None:
        self.keys.discard(key)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_invalidate_session_connects_to_redis_from_unknown_state(
    settings,
) -> None:
    cache = ContextAssemblyCache(settings)
    fake = _FakeRedis({"xzd:context:session-1:cached"})
    cache._redis = fake  # type: ignore[assignment]

    await cache.invalidate_session("session-1")

    assert fake.keys == set()
    assert cache._redis_available is True
    await cache.close()
