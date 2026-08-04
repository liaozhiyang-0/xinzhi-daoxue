from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.feedback import (
    FeedbackCreate,
    FeedbackFeatureStatusRead,
    FeedbackMetricsRead,
    FeedbackRead,
)
from app.dependencies import effective_user_id, get_current_principal, get_db
from app.models import AgentRunModel, TaskFeedbackModel, TaskModel, TaskStatus
from app.services.auth_service import Principal
from app.services.feature_flags import FEEDBACK_LOOP_FEATURE, is_feature_enabled
from app.services.task_observability import (
    first_value as _first_value,
)
from app.services.task_observability import (
    result_sources as _result_sources,
)
from app.services.task_observability import (
    task_latency_ms as _task_latency_ms,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])
DEFAULT_ROW_LIMIT = 2_000


async def _ensure_feedback_enabled(
    request: Request, db: AsyncSession
) -> None:
    if not await is_feature_enabled(db, FEEDBACK_LOOP_FEATURE):
        raise HTTPException(status_code=409, detail="反馈闭环当前已关闭")


@router.get("/status", response_model=FeedbackFeatureStatusRead)
async def feedback_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> FeedbackFeatureStatusRead:
    return FeedbackFeatureStatusRead(
        enabled=await is_feature_enabled(db, FEEDBACK_LOOP_FEATURE)
    )


def _require_metrics_manager(request: Request, principal: Principal) -> None:
    if not request.app.state.settings.auth_required:
        return
    if not principal.authenticated or principal.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="teacher or admin access required")


def _bounded_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if 0 <= result <= 1 else None


def _task_snapshot(task: TaskModel, run: AgentRunModel | None) -> dict[str, Any]:
    sources = _result_sources(task)
    return {
        "agent_id": task.agent_id,
        "agent_version": run.agent_version if run is not None else None,
        "provider": task.provider or (run.provider if run is not None else "unknown"),
        "model_version": _first_value(
            sources, ("model_version", "model_name", "model")
        ),
        "rag_version": _first_value(
            sources, ("rag_version", "index_version", "retrieval_index_version")
        ),
        "retrieval_mode": _first_value(
            sources, ("retrieval_mode", "rag_mode", "mode")
        ),
        "citation_coverage": _bounded_float(
            _first_value(
                sources,
                ("citation_coverage", "citation_coverage_rate", "citation_valid_rate"),
            )
        ),
        "latency_ms": (
            run.latency_ms
            if run is not None and run.latency_ms is not None
            else _task_latency_ms(task)
        ),
    }


async def _latest_agent_run(
    db: AsyncSession, task_id: str
) -> AgentRunModel | None:
    return await db.scalar(
        select(AgentRunModel)
        .where(AgentRunModel.task_id == task_id)
        .order_by(AgentRunModel.created_at.desc())
        .limit(1)
    )


def _feedback_read(item: TaskFeedbackModel) -> FeedbackRead:
    return FeedbackRead.model_validate(item)


@router.post("", response_model=FeedbackRead)
async def submit_feedback(
    payload: FeedbackCreate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> FeedbackRead:
    await _ensure_feedback_enabled(request, db)
    task = await db.get(TaskModel, payload.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    user_id = effective_user_id(principal, task.user_id)
    if task.user_id != user_id:
        raise HTTPException(status_code=404, detail="task not found")
    terminal_statuses = {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }
    if task.status not in terminal_statuses:
        raise HTTPException(status_code=409, detail="feedback requires a terminal task")

    run = await _latest_agent_run(db, task.id)
    snapshot = _task_snapshot(task, run)
    role = principal.role if principal.has_identity and principal.role else "student"
    item = await db.scalar(
        select(TaskFeedbackModel).where(
            TaskFeedbackModel.task_id == task.id,
            TaskFeedbackModel.user_id == user_id,
        )
    )
    if item is None:
        item = TaskFeedbackModel(
            task_id=task.id,
            user_id=user_id,
            user_role=role,
            course_id=task.course_id,
            task_type=task.intent,
            agent_id=str(snapshot["agent_id"] or "unknown"),
            agent_version=snapshot["agent_version"],
            provider=str(snapshot["provider"] or "unknown"),
            model_version=(
                str(snapshot["model_version"])
                if snapshot["model_version"] is not None
                else None
            ),
            rag_version=(
                str(snapshot["rag_version"])
                if snapshot["rag_version"] is not None
                else None
            ),
            retrieval_mode=(
                str(snapshot["retrieval_mode"])
                if snapshot["retrieval_mode"] is not None
                else None
            ),
        )
        db.add(item)
    else:
        item.user_role = role
        item.course_id = task.course_id
        item.task_type = task.intent
        item.agent_id = str(snapshot["agent_id"] or "unknown")
        item.agent_version = snapshot["agent_version"]
        item.provider = str(snapshot["provider"] or "unknown")
        item.model_version = (
            str(snapshot["model_version"])
            if snapshot["model_version"] is not None
            else None
        )
        item.rag_version = (
            str(snapshot["rag_version"])
            if snapshot["rag_version"] is not None
            else None
        )
        item.retrieval_mode = (
            str(snapshot["retrieval_mode"])
            if snapshot["retrieval_mode"] is not None
            else None
        )
    item.resolved = payload.resolved
    item.satisfaction = (
        payload.satisfaction.value if payload.satisfaction is not None else None
    )
    item.problem_type = payload.problem_type
    item.manual_review_required = payload.manual_review_required
    item.citation_coverage = snapshot["citation_coverage"]
    item.latency_ms = snapshot["latency_ms"]
    item.comment = payload.comment or None
    await db.commit()
    await db.refresh(item)
    return _feedback_read(item)


@router.get("/metrics", response_model=FeedbackMetricsRead)
async def feedback_metrics(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    course_id: str | None = Query(default=None, max_length=32),
    window_start: datetime | None = Query(default=None),
    window_end: datetime | None = Query(default=None),
    row_limit: int = Query(default=DEFAULT_ROW_LIMIT, ge=1, le=20_000),
    db: AsyncSession = Depends(get_db),
) -> FeedbackMetricsRead:
    await _ensure_feedback_enabled(request, db)
    _require_metrics_manager(request, principal)
    end = window_end or datetime.now(UTC)
    start = window_start or end - timedelta(days=30)
    if start >= end:
        raise HTTPException(
            status_code=422, detail="window_start must be before window_end"
        )

    task_query = select(TaskModel).where(
        TaskModel.created_at >= start,
        TaskModel.created_at < end,
    )
    feedback_query = select(TaskFeedbackModel).where(
        TaskFeedbackModel.created_at >= start,
        TaskFeedbackModel.created_at < end,
    )
    if course_id:
        normalized_course = course_id.strip()
        task_query = task_query.where(TaskModel.course_id == normalized_course)
        feedback_query = feedback_query.where(
            TaskFeedbackModel.course_id == normalized_course
        )
    tasks = list((await db.scalars(task_query.limit(row_limit + 1))).all())
    feedback = list((await db.scalars(feedback_query.limit(row_limit + 1))).all())
    truncated = len(tasks) > row_limit or len(feedback) > row_limit
    tasks = tasks[:row_limit]
    feedback = feedback[:row_limit]

    status_counts: Counter[str] = Counter()
    user_task_counts: Counter[str] = Counter()
    latencies: list[int] = []
    for task in tasks:
        status = (
            task.status.value
            if isinstance(task.status, TaskStatus)
            else str(task.status)
        )
        status_counts[status] += 1
        user_task_counts[task.user_id] += 1
        latency = _task_latency_ms(task)
        if latency is not None:
            latencies.append(latency)
    completed_count = status_counts[TaskStatus.COMPLETED.value]
    failed_count = status_counts[TaskStatus.FAILED.value]
    terminal_count = sum(
        status_counts[status] for status in ("completed", "failed", "cancelled")
    )
    unique_user_count = len(user_task_counts)
    repeat_user_count = sum(1 for count in user_task_counts.values() if count > 1)

    satisfaction_counts: Counter[str] = Counter()
    problem_type_counts: Counter[str] = Counter()
    user_role_counts: Counter[str] = Counter()
    task_type_counts: Counter[str] = Counter()
    resolved_values: list[bool] = []
    citation_values: list[float] = []
    manual_review_count = 0
    for item in feedback:
        if item.satisfaction:
            satisfaction_counts[item.satisfaction] += 1
        if item.problem_type:
            problem_type_counts[item.problem_type] += 1
        user_role_counts[item.user_role] += 1
        task_type_counts[item.task_type] += 1
        if item.resolved is not None:
            resolved_values.append(item.resolved)
        if item.manual_review_required:
            manual_review_count += 1
        if item.citation_coverage is not None:
            citation_values.append(item.citation_coverage)

    warnings: list[str] = []
    if truncated:
        warnings.append("feedback_metrics_reached_row_limit")
    if feedback and not citation_values:
        warnings.append("citation_coverage_unavailable_in_feedback_snapshots")
    if feedback and not resolved_values:
        warnings.append("resolved_feedback_not_provided")
    return FeedbackMetricsRead(
        course_id=course_id,
        window_start=start,
        window_end=end,
        task_count=len(tasks),
        task_status_counts=dict(status_counts),
        completed_task_count=completed_count,
        failed_task_count=failed_count,
        task_completion_rate=(
            completed_count / terminal_count if terminal_count else None
        ),
        average_latency_ms=sum(latencies) / len(latencies) if latencies else None,
        unique_user_count=unique_user_count,
        repeat_user_rate=(
            repeat_user_count / unique_user_count if unique_user_count else None
        ),
        feedback_count=len(feedback),
        feedback_response_rate=(
            len(feedback) / terminal_count if terminal_count else None
        ),
        satisfaction_counts=dict(satisfaction_counts),
        resolved_count=sum(1 for value in resolved_values if value),
        resolved_rate=(
            sum(1 for value in resolved_values if value) / len(resolved_values)
            if resolved_values
            else None
        ),
        manual_review_request_count=manual_review_count,
        problem_type_counts=dict(problem_type_counts),
        user_role_counts=dict(user_role_counts),
        task_type_counts=dict(task_type_counts),
        average_citation_coverage=(
            sum(citation_values) / len(citation_values) if citation_values else None
        ),
        row_limit=row_limit,
        truncated=truncated,
        data_quality_warnings=warnings,
    )
