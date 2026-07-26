from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse

from app.contracts import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSourceStatus,
    RAGSearchRequest,
    RetrievalResult,
)
from app.dependencies import get_knowledge_base, get_rag_retrieval
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_resources import (
    resolve_course_resource,
    resolve_kb_image_uri,
)
from app.services.rag_retrieval import RAGRetrievalService

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


@router.post("/rag-search", response_model=RetrievalResult)
async def rag_search(
    payload: RAGSearchRequest,
    request: Request,
    rag: RAGRetrievalService = Depends(get_rag_retrieval),
) -> RetrievalResult:
    if not payload.query_text and not payload.image_resource_uri:
        raise HTTPException(status_code=422, detail="query_text 与图片至少提供一项")
    image = None
    if payload.image_resource_uri:
        try:
            image = resolve_kb_image_uri(
                request.app.state.settings, payload.image_resource_uri
            )
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await asyncio.to_thread(
        rag.search,
        query_text=payload.query_text,
        query_image=image,
        course_id=payload.course_id.value,
        intent=payload.intent,
        target_agent_id=payload.target_agent_id,
        top_k=payload.top_k,
        content_types=tuple(payload.content_types),
        include_images=payload.include_images,
        use_reranker=payload.use_reranker,
    )


@router.get("/health", response_model=dict[str, Any])
async def rag_health(
    rag: RAGRetrievalService = Depends(get_rag_retrieval),
) -> dict[str, Any]:
    return await asyncio.to_thread(rag.health)


@router.get("/images/{course_id}/{relative_path:path}")
async def knowledge_image(
    course_id: str,
    relative_path: str,
    request: Request,
) -> FileResponse:
    try:
        target = resolve_course_resource(
            request.app.state.settings,
            course_id=course_id,
            relative_path=relative_path,
            image_only=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(target)


@router.get("/documents/{course_id}/{relative_path:path}")
async def knowledge_document(
    course_id: str,
    relative_path: str,
    request: Request,
) -> PlainTextResponse:
    try:
        target = resolve_course_resource(
            request.app.state.settings,
            course_id=course_id,
            relative_path=relative_path,
            text_only=True,
        )
        content = await asyncio.to_thread(target.read_text, encoding="utf-8")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, UnicodeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlainTextResponse(content, media_type="text/markdown; charset=utf-8")


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
