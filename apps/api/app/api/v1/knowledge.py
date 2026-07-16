from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request

from app.contracts import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSourceStatus,
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


@router.post("/reload", response_model=list[KnowledgeSourceStatus])
async def reload_knowledge(
    request: Request,
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> list[KnowledgeSourceStatus]:
    if request.app.state.settings.app_env == "production":
        return await asyncio.to_thread(knowledge_base.source_statuses)
    return await asyncio.to_thread(knowledge_base.refresh)
