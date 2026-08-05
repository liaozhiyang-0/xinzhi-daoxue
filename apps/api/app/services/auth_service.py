from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.contracts.auth import RegisterRequest
from app.core.config import Settings
from app.core.errors import (
    AccountDisabledError,
    AuthenticationRateLimitError,
    ConflictError,
    InvalidCredentialsError,
    NotFoundError,
)
from app.core.security import (
    create_opaque_token,
    hash_password,
    hash_token,
    normalize_login,
    verify_password,
)
from app.models import AccountModel, AccountStatus, AuthSessionModel
from app.services.audit_service import record_audit


def _as_utc(value: datetime) -> datetime:
    """Normalize database timestamps, including SQLite's naive UTC values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class Principal:
    authenticated: bool
    is_guest: bool = False
    account_id: str = ""
    user_id: str = ""
    login: str = ""
    display_name: str = ""
    role: str = ""
    session_id: str = ""
    access_expires_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    status: str = ""

    @classmethod
    def anonymous(cls) -> Principal:
        return cls(authenticated=False)

    @classmethod
    def guest_principal(cls, user_id: str, expires_at: datetime) -> Principal:
        return cls(
            authenticated=False,
            is_guest=True,
            user_id=user_id,
            display_name="游客",
            role="guest",
            access_expires_at=expires_at,
            status="guest",
        )

    @property
    def has_identity(self) -> bool:
        return self.authenticated or self.is_guest

    def effective_user_id(self, requested: str | None) -> str:
        if self.has_identity:
            return self.user_id
        return str(requested or "")


@dataclass(frozen=True, slots=True)
class IssuedAuthSession:
    session: AuthSessionModel
    account: AccountModel
    access_token: str
    refresh_token: str


@dataclass(slots=True)
class _LoginAttempt:
    first_failed_at: datetime
    failures: int = 0
    locked_until: datetime | None = None


class LoginRateLimiter:
    """Process-local limiter with a stable interface for a future Redis backend."""

    def __init__(self) -> None:
        self._attempts: dict[str, _LoginAttempt] = {}

    def check(self, key: str, settings: Settings, *, now: datetime) -> None:
        item = self._attempts.get(key)
        if item is None:
            return
        if item.locked_until is not None and item.locked_until > now:
            retry_after = max(1, int((item.locked_until - now).total_seconds()))
            raise AuthenticationRateLimitError(
                "登录尝试过于频繁，请稍后再试",
                details={"retry_after_seconds": retry_after},
            )
        if (
            now - item.first_failed_at
        ).total_seconds() > settings.auth_login_window_seconds:
            self._attempts.pop(key, None)

    def failure(self, key: str, settings: Settings, *, now: datetime) -> None:
        item = self._attempts.get(key)
        if item is None or (
            now - item.first_failed_at
        ).total_seconds() > settings.auth_login_window_seconds:
            item = _LoginAttempt(first_failed_at=now)
            self._attempts[key] = item
        item.failures += 1
        if item.failures >= settings.auth_login_max_attempts:
            item.locked_until = now + timedelta(
                seconds=settings.auth_login_lockout_seconds
            )

    def success(self, key: str) -> None:
        self._attempts.pop(key, None)


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        limiter: LoginRateLimiter,
    ) -> None:
        self.db = db
        self.settings = settings
        self.limiter = limiter

    async def register(
        self,
        data: RegisterRequest,
        *,
        request: Request,
        role: str = "student",
    ) -> IssuedAuthSession:
        if not self.settings.auth_allow_registration:
            raise AccountDisabledError("当前环境不允许公开注册")
        normalized = normalize_login(data.login)
        existing = await self._account_by_login(normalized)
        if existing is not None:
            raise ConflictError("登录名已存在")
        now = datetime.now(UTC)
        account = AccountModel(
            id=f"user_{uuid4().hex}",
            login=data.login.strip(),
            login_normalized=normalized,
            display_name=data.display_name.strip() or data.login.strip(),
            password_hash=self._password_hash(data.password),
            role=role,
            status=AccountStatus.ACTIVE,
            password_changed_at=now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(account)
        await self.db.flush()
        issued = self._issue(account, request)
        record_audit(
            self.db,
            request,
            action="account.register",
            actor_account_id=account.id,
            target_type="account",
            target_id=account.id,
        )
        await self.db.commit()
        return issued

    async def login(
        self, login: str, password: str, *, request: Request
    ) -> IssuedAuthSession:
        normalized = normalize_login(login)
        key = self._attempt_key(normalized, request)
        now = datetime.now(UTC)
        self.limiter.check(key, self.settings, now=now)
        account = await self._account_by_login(normalized)
        valid = account is not None and verify_password(password, account.password_hash)
        if not valid:
            self.limiter.failure(key, self.settings, now=now)
            raise InvalidCredentialsError("登录名或密码错误")
        assert account is not None
        if account.status != AccountStatus.ACTIVE or (
            account.locked_until is not None
            and _as_utc(account.locked_until) > now
        ):
            raise AccountDisabledError("账号当前不可用")
        self.limiter.success(key)
        account.failed_login_attempts = 0
        account.locked_until = None
        account.last_login_at = now
        account.updated_at = now
        issued = self._issue(account, request)
        record_audit(
            self.db,
            request,
            action="auth.login",
            actor_account_id=account.id,
            target_type="account",
            target_id=account.id,
        )
        await self.db.commit()
        return issued

    async def refresh(
        self, refresh_token: str, *, request: Request
    ) -> IssuedAuthSession:
        now = datetime.now(UTC)
        session = await self._session_by_refresh(refresh_token)
        if (
            session is None
            or session.revoked_at is not None
            or _as_utc(session.refresh_expires_at) <= now
            or session.account.status != AccountStatus.ACTIVE
        ):
            raise InvalidCredentialsError("刷新会话无效或已过期")
        session.revoked_at = now
        issued = self._issue(session.account, request)
        record_audit(
            self.db,
            request,
            action="auth.refresh",
            actor_account_id=session.account.id,
            target_type="auth_session",
            target_id=session.id,
        )
        await self.db.commit()
        return issued

    async def logout(
        self,
        access_token: str | None,
        refresh_token: str | None,
        *,
        request: Request | None = None,
    ) -> None:
        token_hashes = {
            hash_token(token)
            for token in (access_token, refresh_token)
            if token
        }
        if not token_hashes:
            return
        statement = select(AuthSessionModel).where(
            (AuthSessionModel.access_token_hash.in_(token_hashes))
            | (AuthSessionModel.refresh_token_hash.in_(token_hashes))
        )
        session = (await self.db.execute(statement)).scalar_one_or_none()
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            record_audit(
                self.db,
                request,
                action="auth.logout",
                actor_account_id=session.account_id,
                target_type="auth_session",
                target_id=session.id,
            )
            await self.db.commit()

    async def authenticate(self, access_token: str) -> Principal:
        now = datetime.now(UTC)
        statement = (
            select(AuthSessionModel)
            .options(selectinload(AuthSessionModel.account))
            .where(AuthSessionModel.access_token_hash == hash_token(access_token))
        )
        session = (await self.db.execute(statement)).scalar_one_or_none()
        if (
            session is None
            or session.revoked_at is not None
            or _as_utc(session.access_expires_at) <= now
            or session.account.status != AccountStatus.ACTIVE
        ):
            raise InvalidCredentialsError("认证会话无效或已过期")
        return Principal(
            authenticated=True,
            account_id=session.account.id,
            user_id=session.account.id,
            login=session.account.login,
            display_name=session.account.display_name,
            role=session.account.role,
            session_id=session.id,
            access_expires_at=_as_utc(session.access_expires_at),
            last_login_at=session.account.last_login_at,
            created_at=session.account.created_at,
            status=session.account.status.value,
        )

    async def get_account(self, account_id: str) -> AccountModel:
        account = await self.db.get(AccountModel, account_id)
        if account is None:
            raise NotFoundError("账号不存在")
        return account

    def _issue(self, account: AccountModel, request: Request) -> IssuedAuthSession:
        now = datetime.now(UTC)
        access_token = create_opaque_token()
        refresh_token = create_opaque_token()
        session = AuthSessionModel(
            id=f"auth_{uuid4().hex}",
            account_id=account.id,
            access_token_hash=hash_token(access_token),
            refresh_token_hash=hash_token(refresh_token),
            access_expires_at=now
            + timedelta(seconds=self.settings.auth_access_ttl_seconds),
            refresh_expires_at=now
            + timedelta(seconds=self.settings.auth_refresh_ttl_seconds),
            ip_address=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:512] or None,
            created_at=now,
        )
        self.db.add(session)
        session.account = account
        return IssuedAuthSession(session, account, access_token, refresh_token)

    async def _account_by_login(self, normalized: str) -> AccountModel | None:
        statement = select(AccountModel).where(
            AccountModel.login_normalized == normalized
        )
        return (await self.db.execute(statement)).scalar_one_or_none()

    async def _session_by_refresh(self, refresh_token: str) -> AuthSessionModel | None:
        statement = (
            select(AuthSessionModel)
            .options(selectinload(AuthSessionModel.account))
            .where(AuthSessionModel.refresh_token_hash == hash_token(refresh_token))
        )
        return (await self.db.execute(statement)).scalar_one_or_none()

    def _password_hash(self, password: str) -> str:
        return hash_password(
            password,
            n_log2=self.settings.auth_scrypt_n_log2,
            r=self.settings.auth_scrypt_r,
            p=self.settings.auth_scrypt_p,
        )

    @staticmethod
    def _attempt_key(login: str, request: Request) -> str:
        host = request.client.host if request.client else "unknown"
        return f"{host}:{login}"
