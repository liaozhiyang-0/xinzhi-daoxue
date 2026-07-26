from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.learning import (
    LearnerKnowledgeState,
    LearningActionRequest,
    LearningActionResponse,
)
from app.dependencies import get_db
from app.services.learning_loop import LearningLoopService

router = APIRouter(prefix="/learning", tags=["learning"])


@router.post("/actions", response_model=LearningActionResponse)
async def learning_action(
    data: LearningActionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LearningActionResponse:
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.act(db, data)


@router.get("/states", response_model=list[LearnerKnowledgeState])
async def learning_states(
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    course_id: str | None = Query(default=None, max_length=32),
    db: AsyncSession = Depends(get_db),
) -> list[LearnerKnowledgeState]:
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.list_states(db, user_id, course_id)
