from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.auth import (
    AccountRead,
    AuthMeRead,
    AuthSessionRead,
    GuestSessionRead,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.core.errors import AuthenticationRequiredError, InvalidCredentialsError
from app.core.security import create_guest_token, verify_guest_token
from app.dependencies import get_current_principal, get_db
from app.services.auth_service import (
    AuthService,
    IssuedAuthSession,
    Principal,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _service(request: Request, db: AsyncSession) -> AuthService:
    return AuthService(
        db,
        request.app.state.settings,
        request.app.state.auth_rate_limiter,
    )


def _set_auth_cookies(
    response: Response, request: Request, access: str, refresh: str
) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        settings.auth_access_cookie_name,
        access,
        max_age=settings.auth_access_ttl_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_same_site,
        path="/",
    )
    response.set_cookie(
        settings.auth_refresh_cookie_name,
        refresh,
        max_age=settings.auth_refresh_ttl_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_same_site,
        path="/api/v1/auth",
    )
    response.delete_cookie(settings.auth_guest_cookie_name, path="/")


def _clear_auth_cookies(response: Response, request: Request) -> None:
    settings = request.app.state.settings
    response.delete_cookie(settings.auth_access_cookie_name, path="/")
    response.delete_cookie(settings.auth_refresh_cookie_name, path="/api/v1/auth")
    response.delete_cookie(settings.auth_guest_cookie_name, path="/")


def _set_guest_cookie(response: Response, request: Request, token: str) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        settings.auth_guest_cookie_name,
        token,
        max_age=settings.auth_guest_ttl_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_same_site,
        path="/",
    )


def _session_response(issued: IssuedAuthSession) -> AuthSessionRead:
    session = issued.session
    account = issued.account
    return AuthSessionRead(
        account=AccountRead.model_validate(account),
        access_expires_at=session.access_expires_at,
        refresh_expires_at=session.refresh_expires_at,
    )


@router.post(
    "/register",
    response_model=AuthSessionRead,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionRead:
    issued = await _service(request, db).register(data, request=request)
    _set_auth_cookies(response, request, issued.access_token, issued.refresh_token)
    return _session_response(issued)


@router.post("/login", response_model=AuthSessionRead)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionRead:
    issued = await _service(request, db).login(
        data.login, data.password, request=request
    )
    _set_auth_cookies(response, request, issued.access_token, issued.refresh_token)
    return _session_response(issued)


@router.post("/guest", response_model=GuestSessionRead)
async def guest(request: Request, response: Response) -> GuestSessionRead:
    settings = request.app.state.settings
    if not settings.auth_allow_guest:
        raise AuthenticationRequiredError("当前环境不允许游客模式")
    signing_key = (
        settings.auth_guest_signing_key.get_secret_value()
        or "development-guest-signing-key"
    )
    token = create_guest_token(signing_key, ttl_seconds=settings.auth_guest_ttl_seconds)
    _set_guest_cookie(response, request, token)
    claims = verify_guest_token(token, signing_key)
    if claims is None:
        raise AuthenticationRequiredError("游客会话创建失败")
    user_id, expires_at = claims
    return GuestSessionRead(user_id=user_id, expires_at=expires_at)


@router.post("/refresh", response_model=AuthSessionRead)
async def refresh(
    data: RefreshRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionRead:
    refresh_token = data.refresh_token or request.cookies.get(
        request.app.state.settings.auth_refresh_cookie_name
    )
    if not refresh_token:
        raise InvalidCredentialsError("缺少刷新会话")
    issued = await _service(request, db).refresh(refresh_token, request=request)
    _set_auth_cookies(response, request, issued.access_token, issued.refresh_token)
    return _session_response(issued)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Response:
    authorization = request.headers.get("authorization", "")
    _, _, access_token = authorization.partition(" ")
    await _service(request, db).logout(
        access_token.strip() if access_token else request.cookies.get(
            request.app.state.settings.auth_access_cookie_name
        ),
        request.cookies.get(request.app.state.settings.auth_refresh_cookie_name),
        request=request,
    )
    _clear_auth_cookies(response, request)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AuthMeRead | GuestSessionRead)
async def me(
    principal: Principal = Depends(get_current_principal),
) -> AuthMeRead | GuestSessionRead:
    if principal.is_guest:
        if principal.access_expires_at is None:
            raise AuthenticationRequiredError("游客会话无效或已过期")
        return GuestSessionRead(
            user_id=principal.user_id, expires_at=principal.access_expires_at
        )
    if not principal.authenticated:
        raise AuthenticationRequiredError("请先登录")
    if principal.access_expires_at is None:
        raise AuthenticationRequiredError("认证会话无效或已过期")
    return AuthMeRead(
        id=principal.account_id,
        login=principal.login,
        display_name=principal.display_name,
        role=principal.role,
        status=principal.status,
        last_login_at=principal.last_login_at,
        created_at=principal.created_at or datetime.now(UTC),
        session_id=principal.session_id,
        access_expires_at=principal.access_expires_at,
    )
