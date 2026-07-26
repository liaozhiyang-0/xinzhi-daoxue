from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FileModel


class FileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, model: FileModel) -> FileModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get(self, file_id: str) -> FileModel | None:
        return await self.session.get(FileModel, file_id)

    async def list_expired(self, before: datetime) -> list[FileModel]:
        result = await self.session.execute(
            select(FileModel).where(
                FileModel.expires_at.is_not(None), FileModel.expires_at <= before
            )
        )
        return list(result.scalars())
