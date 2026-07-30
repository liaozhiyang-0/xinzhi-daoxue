from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse

from app.contracts import (
    KnowledgeDocumentPage,
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
from app.services.math_formatting_service import MathFormattingService
from app.services.rag_retrieval import RAGRetrievalService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
DOCUMENT_PAGE_CHARS = 24_000
DOCUMENT_PAGE_MAX_CHARS = 60_000


def _searchable_text(value: str) -> tuple[str, list[int]]:
    normalized: list[str] = []
    offsets: list[int] = []
    for index, character in enumerate(value):
        if character.isalnum():
            normalized.append(character.casefold())
            offsets.append(index)
    return "".join(normalized), offsets


def _find_anchor(document: str, anchor: str) -> int | None:
    if not anchor.strip():
        return None
    direct = document.find(anchor)
    if direct >= 0:
        return direct
    searchable_document, offsets = _searchable_text(document)
    searchable_anchor, _ = _searchable_text(anchor)
    if not searchable_anchor or not offsets:
        return None
    lengths = tuple(
        dict.fromkeys(
            min(len(searchable_anchor), value)
            for value in (360, 240, 160, 100, 60)
            if len(searchable_anchor) >= min(len(searchable_anchor), value)
        )
    )
    for length in lengths:
        if length < 30:
            continue
        matched = searchable_document.find(searchable_anchor[:length])
        if matched >= 0:
            return offsets[matched]
    return None


def _document_window(
    document: str,
    *,
    offset: int | None,
    limit: int,
    anchor: str,
) -> tuple[
    int,
    int,
    Literal["matched", "not_found", "not_requested"],
]:
    anchor_status: Literal["matched", "not_found", "not_requested"]
    anchor_offset = _find_anchor(document, anchor) if offset is None else None
    if anchor_offset is not None:
        start = max(0, anchor_offset - limit // 4)
        anchor_status = "matched"
    else:
        start = max(0, min(offset or 0, max(0, len(document) - 1)))
        anchor_status = (
            "not_found"
            if anchor.strip() and offset is None
            else "not_requested"
        )
    if start and offset is None:
        line_start = document.rfind("\n", max(0, start - 1000), start)
        if line_start >= 0:
            start = line_start + 1
    elif start:
        line_start = document.find("\n", start, min(len(document), start + 1000))
        if line_start >= 0:
            start = line_start + 1
    end = min(len(document), start + limit)
    if end < len(document):
        line_end = document.find("\n", end, min(len(document), end + 1000))
        if line_end >= 0:
            end = line_end
    return start, end, anchor_status


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
    normalize_math: bool = False,
    chunk: str = "",
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> PlainTextResponse:
    try:
        if chunk:
            if not chunk.startswith("chunk-") or not chunk.removeprefix(
                "chunk-"
            ).isdigit():
                raise ValueError("知识库片段编号无效")
            source_ref = f"kb://{course_id}/{relative_path}#{chunk}"
            content = await asyncio.to_thread(
                knowledge_base.source_content, source_ref
            )
            if content is None:
                raise FileNotFoundError("知识库片段不存在")
        else:
            target = resolve_course_resource(
                request.app.state.settings,
                course_id=course_id,
                relative_path=relative_path,
                text_only=True,
            )
            content = await asyncio.to_thread(target.read_text, encoding="utf-8")
        if normalize_math:
            content = await asyncio.to_thread(
                lambda: MathFormattingService().process_markdown(content).markdown
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, UnicodeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlainTextResponse(content, media_type="text/markdown; charset=utf-8")


@router.get(
    "/document-pages/{course_id}/{relative_path:path}",
    response_model=KnowledgeDocumentPage,
)
async def knowledge_document_page(
    course_id: str,
    relative_path: str,
    request: Request,
    offset: int | None = Query(default=None, ge=0),
    limit: int = Query(
        default=DOCUMENT_PAGE_CHARS,
        ge=4000,
        le=DOCUMENT_PAGE_MAX_CHARS,
    ),
    anchor: str = Query(default="", max_length=2000),
    chunk: str = Query(default="", max_length=64),
    normalize_math: bool = True,
) -> KnowledgeDocumentPage:
    try:
        if chunk and (
            not chunk.startswith("chunk-")
            or not chunk.removeprefix("chunk-").isdigit()
        ):
            raise ValueError("知识库片段编号无效")
        target = resolve_course_resource(
            request.app.state.settings,
            course_id=course_id,
            relative_path=relative_path,
            text_only=True,
        )
        document = await asyncio.to_thread(target.read_text, encoding="utf-8")
        start, end, anchor_status = await asyncio.to_thread(
            _document_window,
            document,
            offset=offset,
            limit=limit,
            anchor=anchor,
        )
        content = document[start:end]
        if normalize_math:
            content = await asyncio.to_thread(
                lambda: MathFormattingService().process_markdown(content).markdown
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, UnicodeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    source_ref = f"kb://{course_id}/{relative_path}"
    if chunk:
        source_ref += f"#{chunk}"
    return KnowledgeDocumentPage(
        source_ref=source_ref,
        course_id=course_id,
        relative_path=relative_path,
        requested_chunk=chunk,
        content=content,
        total_chars=len(document),
        start_offset=start,
        end_offset=end,
        previous_offset=max(0, start - limit - 1000) if start > 0 else None,
        next_offset=end if end < len(document) else None,
        anchor_status=anchor_status,
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
