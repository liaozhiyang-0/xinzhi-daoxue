from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.analytics import AnalyticsQuery, AnalyticsReportRead
from app.dependencies import get_current_principal, get_db, require_admin_account
from app.services.analytics import AnalyticsService
from app.services.auth_service import Principal

router = APIRouter(prefix="/analytics", tags=["analytics"])


def analytics_query(
    window_start: datetime | None = Query(default=None, alias="from"),
    window_end: datetime | None = Query(default=None, alias="to"),
    timezone: str = Query(default="UTC", max_length=64),
    course: str | None = Query(default=None, max_length=32),
    role: str | None = Query(default=None, max_length=32),
    intent: str | None = Query(default=None, max_length=64),
    capability: str | None = Query(default=None, max_length=160),
    skill: str | None = Query(default=None, max_length=160),
    tool: str | None = Query(default=None, max_length=160),
    scenario: str | None = Query(default=None, max_length=128),
    provider: str | None = Query(default=None, max_length=64),
    model: str | None = Query(default=None, max_length=128),
    task_id: str | None = Query(default=None, max_length=64),
    pilot_batch: str | None = Query(default=None, max_length=128),
    row_limit: int = Query(default=20_000, ge=100, le=20_000),
) -> AnalyticsQuery:
    end = window_end or datetime.now(UTC)
    start = window_start or end - timedelta(days=30)
    return AnalyticsQuery(
        window_start=start,
        window_end=end,
        timezone=timezone,
        course=course,
        role=role,
        intent=intent,
        capability=capability,
        skill=skill,
        tool=tool,
        scenario=scenario,
        provider=provider,
        model=model,
        task_id=task_id,
        pilot_batch=pilot_batch,
        row_limit=row_limit,
    )


async def _report(
    kind: str, query: AnalyticsQuery, db: AsyncSession
) -> AnalyticsReportRead:
    return await AnalyticsService(db).report(kind, query)


@router.get(
    "/overview",
    response_model=AnalyticsReportRead,
    dependencies=[Depends(require_admin_account)],
)
async def overview(
    query: AnalyticsQuery = Depends(analytics_query), db: AsyncSession = Depends(get_db)
) -> AnalyticsReportRead:
    return await _report("overview", query, db)


@router.get(
    "/users",
    response_model=AnalyticsReportRead,
    dependencies=[Depends(require_admin_account)],
)
async def users(
    query: AnalyticsQuery = Depends(analytics_query), db: AsyncSession = Depends(get_db)
) -> AnalyticsReportRead:
    return await _report("users", query, db)


@router.get(
    "/sessions",
    response_model=AnalyticsReportRead,
    dependencies=[Depends(require_admin_account)],
)
async def sessions(
    query: AnalyticsQuery = Depends(analytics_query), db: AsyncSession = Depends(get_db)
) -> AnalyticsReportRead:
    return await _report("sessions", query, db)


@router.get(
    "/tasks",
    response_model=AnalyticsReportRead,
    dependencies=[Depends(require_admin_account)],
)
async def tasks(
    query: AnalyticsQuery = Depends(analytics_query), db: AsyncSession = Depends(get_db)
) -> AnalyticsReportRead:
    return await _report("tasks", query, db)


@router.get(
    "/answers",
    response_model=AnalyticsReportRead,
    dependencies=[Depends(require_admin_account)],
)
async def answers(
    query: AnalyticsQuery = Depends(analytics_query), db: AsyncSession = Depends(get_db)
) -> AnalyticsReportRead:
    return await _report("answers", query, db)


@router.get(
    "/agentic",
    response_model=AnalyticsReportRead,
    dependencies=[Depends(require_admin_account)],
)
async def agentic(
    query: AnalyticsQuery = Depends(analytics_query), db: AsyncSession = Depends(get_db)
) -> AnalyticsReportRead:
    return await _report("agentic", query, db)


@router.get(
    "/performance",
    response_model=AnalyticsReportRead,
    dependencies=[Depends(require_admin_account)],
)
async def performance(
    query: AnalyticsQuery = Depends(analytics_query), db: AsyncSession = Depends(get_db)
) -> AnalyticsReportRead:
    return await _report("performance", query, db)


@router.get(
    "/courses",
    response_model=AnalyticsReportRead,
    dependencies=[Depends(require_admin_account)],
)
async def courses(
    query: AnalyticsQuery = Depends(analytics_query), db: AsyncSession = Depends(get_db)
) -> AnalyticsReportRead:
    return await _report("courses", query, db)


@router.get("/teacher", response_model=AnalyticsReportRead)
async def teacher_analytics(
    query: AnalyticsQuery = Depends(analytics_query),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsReportRead:
    if not principal.authenticated:
        raise HTTPException(status_code=401, detail="请先登录")
    if principal.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="需要教师或管理员权限")
    return await _report("teacher", query, db)
