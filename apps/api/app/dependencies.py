from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import cast

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import AuthenticationRequiredError
from app.core.security import verify_guest_token
from app.providers.base import AgentProvider
from app.services.auth_service import AuthService, LoginRateLimiter, Principal
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


def _access_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.casefold() == "bearer" and value.strip():
        return value.strip()
    cookie_name = request.app.state.settings.auth_access_cookie_name
    return request.cookies.get(cookie_name)


async def get_current_principal(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Principal:
    token = _access_token(request)
    if not token:
        settings = request.app.state.settings
        guest_claims = verify_guest_token(
            request.cookies.get(settings.auth_guest_cookie_name, ""),
            settings.auth_guest_signing_key.get_secret_value()
            or "development-guest-signing-key",
        )
        if guest_claims is not None:
            guest_id, expires_at = guest_claims
            return Principal.guest_principal(guest_id, expires_at)
    if not token:
        if request.app.state.settings.auth_required:
            raise AuthenticationRequiredError("请先登录")
        return Principal.anonymous()
    limiter = getattr(request.app.state, "auth_rate_limiter", None)
    if not isinstance(limiter, LoginRateLimiter):
        limiter = LoginRateLimiter()
    return await AuthService(
        db, request.app.state.settings, limiter
    ).authenticate(token)


async def require_admin(
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    """Protect management/debug surfaces once production auth is enabled."""

    if not request.app.state.settings.auth_required:
        return principal
    if not principal.authenticated:
        raise AuthenticationRequiredError("璇峰厛鐧诲綍")
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="闇€瑕佺鐞嗗憳鏉冮檺")
    return principal


async def require_admin_account(
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    """Require an authenticated administrator even in development mode."""

    if not principal.authenticated:
        raise AuthenticationRequiredError("请先登录")
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return principal


def effective_user_id(principal: Principal, requested: str | None) -> str:
    """Use the authenticated account id whenever a token is present."""

    return principal.effective_user_id(requested)
