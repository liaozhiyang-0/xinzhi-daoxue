from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.learning import (
    LearnerKnowledgeState,
    LearningActionRequest,
    LearningActionResponse,
    LearningMetricsRead,
    LearningRuntimeApprovalRequest,
    RetestPlanV1,
    StudentAttemptV2,
)
from app.dependencies import effective_user_id, get_current_principal, get_db
from app.services.auth_service import Principal
from app.services.learning_loop import LearningLoopService
from app.services.learning_metrics import LearningMetricsService

router = APIRouter(prefix="/learning", tags=["learning"])


def _require_metrics_manager(request: Request, principal: Principal) -> None:
    if not request.app.state.settings.auth_required:
        return
    if not principal.authenticated or principal.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="需要教师或管理员权限")


@router.post("/actions", response_model=LearningActionResponse)
async def learning_action(
    data: LearningActionRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> LearningActionResponse:
    data = data.model_copy(
        update={"user_id": effective_user_id(principal, data.user_id)}
    )
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.act(db, data)


@router.post(
    "/runtime/{run_id}/approve",
    response_model=LearningActionResponse,
    summary="Approve a teaching interaction Runtime run",
)
async def approve_learning_runtime(
    run_id: str,
    data: LearningRuntimeApprovalRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> LearningActionResponse:
    user_id = effective_user_id(principal, None)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.approve_runtime_interaction(
        db,
        run_id,
        user_id=user_id,
        expected_state_version=data.expected_state_version,
    )


@router.get("/states", response_model=list[LearnerKnowledgeState])
async def learning_states(
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    principal: Principal = Depends(get_current_principal),
    course_id: str | None = Query(default=None, max_length=32),
    db: AsyncSession = Depends(get_db),
) -> list[LearnerKnowledgeState]:
    user_id = effective_user_id(principal, user_id)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.list_states(db, user_id, course_id)


@router.get("/attempts", response_model=list[StudentAttemptV2])
async def learning_attempts(
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    principal: Principal = Depends(get_current_principal),
    source_task_id: str | None = Query(default=None, max_length=64),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[StudentAttemptV2]:
    user_id = effective_user_id(principal, user_id)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.attempts.list(
        db,
        user_id=user_id,
        source_task_id=source_task_id,
        offset=offset,
        limit=limit,
    )


@router.get("/attempts/{attempt_id}", response_model=StudentAttemptV2)
async def learning_attempt(
    attempt_id: str,
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> StudentAttemptV2:
    user_id = effective_user_id(principal, user_id)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.attempts.get(db, attempt_id=attempt_id, user_id=user_id)


@router.get("/retests", response_model=list[RetestPlanV1])
async def learning_retests(
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    principal: Principal = Depends(get_current_principal),
    status: str | None = Query(
        default=None,
        pattern="^(scheduled|due|completed|cancelled|superseded)$",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[RetestPlanV1]:
    user_id = effective_user_id(principal, user_id)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.retests.list(
        db,
        user_id=user_id,
        status=status,
        offset=offset,
        limit=limit,
    )


@router.get("/metrics", response_model=LearningMetricsRead)
async def learning_metrics(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    course_id: str | None = Query(default=None, max_length=32),
    window_start: datetime | None = Query(default=None),
    window_end: datetime | None = Query(default=None),
    row_limit: int = Query(
        default=LearningMetricsService.DEFAULT_ROW_LIMIT, ge=1, le=20_000
    ),
    db: AsyncSession = Depends(get_db),
) -> LearningMetricsRead:
    _require_metrics_manager(request, principal)
    end = window_end or datetime.now(UTC)
    start = window_start or end - timedelta(days=30)
    if start >= end:
        raise HTTPException(
            status_code=422, detail="window_start must be before window_end"
        )
    return await LearningMetricsService().aggregate(
        db,
        course_id=course_id,
        window_start=start,
        window_end=end,
        row_limit=row_limit,
    )
