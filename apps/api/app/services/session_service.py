from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.api import SessionCreate, SessionUpdate
from app.core.errors import NotFoundError
from app.models import SessionModel
from app.repositories import SessionRepository


class SessionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = SessionRepository(db)

    async def create(self, data: SessionCreate) -> SessionModel:
        model = SessionModel(
            id=f"session_{uuid4().hex}",
            user_id=data.user_id,
            course_id=data.course_id,
            title=data.title,
            title_source="manual" if data.title.strip() else "default",
        )
        await self.repository.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return model

    async def get(self, session_id: str) -> SessionModel:
        model = await self.repository.get(session_id)
        if model is None:
            raise NotFoundError("会话不存在", details={"session_id": session_id})
        return model

    async def get_for_user(self, session_id: str, user_id: str) -> SessionModel:
        model = await self.repository.get_for_user(session_id, user_id)
        if model is None:
            raise NotFoundError("会话不存在", details={"session_id": session_id})
        return model

    async def list(
        self,
        user_id: str,
        *,
        include_archived: bool = False,
        query: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> list[SessionModel]:
        return await self.repository.list_for_user(
            user_id,
            include_archived=include_archived,
            query_text=query,
            offset=offset,
            limit=limit,
        )

    async def update(self, session_id: str, data: SessionUpdate) -> SessionModel:
        model = await self.get_for_user(session_id, data.user_id)
        changed_context = False
        if data.title is not None:
            model.title = data.title.strip()
            model.title_source = "manual"
        if data.course_id is not None:
            course_id = data.course_id.strip().upper()
            if course_id and course_id != model.course_id:
                model.course_id = course_id
                changed_context = True
        for field in (
            "memory_enabled",
            "auto_memory_enabled",
            "context_compaction_enabled",
        ):
            value = getattr(data, field)
            if value is not None and value != getattr(model, field):
                setattr(model, field, value)
                changed_context = True
        if not model.memory_enabled:
            model.auto_memory_enabled = False
        if changed_context:
            model.session_revision += 1
        model.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(model)
        return model

    async def archive(
        self, session_id: str, user_id: str, *, archived: bool
    ) -> SessionModel:
        model = await self.get_for_user(session_id, user_id)
        model.archived_at = datetime.now(UTC) if archived else None
        model.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(model)
        return model
