from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts.api import HealthRead
from app.core.config import Settings
from app.dependencies import get_settings_from_app
from app.services.health import build_health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
async def health(
    request: Request,
    settings: Settings = Depends(get_settings_from_app),
) -> HealthRead:
    session_factory: async_sessionmaker[AsyncSession] = (
        request.app.state.session_factory
    )
    return await build_health(
        settings,
        session_factory,
        request.app.state.provider,
        request.app.state.external_search,
    )
