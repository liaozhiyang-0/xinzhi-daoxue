from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import PracticeAttemptModel, RetestPlanModel


class LearningRecordRepository:
    """User-scoped persistence for attempt versions and delayed retests."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def attempt_by_id(
        self, attempt_id: str, user_id: str
    ) -> PracticeAttemptModel | None:
        return await self.session.scalar(
            select(PracticeAttemptModel).where(
                PracticeAttemptModel.id == attempt_id,
                PracticeAttemptModel.user_id == user_id,
            )
        )

    async def attempt_by_idempotency(
        self, user_id: str, idempotency_key: str
    ) -> PracticeAttemptModel | None:
        return await self.session.scalar(
            select(PracticeAttemptModel).where(
                PracticeAttemptModel.user_id == user_id,
                PracticeAttemptModel.idempotency_key == idempotency_key,
            )
        )

    async def latest_attempt(
        self, source_task_id: str, user_id: str
    ) -> PracticeAttemptModel | None:
        return await self.session.scalar(
            select(PracticeAttemptModel)
            .where(
                PracticeAttemptModel.source_task_id == source_task_id,
                PracticeAttemptModel.user_id == user_id,
                PracticeAttemptModel.attempt_sequence.is_not(None),
            )
            .order_by(PracticeAttemptModel.attempt_sequence.desc())
            .limit(1)
        )

    async def list_attempts(
        self,
        user_id: str,
        *,
        source_task_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[PracticeAttemptModel]:
        statement: Select[tuple[PracticeAttemptModel]] = select(
            PracticeAttemptModel
        ).where(
            PracticeAttemptModel.user_id == user_id,
            PracticeAttemptModel.attempt_sequence.is_not(None),
        )
        if source_task_id:
            statement = statement.where(
                PracticeAttemptModel.source_task_id == source_task_id
            )
        statement = (
            statement.order_by(PracticeAttemptModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    async def retest_by_id(
        self, retest_plan_id: str, user_id: str
    ) -> RetestPlanModel | None:
        return await self.session.scalar(
            select(RetestPlanModel).where(
                RetestPlanModel.id == retest_plan_id,
                RetestPlanModel.user_id == user_id,
            )
        )

    async def existing_retest(
        self,
        *,
        user_id: str,
        skill_id: str,
        source_task_id: str,
        interval_days: int,
    ) -> RetestPlanModel | None:
        return await self.session.scalar(
            select(RetestPlanModel).where(
                RetestPlanModel.user_id == user_id,
                RetestPlanModel.skill_id == skill_id,
                RetestPlanModel.source_task_id == source_task_id,
                RetestPlanModel.interval_days == interval_days,
            )
        )

    async def list_retests(
        self,
        user_id: str,
        *,
        status: str | None = None,
        now: datetime,
        offset: int = 0,
        limit: int = 50,
    ) -> list[RetestPlanModel]:
        statement: Select[tuple[RetestPlanModel]] = select(RetestPlanModel).where(
            RetestPlanModel.user_id == user_id
        )
        if status == "due":
            statement = statement.where(
                RetestPlanModel.due_at <= now,
                RetestPlanModel.status.in_(("scheduled", "due")),
            )
        elif status:
            statement = statement.where(RetestPlanModel.status == status)
        else:
            statement = statement.where(
                or_(
                    RetestPlanModel.status != "superseded",
                    RetestPlanModel.status.is_(None),
                )
            )
        statement = (
            statement.order_by(RetestPlanModel.due_at).offset(offset).limit(limit)
        )
        return list((await self.session.scalars(statement)).all())
