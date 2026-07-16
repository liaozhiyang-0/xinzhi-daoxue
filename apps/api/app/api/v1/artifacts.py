from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.api import ArtifactRead
from app.core.errors import NotFoundError
from app.dependencies import get_db
from app.repositories import ArtifactRepository

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{artifact_id}", response_model=ArtifactRead)
async def get_artifact(
    artifact_id: str, db: AsyncSession = Depends(get_db)
) -> ArtifactRead:
    artifact = await ArtifactRepository(db).get(artifact_id)
    if artifact is None:
        raise NotFoundError("产物不存在", details={"artifact_id": artifact_id})
    return ArtifactRead.model_validate(artifact)
