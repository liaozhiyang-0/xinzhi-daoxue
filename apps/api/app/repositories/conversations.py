from __future__ import annotations

from typing import cast

from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConversationMessageModel


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, model: ConversationMessageModel) -> ConversationMessageModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get(self, message_id: str) -> ConversationMessageModel | None:
        return cast(
            ConversationMessageModel | None,
            await self.session.get(ConversationMessageModel, message_id),
        )

    async def list_by_ids(
        self,
        session_id: str,
        *,
        user_id: str,
        message_ids: list[str],
    ) -> list[ConversationMessageModel]:
        bounded_ids = list(dict.fromkeys(str(item) for item in message_ids))[:100]
        if not bounded_ids:
            return []
        query = select(ConversationMessageModel).where(
            ConversationMessageModel.session_id == session_id,
            ConversationMessageModel.user_id == user_id,
            ConversationMessageModel.id.in_(bounded_ids),
        )
        return list((await self.session.scalars(query)).all())

    async def get_for_task_role(
        self, task_id: str, role: str
    ) -> ConversationMessageModel | None:
        query = select(ConversationMessageModel).where(
            ConversationMessageModel.source_task_id == task_id,
            ConversationMessageModel.role == role,
        )
        return cast(
            ConversationMessageModel | None, await self.session.scalar(query)
        )

    async def list_for_session(
        self,
        session_id: str,
        *,
        user_id: str,
        after_sequence: int = 0,
        limit: int = 50,
        visible_only: bool = True,
    ) -> list[ConversationMessageModel]:
        conditions = [
            ConversationMessageModel.session_id == session_id,
            ConversationMessageModel.user_id == user_id,
            ConversationMessageModel.sequence > after_sequence,
        ]
        if visible_only:
            conditions.append(
                ConversationMessageModel.visibility == "user_visible"
            )
        query = (
            select(ConversationMessageModel)
            .where(*conditions)
            .order_by(asc(ConversationMessageModel.sequence))
            .limit(limit)
        )
        return list((await self.session.scalars(query)).all())

    async def list_recent(
        self, session_id: str, *, user_id: str, limit: int
    ) -> list[ConversationMessageModel]:
        query = (
            select(ConversationMessageModel)
            .where(
                ConversationMessageModel.session_id == session_id,
                ConversationMessageModel.user_id == user_id,
                ConversationMessageModel.visibility == "user_visible",
                ConversationMessageModel.status != "superseded",
            )
            .order_by(desc(ConversationMessageModel.sequence))
            .limit(limit)
        )
        rows = list((await self.session.scalars(query)).all())
        rows.reverse()
        return rows

    async def list_range(
        self,
        session_id: str,
        *,
        user_id: str,
        from_sequence: int,
        through_sequence: int,
    ) -> list[ConversationMessageModel]:
        query = (
            select(ConversationMessageModel)
            .where(
                ConversationMessageModel.session_id == session_id,
                ConversationMessageModel.user_id == user_id,
                ConversationMessageModel.sequence >= from_sequence,
                ConversationMessageModel.sequence <= through_sequence,
                ConversationMessageModel.visibility == "user_visible",
            )
            .order_by(asc(ConversationMessageModel.sequence))
        )
        return list((await self.session.scalars(query)).all())

    async def list_older(
        self,
        session_id: str,
        *,
        user_id: str,
        before_sequence: int,
        limit: int,
    ) -> list[ConversationMessageModel]:
        query = (
            select(ConversationMessageModel)
            .where(
                ConversationMessageModel.session_id == session_id,
                ConversationMessageModel.user_id == user_id,
                ConversationMessageModel.sequence < before_sequence,
                ConversationMessageModel.visibility == "user_visible",
                ConversationMessageModel.status != "superseded",
            )
            .order_by(desc(ConversationMessageModel.sequence))
            .limit(limit)
        )
        rows = list((await self.session.scalars(query)).all())
        rows.reverse()
        return rows
