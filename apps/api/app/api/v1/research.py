from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.dependencies import get_current_principal
from app.services.auth_service import Principal
from app.services.research_knowledge import ResearchKnowledgeService

router = APIRouter(prefix="/research", tags=["research"])


class ResearchKnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=8, ge=1, le=30)


def get_research_knowledge(request: Request) -> ResearchKnowledgeService:
    return cast(ResearchKnowledgeService, request.app.state.research_knowledge)


@router.get("/knowledge/status")
async def research_knowledge_status(
    service: ResearchKnowledgeService = Depends(get_research_knowledge),
) -> dict[str, Any]:
    return await service.status()


@router.post("/knowledge/search")
async def research_knowledge_search(
    payload: ResearchKnowledgeSearchRequest,
    service: ResearchKnowledgeService = Depends(get_research_knowledge),
) -> dict[str, Any]:
    hits = await service.search(payload.query, limit=payload.limit)
    return {
        "query": payload.query,
        "hits": [
            {"evidence_id": hit.item_id, "score": hit.score, **hit.payload}
            for hit in hits
        ],
    }


@router.post("/knowledge/maintain")
async def maintain_research_knowledge(
    service: ResearchKnowledgeService = Depends(get_research_knowledge),
    _principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    return await service.maintain()

