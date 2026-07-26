from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.providers.base import AgentProvider
from app.services.knowledge_base import KnowledgeBaseService
from app.services.rag_retrieval import RAGRetrievalService


def get_settings_from_app(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_provider(request: Request) -> AgentProvider:
    return cast(AgentProvider, request.app.state.provider)


def get_knowledge_base(request: Request) -> KnowledgeBaseService:
    return cast(KnowledgeBaseService, request.app.state.knowledge_base)


def get_rag_retrieval(request: Request) -> RAGRetrievalService:
    return cast(RAGRetrievalService, request.app.state.rag_retrieval)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = cast(
        async_sessionmaker[AsyncSession], request.app.state.session_factory
    )
    async with session_factory() as session:
        yield session
