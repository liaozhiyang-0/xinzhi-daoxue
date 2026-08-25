from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import require_admin

router = APIRouter(
    prefix="/debug/traces", tags=["development"], dependencies=[Depends(require_admin)]
)


@router.get("/{trace_id}", response_model=dict[str, Any])
async def get_trace(trace_id: str, request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    if not settings.enable_debug_api or settings.app_env == "production":
        raise HTTPException(status_code=404, detail="Debug Trace API 未启用")
    record = request.app.state.trace_store.get(trace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Trace 不存在或已过期")
    from app.observability import TraceProjectionService

    projection = TraceProjectionService(
        request.app.state.trace_store,
        request.app.state.model_tracer,
    ).project(trace_id)
    return {**record, "projection": projection}
