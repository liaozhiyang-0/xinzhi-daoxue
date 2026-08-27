from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI

from app.application.container import ApplicationContainer
from app.database.base import Base
from app.services.context_cache import ContextAssemblyCache
from app.services.external_retrieval import ExternalContentFetcher
from app.services.knowledge_base import KnowledgeBaseService
from app.services.model_service import ModelService
from app.services.production_execution_manifest import (
    ExecutionSurfaceError,
)
from app.services.rag_retrieval import RAGRetrievalService
from app.services.research_knowledge import ResearchKnowledgeService
from app.services.task_executor import TaskExecutor

logger = logging.getLogger(__name__)
QWEN_WARMUP_PROMPT = "只回复 OK"


@dataclass(frozen=True, slots=True)
class ApplicationLifecycleResources:
    settings: Any
    engine: Any
    session_factory: Any
    container: ApplicationContainer
    task_executor: TaskExecutor
    context_cache: ContextAssemblyCache
    external_search: Any
    external_fetcher: ExternalContentFetcher
    provider: Any
    model_service: ModelService
    rag_retrieval: RAGRetrievalService
    research_knowledge: ResearchKnowledgeService


def build_app_lifespan(
    resources: ApplicationLifecycleResources,
) -> Callable[[FastAPI], Any]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resources.container.install(app)
        _execution_surface_preflight(resources.container)

        research_maintenance_task: asyncio.Task[None] | None = None
        deferred_startup_task: asyncio.Task[None] | None = None
        qwen_warmup_task: asyncio.Task[None] | None = None
        if resources.settings.app_env == "test":
            async with resources.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            app.state.rag_warmup = {
                "status": "skipped",
                "reason": "test_environment_or_disabled",
            }
            app.state.qwen_warmup = {
                "status": "skipped",
                "reason": "test_environment",
            }
            await _recover_tasks(resources.task_executor)
        else:
            app.state.rag_warmup = {
                "status": "deferred",
                "reason": "fast_startup",
            }
            app.state.qwen_warmup = {
                "status": "deferred",
                "reason": "fast_startup",
            }

            if (
                resources.settings.knowledge_enabled
                and resources.settings.knowledge_warmup_on_startup
            ):
                await _warm_knowledge_base(
                    app,
                    resources.container.knowledge_base,
                )

            async def deferred_startup() -> None:
                nonlocal qwen_warmup_task, research_maintenance_task
                await asyncio.sleep(0)
                qwen_warmup_task = asyncio.create_task(
                    _warm_qwen(
                        app,
                        resources.model_service,
                        resources.settings,
                    ),
                    name="xzd-qwen-model-warmup",
                )
                if resources.settings.research_knowledge_maintenance_enabled:
                    try:
                        await resources.research_knowledge.maintain()
                    except Exception:
                        logger.exception(
                            "research_knowledge_initial_maintenance_failed"
                        )
                    research_maintenance_task = asyncio.create_task(
                        _research_maintenance_loop(
                            resources.research_knowledge,
                            resources.settings
                            .research_knowledge_maintenance_interval_seconds,
                        ),
                        name="xzd-research-knowledge-maintenance",
                    )
                if (
                    resources.settings.rag_enabled
                    and resources.settings.rag_warmup_on_startup
                ):
                    await _warm_rag(app, resources.rag_retrieval)
                await _recover_tasks(resources.task_executor)

            deferred_startup_task = asyncio.create_task(
                deferred_startup(),
                name="xzd-deferred-startup",
            )
        try:
            yield
        finally:
            await _cancel_task(deferred_startup_task)
            await _cancel_task(qwen_warmup_task)
            await _cancel_task(research_maintenance_task)
            await resources.task_executor.shutdown()
            await resources.context_cache.close()
            await resources.external_search.close()
            await resources.external_fetcher.close()
            close_provider = getattr(resources.provider, "aclose", None)
            if close_provider is not None:
                await close_provider()
            await resources.model_service.aclose()
            resources.rag_retrieval.close()
            await resources.engine.dispose()

    return lifespan


async def _research_maintenance_loop(
    research_knowledge: ResearchKnowledgeService,
    interval_seconds: int,
) -> None:
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await research_knowledge.maintain()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("research_knowledge_maintenance_failed")


async def _recover_tasks(task_executor: TaskExecutor) -> None:
    try:
        recovered_tasks = await task_executor.recover()
    except Exception:
        logger.exception("task_recovery_startup_failed")
        return
    if recovered_tasks:
        logger.info("task_recovery_requeued count=%s", recovered_tasks)


async def _warm_rag(app: FastAPI, rag_retrieval: RAGRetrievalService) -> None:
    logger.info("rag_model_warmup_started_deferred")
    try:
        warmup = await asyncio.to_thread(rag_retrieval.warmup)
        app.state.rag_warmup = warmup
        logger.info(
            "rag_model_warmup_completed status=%s elapsed_ms=%s failed=%s",
            warmup["status"],
            warmup["elapsed_ms"],
            warmup["failed_components"],
        )
    except Exception:
        logger.exception("rag_model_warmup_failed_deferred")
        app.state.rag_warmup = {
            "status": "failed",
            "reason": "deferred_warmup_error",
        }


async def _warm_knowledge_base(
    app: FastAPI,
    knowledge_base: KnowledgeBaseService,
) -> None:
    """Load the lexical index before production requests can race the scan."""

    logger.info("knowledge_base_warmup_started")
    started = asyncio.get_running_loop().time()
    try:
        statuses = await asyncio.to_thread(knowledge_base.refresh)
        app.state.knowledge_warmup = {
            "status": "ready",
            "elapsed_ms": int(
                (asyncio.get_running_loop().time() - started) * 1000
            ),
            "document_count": sum(item.document_count for item in statuses),
            "chunk_count": sum(item.chunk_count for item in statuses),
        }
        logger.info(
            "knowledge_base_warmup_completed elapsed_ms=%s documents=%s chunks=%s",
            app.state.knowledge_warmup["elapsed_ms"],
            app.state.knowledge_warmup["document_count"],
            app.state.knowledge_warmup["chunk_count"],
        )
    except Exception:
        logger.exception("knowledge_base_warmup_failed")
        app.state.knowledge_warmup = {
            "status": "failed",
            "reason": "startup_warmup_error",
        }


async def _warm_qwen(app: FastAPI, model_service: ModelService, settings: Any) -> None:
    if not settings.qwen_warmup_enabled:
        app.state.qwen_warmup = {
            "status": "skipped",
            "reason": "disabled",
        }
        return

    preflight = model_service.preflight("general_question_answer", modality="text")
    if "qwen_text_fast" not in preflight.usable_aliases:
        app.state.qwen_warmup = {
            "status": "skipped",
            "reason": "qwen_text_fast_unavailable",
        }
        return

    logger.info("qwen_model_warmup_started_deferred model_alias=qwen_text_fast")
    try:
        response = await asyncio.wait_for(
            model_service.generate_for_task(
                "general_question_answer",
                messages=[{"role": "user", "content": QWEN_WARMUP_PROMPT}],
                request_id="startup_qwen_warmup",
                extra_options={
                    "max_tokens": 4,
                    "temperature": 0,
                    "response_depth": "standard",
                    "_allow_route_fallback": False,
                },
            ),
            timeout=float(settings.qwen_warmup_timeout_seconds),
        )
        app.state.qwen_warmup = {
            "status": "completed",
            "model": response.model,
            "elapsed_ms": response.elapsed_ms,
        }
        logger.info(
            "qwen_model_warmup_completed model=%s elapsed_ms=%s",
            response.model,
            response.elapsed_ms,
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("qwen_model_warmup_failed_deferred")
        app.state.qwen_warmup = {
            "status": "failed",
            "reason": "deferred_warmup_error",
        }


async def _cancel_task(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def _execution_surface_preflight(container: ApplicationContainer) -> None:
    """Reject a bootstrap that could drift into a second execution surface."""

    manifest = getattr(container, "production_manifest", None)
    if manifest is None:
        raise ExecutionSurfaceError("PRODUCTION_MANIFEST_MISSING")
    manifest.validate_bootstrap()
    if not getattr(container.runtime_handler_registry, "frozen", False):
        raise ExecutionSurfaceError("RUNTIME_HANDLER_REGISTRY_NOT_FROZEN")
    if not getattr(container.runtime_subagent_registry, "frozen", False):
        raise ExecutionSurfaceError("RUNTIME_SUBAGENT_REGISTRY_NOT_FROZEN")
    if not getattr(container.tool_registry, "frozen", False):
        raise ExecutionSurfaceError("TOOL_REGISTRY_NOT_FROZEN")
    if container.planner.manifest is not manifest:
        raise ExecutionSurfaceError("PLANNER_MANIFEST_NOT_BOUND")
    if container.task_engine.runtime_boundary.manifest is not manifest:
        raise ExecutionSurfaceError("RUNTIME_MANIFEST_NOT_BOUND")
    if container.task_engine.preparation.manifest is not manifest:
        raise ExecutionSurfaceError("PREPARATION_MANIFEST_NOT_BOUND")
    logger.info(
        "PRODUCTION_EXECUTION_FINGERPRINT fingerprint=%s build_id=%s "
        "runtime_generation=%s planner_version=%s active_handler_hash=%s "
        "active_capability_hash=%s active_tool_hash=%s",
        manifest.fingerprint,
        manifest.build_id,
        manifest.runtime_generation,
        manifest.planner_version,
        manifest.active_handler_hash,
        manifest.active_capability_hash,
        manifest.active_tool_hash,
    )
