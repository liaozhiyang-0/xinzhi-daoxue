from __future__ import annotations

from typing import cast

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MemoryModel


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, model: MemoryModel) -> MemoryModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get_for_user(self, memory_id: str, user_id: str) -> MemoryModel | None:
        query = select(MemoryModel).where(
            MemoryModel.id == memory_id, MemoryModel.user_id == user_id
        )
        return cast(MemoryModel | None, await self.session.scalar(query))

    async def list_for_user(
        self,
        user_id: str,
        *,
        memory_type: str | None = None,
        course_id: str | None = None,
        statuses: tuple[str, ...] = ("active",),
        offset: int = 0,
        limit: int = 50,
    ) -> list[MemoryModel]:
        conditions = [
            MemoryModel.user_id == user_id,
            MemoryModel.status.in_(statuses),
        ]
        if memory_type:
            conditions.append(MemoryModel.memory_type == memory_type)
        if course_id:
            conditions.append(
                or_(
                    MemoryModel.scope == "global",
                    MemoryModel.course_id == course_id.upper(),
                )
            )
        query = (
            select(MemoryModel)
            .where(*conditions)
            .order_by(desc(MemoryModel.importance), desc(MemoryModel.updated_at))
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.scalars(query)).all())

    async def max_revision(self, user_id: str) -> int:
        value = await self.session.scalar(
            select(func.sum(MemoryModel.revision + 100_000)).where(
                MemoryModel.user_id == user_id
            )
        )
        return int(value or 0)

    async def active_with_key(
        self, user_id: str, conflict_key: str
    ) -> list[MemoryModel]:
        query = select(MemoryModel).where(
            MemoryModel.user_id == user_id,
            MemoryModel.status == "active",
            MemoryModel.content_data["conflict_key"].as_string() == conflict_key,
        )
        return list((await self.session.scalars(query)).all())
