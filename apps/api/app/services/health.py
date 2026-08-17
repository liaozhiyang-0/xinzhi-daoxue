from __future__ import annotations

import asyncio
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts.api import HealthRead
from app.core.config import Settings
from app.providers.base import AgentProvider
from app.providers.retrieval.academic import AcademicSearchService


async def _database_status(
    session_factory: async_sessionmaker[AsyncSession],
) -> str:
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "unavailable"


async def _redis_status(url: str) -> str:
    client = Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
    try:
        await client.ping()
        return "ok"
    except Exception:
        return "unavailable"
    finally:
        await client.aclose()


async def _minio_status(endpoint: str) -> str:
    try:
        host, port_text = endpoint.rsplit(":", 1)
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, int(port_text)), timeout=0.5
        )
        writer.close()
        await writer.wait_closed()
        return "ok"
    except Exception:
        return "unavailable"


async def build_health(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    provider: AgentProvider,
    external_search: AcademicSearchService | None = None,
    task_queue: Any | None = None,
) -> HealthRead:
    database, redis, minio = await asyncio.gather(
        _database_status(session_factory),
        _redis_status(settings.redis_url),
        _minio_status(settings.minio_endpoint),
    )
    provider_mode = "local_runtime" if provider.provider_name == "local" else "mock"
    task_queue_metrics: dict[str, Any] = {}
    if task_queue is not None:
        try:
            task_queue_metrics = await task_queue.metrics()
            task_queue_metrics["mode"] = settings.task_executor_mode
        except Exception:
            task_queue_metrics = {
                "mode": settings.task_executor_mode,
                "error": "unavailable",
            }
    return HealthRead(
        status=(
            "ok" if database == "ok" and redis == "ok" and minio == "ok" else "degraded"
        ),
        environment=settings.app_env,
        database=database,
        redis=redis,
        minio=minio,
        requested_provider=settings.default_agent_provider,
        active_provider=provider.provider_name,
        provider_mode=provider_mode,
        version=settings.app_version,
        external_retrieval=(
            external_search.health() if external_search is not None else {}
        ),
        task_queue=task_queue_metrics,
    )
