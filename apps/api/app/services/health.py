from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts.api import HealthRead
from app.core.config import Settings
from app.providers.base import AgentProvider
from app.providers.retrieval.academic import AcademicSearchService
from app.services.model_service import ModelService


def _file_digest(path: Path) -> str:
    """Return a short, non-secret identity for the loaded configuration file."""

    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return "unavailable"


def _runtime_identity(settings: Settings) -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    return {
        "app_version": settings.app_version,
        "agent_registry_sha256": _file_digest(root / "agent_configs" / "registry.yaml"),
        "scenario_catalog_sha256": _file_digest(
            root / "config" / "scenarios.yaml"
        ),
        "solver_ct_baseline": "SOLVER_CT_v1.0_frozen",
    }


def _configuration_warnings(
    settings: Settings, provider: AgentProvider, model_runtime: dict[str, Any]
) -> list[str]:
    warnings: list[str] = []
    if settings.app_env == "production" and provider.provider_name == "mock":
        warnings.append("production_active_provider_mock")
    if settings.app_env == "production" and settings.allow_mock_fallback:
        warnings.append("production_mock_fallback_enabled")
    if provider.provider_name == "mock":
        warnings.append("active_agent_provider_mock")
    if not model_runtime.get("real_provider_configured", False):
        warnings.append("model_provider_unconfigured")
    return warnings


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
    model_service: ModelService | None = None,
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
    model_runtime = (
        model_service.configuration_snapshot()
        if model_service is not None
        else {"status": "unknown", "real_provider_configured": False}
    )
    configuration_warnings = _configuration_warnings(
        settings, provider, model_runtime
    )
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
        runtime_identity=_runtime_identity(settings),
        configuration_status=(
            "degraded" if configuration_warnings else "ready"
        ),
        configuration_warnings=configuration_warnings,
        model_runtime=model_runtime,
        external_retrieval=(
            external_search.health() if external_search is not None else {}
        ),
        task_queue=task_queue_metrics,
    )
