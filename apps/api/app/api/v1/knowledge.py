from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.contracts import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSourceStatus,
    RetrievalResult,
)
from app.dependencies import get_knowledge_base
from app.services.knowledge_base import KnowledgeBaseService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/sources", response_model=list[KnowledgeSourceStatus])
async def list_sources(
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> list[KnowledgeSourceStatus]:
    return await asyncio.to_thread(knowledge_base.source_statuses)


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    payload: KnowledgeSearchRequest,
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> KnowledgeSearchResponse:
    hits = await asyncio.to_thread(
        knowledge_base.search,
        payload.query,
        list(payload.course_ids),
        payload.top_k,
    )
    sources = await asyncio.to_thread(knowledge_base.source_statuses)
    return KnowledgeSearchResponse(query=payload.query, hits=hits, sources=sources)


@router.post("/evaluate-query", response_model=RetrievalResult)
async def evaluate_query(
    payload: KnowledgeSearchRequest,
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> RetrievalResult:
    return await asyncio.to_thread(
        knowledge_base.search_result,
        payload.query,
        list(payload.course_ids),
        payload.top_k,
    )


@router.get("/benchmark-summary", response_model=dict[str, Any])
async def benchmark_summary(request: Request) -> dict[str, Any]:
    root = Path(request.app.state.settings.knowledge_config_path).parent
    results = root / "evaluation" / "knowledge_retrieval" / "results"
    runs: dict[str, Any] = {}
    for run_id in ("baseline_lexical_v1", "local_lexical_v2"):
        path = results / f"{run_id}.json"
        if not path.is_file():
            runs[run_id] = {"available": False}
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            runs[run_id] = {"available": False, "warning": "结果文件不可读"}
            continue
        runs[run_id] = {
            "available": True,
            "generated_at": payload.get("generated_at"),
            "case_count": payload.get("case_count"),
            "case_status": payload.get("case_status"),
            "metrics": payload.get("metrics", {}),
        }
    return {"benchmark_status": "draft", "human_review_required": True, "runs": runs}


@router.post("/reload", response_model=list[KnowledgeSourceStatus])
async def reload_knowledge(
    request: Request,
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> list[KnowledgeSourceStatus]:
    if request.app.state.settings.app_env == "production":
        return await asyncio.to_thread(knowledge_base.source_statuses)
    return await asyncio.to_thread(knowledge_base.refresh)
