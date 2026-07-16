from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SessionModel


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, model: SessionModel) -> SessionModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get(self, session_id: str) -> SessionModel | None:
        return await self.session.get(SessionModel, session_id)
