from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExperienceRecordModel


class ExperienceRecordRepository:
    """Persistence adapter for the single ExperienceRecord table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, model: ExperienceRecordModel) -> ExperienceRecordModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get(
        self, experience_id: str, *, for_update: bool = False
    ) -> ExperienceRecordModel | None:
        query = select(ExperienceRecordModel).where(
            ExperienceRecordModel.experience_id == experience_id
        )
        if for_update:
            query = query.with_for_update()
        return cast(ExperienceRecordModel | None, await self.session.scalar(query))

    async def active_candidates(
        self,
        *,
        course_id: str | None = None,
        capability_id: str = "",
        owner_id: str | None = None,
        limit: int = 100,
    ) -> list[ExperienceRecordModel]:
        now = datetime.now(UTC)
        conditions = [
            ExperienceRecordModel.lifecycle_status == "active",
            or_(
                ExperienceRecordModel.expires_at.is_(None),
                ExperienceRecordModel.expires_at > now,
            ),
            or_(
                ExperienceRecordModel.scope != "user_scoped",
                and_(
                    ExperienceRecordModel.scope == "user_scoped",
                    ExperienceRecordModel.scope_owner_id == owner_id,
                ),
            ),
        ]
        if course_id:
            normalized = course_id.strip().upper()
            conditions.append(
                or_(
                    ExperienceRecordModel.scope != "course_scoped",
                    ExperienceRecordModel.course_id == normalized,
                )
            )
        if capability_id:
            conditions.append(
                or_(
                    ExperienceRecordModel.capability_id == capability_id,
                    ExperienceRecordModel.capability_id == "",
                )
            )
        query = (
            select(ExperienceRecordModel)
            .where(*conditions)
            .order_by(
                ExperienceRecordModel.confidence.desc(),
                ExperienceRecordModel.updated_at.desc(),
            )
            .limit(limit)
        )
        return list((await self.session.scalars(query)).all())

    async def list_for_lifecycle(
        self, lifecycle_status: str, *, limit: int = 100
    ) -> list[ExperienceRecordModel]:
        query = (
            select(ExperienceRecordModel)
            .where(ExperienceRecordModel.lifecycle_status == lifecycle_status)
            .order_by(ExperienceRecordModel.updated_at.desc())
            .limit(limit)
        )
        return list((await self.session.scalars(query)).all())
