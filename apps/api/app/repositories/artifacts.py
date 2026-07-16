from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArtifactModel


class ArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, model: ArtifactModel) -> ArtifactModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get(self, artifact_id: str) -> ArtifactModel | None:
        return await self.session.get(ArtifactModel, artifact_id)
