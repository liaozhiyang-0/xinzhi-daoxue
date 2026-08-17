from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.observability.metrics import (
    build_observability_snapshot,
    prometheus_text,
)
from app.observability.model_tracer import ModelTracer
from app.observability.tracer import TraceStore
from app.services.task_queue import TaskQueue

router = APIRouter(prefix="/observability", tags=["observability"])


def _resources(request: Request) -> tuple[Any, Any, Any, Any, Any]:
    settings = request.app.state.settings
    session_factory: async_sessionmaker[AsyncSession] = (
        request.app.state.session_factory
    )
    trace_store: TraceStore = request.app.state.trace_store
    model_tracer: ModelTracer = request.app.state.model_tracer
    task_queue: TaskQueue | None = getattr(request.app.state, "task_queue", None)
    return settings, session_factory, trace_store, model_tracer, task_queue


@router.get("/summary")
async def observability_summary(request: Request) -> JSONResponse:
    settings, session_factory, trace_store, model_tracer, task_queue = _resources(
        request
    )
    snapshot = await build_observability_snapshot(
        session_factory=session_factory,
        trace_store=trace_store,
        model_tracer=model_tracer,
        task_queue=task_queue,
        task_executor_mode=settings.task_executor_mode,
    )
    return JSONResponse(snapshot)


@router.get("/metrics")
async def observability_metrics(request: Request) -> PlainTextResponse:
    settings, session_factory, trace_store, model_tracer, task_queue = _resources(
        request
    )
    snapshot = await build_observability_snapshot(
        session_factory=session_factory,
        trace_store=trace_store,
        model_tracer=model_tracer,
        task_queue=task_queue,
        task_executor_mode=settings.task_executor_mode,
    )
    return PlainTextResponse(
        prometheus_text(snapshot),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
