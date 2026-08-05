from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ArtifactModel


class ArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, model: ArtifactModel) -> ArtifactModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get(self, artifact_id: str) -> ArtifactModel | None:
        statement = (
            select(ArtifactModel)
            .options(selectinload(ArtifactModel.task))
            .where(ArtifactModel.id == artifact_id)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()
