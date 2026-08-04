from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings
from app.models import FileModel, TaskModel, TaskStatus
from app.services.evaluation_attachment_cleanup import (
    EVALUATION_ATTACHMENT_PURPOSE,
    cleanup_evaluation_attachments,
)

TERMINAL_TASK_STATUSES = (
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
)


@dataclass(frozen=True)
class EvaluationAttachmentResidueReport:
    as_of: datetime
    grace_seconds: int
    cutoff: datetime
    total_file_count: int
    total_bytes: int
    unbound_file_count: int
    active_task_file_count: int
    terminal_task_file_count: int
    missing_task_file_count: int
    cleanup_candidate_count: int
    cleanup_candidate_bytes: int
    oldest_created_at: datetime | None


def _task_join():
    return FileModel.task_id == TaskModel.id


def _candidate_filter(cutoff: datetime):
    task_is_terminal = TaskModel.status.in_(TERMINAL_TASK_STATUSES)
    task_is_missing = and_(
        FileModel.task_id.is_not(None),
        TaskModel.id.is_(None),
    )
    return and_(
        FileModel.created_at <= cutoff,
        or_(
            FileModel.task_id.is_(None),
            task_is_terminal,
            task_is_missing,
        ),
    )


def _active_task_file_filter():
    return and_(
        FileModel.task_id.is_not(None),
        TaskModel.id.is_not(None),
        TaskModel.status.not_in(TERMINAL_TASK_STATUSES),
    )


async def inspect_evaluation_attachment_residue(
    db: AsyncSession,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> EvaluationAttachmentResidueReport:
    """Report controlled evaluation files without mutating storage or the DB."""

    as_of = now or datetime.now(UTC)
    grace_seconds = settings.evaluation_attachment_cleanup_grace_seconds
    cutoff = as_of - timedelta(seconds=grace_seconds)
    base = FileModel.purpose == EVALUATION_ATTACHMENT_PURPOSE

    async def count(*conditions: ColumnElement[bool]) -> int:
        statement = (
            select(func.count(FileModel.id))
            .select_from(FileModel)
            .outerjoin(TaskModel, _task_join())
            .where(base, *conditions)
        )
        return int(await db.scalar(statement) or 0)

    async def total_bytes(*conditions: ColumnElement[bool]) -> int:
        statement = (
            select(func.coalesce(func.sum(FileModel.size_bytes), 0))
            .select_from(FileModel)
            .outerjoin(TaskModel, _task_join())
            .where(base, *conditions)
        )
        return int(await db.scalar(statement) or 0)

    candidate = _candidate_filter(cutoff)
    oldest = await db.scalar(
        select(func.min(FileModel.created_at)).where(base)
    )
    return EvaluationAttachmentResidueReport(
        as_of=as_of,
        grace_seconds=grace_seconds,
        cutoff=cutoff,
        total_file_count=await count(),
        total_bytes=await total_bytes(),
        unbound_file_count=await count(FileModel.task_id.is_(None)),
        active_task_file_count=await count(_active_task_file_filter()),
        terminal_task_file_count=await count(
            TaskModel.status.in_(TERMINAL_TASK_STATUSES)
        ),
        missing_task_file_count=await count(
            and_(FileModel.task_id.is_not(None), TaskModel.id.is_(None))
        ),
        cleanup_candidate_count=await count(candidate),
        cleanup_candidate_bytes=await total_bytes(candidate),
        oldest_created_at=oldest,
    )


async def cleanup_stale_evaluation_attachments(
    db: AsyncSession,
    settings: Settings,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    """Delete one bounded batch of candidates; callers own the commit."""

    if limit < 1:
        return 0
    as_of = now or datetime.now(UTC)
    cutoff = as_of - timedelta(
        seconds=settings.evaluation_attachment_cleanup_grace_seconds
    )
    statement = (
        select(FileModel.id)
        .select_from(FileModel)
        .outerjoin(TaskModel, _task_join())
        .where(
            FileModel.purpose == EVALUATION_ATTACHMENT_PURPOSE,
            _candidate_filter(cutoff),
        )
        .order_by(FileModel.created_at.asc(), FileModel.id.asc())
        .limit(limit)
    )
    file_ids = list((await db.scalars(statement)).all())
    if not file_ids:
        return 0
    return await cleanup_evaluation_attachments(
        db,
        settings,
        file_ids=file_ids,
    )
