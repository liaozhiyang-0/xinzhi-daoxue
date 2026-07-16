from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.api import SessionCreate
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
