from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.providers.base import AgentProvider
from app.services.knowledge_base import KnowledgeBaseService


def get_settings_from_app(request: Request) -> Settings:
    return request.app.state.settings


def get_provider(request: Request) -> AgentProvider:
    return request.app.state.provider


def get_knowledge_base(request: Request) -> KnowledgeBaseService:
    return request.app.state.knowledge_base


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.session_factory() as session:
        yield session
