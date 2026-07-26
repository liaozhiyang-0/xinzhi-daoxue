from typing import cast

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SessionModel


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, model: SessionModel) -> SessionModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get(
        self, session_id: str, *, for_update: bool = False
    ) -> SessionModel | None:
        query = select(SessionModel).where(SessionModel.id == session_id)
        if for_update:
            query = query.with_for_update()
        return cast(SessionModel | None, await self.session.scalar(query))

    async def get_for_user(
        self, session_id: str, user_id: str, *, for_update: bool = False
    ) -> SessionModel | None:
        query = select(SessionModel).where(
            SessionModel.id == session_id, SessionModel.user_id == user_id
        )
        if for_update:
            query = query.with_for_update()
        return cast(SessionModel | None, await self.session.scalar(query))

    async def list_for_user(
        self,
        user_id: str,
        *,
        include_archived: bool = False,
        query_text: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> list[SessionModel]:
        conditions = [SessionModel.user_id == user_id]
        if not include_archived:
            conditions.append(SessionModel.archived_at.is_(None))
        if query_text.strip():
            pattern = f"%{query_text.strip()}%"
            conditions.append(
                or_(
                    SessionModel.title.ilike(pattern),
                    SessionModel.course_id.ilike(pattern),
                )
            )
        query = (
            select(SessionModel)
            .where(*conditions)
            .order_by(
                desc(SessionModel.last_message_at),
                desc(SessionModel.updated_at),
            )
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.scalars(query)).all())
