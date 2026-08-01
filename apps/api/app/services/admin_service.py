from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from fastapi import Request
from sqlalchemy import func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.contracts.admin import (
    AdminAccountCreate,
    AdminAccountUpdate,
    AdminPasswordReset,
)
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_password, normalize_login
from app.models import (
    AccountModel,
    AccountStatus,
    AuditLogModel,
    AuthSessionModel,
    TaskModel,
    TaskStatus,
)
from app.services.audit_service import record_audit


class AdminService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def list_accounts(
        self,
        *,
        search: str | None,
        role: str | None,
        status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[AccountModel], int]:
        filters = self._account_filters(search=search, role=role, status=status)
        total = int(
            await self.db.scalar(
                select(func.count(AccountModel.id)).where(*filters)
            )
            or 0
        )
        statement = (
            select(AccountModel)
            .where(*filters)
            .order_by(AccountModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await self.db.scalars(statement)).all()), total

    async def get_account(self, account_id: str) -> AccountModel:
        account = await self.db.get(AccountModel, account_id)
        if account is None:
            raise NotFoundError("账号不存在", details={"account_id": account_id})
        return account

    async def create_account(
        self,
        data: AdminAccountCreate,
        *,
        actor_account_id: str,
        request: Request,
    ) -> AccountModel:
        normalized = normalize_login(data.login)
        existing = await self.db.scalar(
            select(AccountModel).where(AccountModel.login_normalized == normalized)
        )
        if existing is not None:
            raise ConflictError("登录名已存在")
        now = datetime.now(UTC)
        account = AccountModel(
            id=f"user_{uuid4().hex}",
            login=data.login.strip(),
            login_normalized=normalized,
            display_name=data.display_name.strip() or data.login.strip(),
            password_hash=hash_password(
                data.password,
                n_log2=self.settings.auth_scrypt_n_log2,
                r=self.settings.auth_scrypt_r,
                p=self.settings.auth_scrypt_p,
            ),
            role=data.role,
            status=AccountStatus.ACTIVE,
            password_changed_at=now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(account)
        await self.db.flush()
        record_audit(
            self.db,
            request,
            action="admin.account.create",
            actor_account_id=actor_account_id,
            target_type="account",
            target_id=account.id,
            details={"role": account.role},
        )
        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def update_account(
        self,
        account_id: str,
        data: AdminAccountUpdate,
        *,
        actor_account_id: str,
        request: Request,
    ) -> AccountModel:
        account = await self.get_account(account_id)
        if account.id == actor_account_id and (
            data.role not in {None, "admin"}
            or data.status not in {None, "active"}
        ):
            raise ConflictError("不能降低或停用当前管理员账号")
        changes: dict[str, str] = {}
        if data.display_name is not None:
            account.display_name = data.display_name.strip() or account.login
            changes["display_name"] = account.display_name
        if data.role is not None and data.role != account.role:
            await self._ensure_admin_remains(account, role=data.role)
            changes["role"] = data.role
            account.role = data.role
        if data.status is not None and data.status != account.status.value:
            await self._ensure_admin_remains(account, status=data.status)
            changes["status"] = data.status
            account.status = AccountStatus(data.status)
            account.locked_until = (
                datetime.now(UTC)
                + timedelta(seconds=self.settings.auth_login_lockout_seconds)
                if account.status == AccountStatus.LOCKED
                else None
            )
        if changes:
            account.updated_at = datetime.now(UTC)
            record_audit(
                self.db,
                request,
                action="admin.account.update",
                actor_account_id=actor_account_id,
                target_type="account",
                target_id=account.id,
                details=changes,
            )
            await self.db.commit()
            await self.db.refresh(account)
        return account

    async def reset_password(
        self,
        account_id: str,
        data: AdminPasswordReset,
        *,
        actor_account_id: str,
        request: Request,
    ) -> AccountModel:
        account = await self.get_account(account_id)
        now = datetime.now(UTC)
        account.password_hash = hash_password(
            data.password,
            n_log2=self.settings.auth_scrypt_n_log2,
            r=self.settings.auth_scrypt_r,
            p=self.settings.auth_scrypt_p,
        )
        account.password_changed_at = now
        account.failed_login_attempts = 0
        account.locked_until = None
        account.status = AccountStatus.ACTIVE
        account.updated_at = now
        await self._revoke_sessions(account.id, now)
        record_audit(
            self.db,
            request,
            action="admin.account.reset_password",
            actor_account_id=actor_account_id,
            target_type="account",
            target_id=account.id,
        )
        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def revoke_account_sessions(
        self,
        account_id: str,
        *,
        actor_account_id: str,
        request: Request,
    ) -> int:
        await self.get_account(account_id)
        count = await self._revoke_sessions(account_id, datetime.now(UTC))
        record_audit(
            self.db,
            request,
            action="admin.account.revoke_sessions",
            actor_account_id=actor_account_id,
            target_type="account",
            target_id=account_id,
            details={"revoked_count": count},
        )
        await self.db.commit()
        return count

    async def list_sessions(
        self, *, account_id: str | None, active_only: bool, offset: int, limit: int
    ) -> list[AuthSessionModel]:
        filters = []
        if account_id:
            filters.append(AuthSessionModel.account_id == account_id)
        if active_only:
            filters.append(AuthSessionModel.revoked_at.is_(None))
        statement = (
            select(AuthSessionModel)
            .options(selectinload(AuthSessionModel.account))
            .where(*filters)
            .order_by(AuthSessionModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await self.db.scalars(statement)).all())

    async def revoke_session(
        self,
        session_id: str,
        *,
        actor_account_id: str,
        request: Request,
    ) -> None:
        session = await self.db.get(AuthSessionModel, session_id)
        if session is None:
            raise NotFoundError("会话不存在", details={"session_id": session_id})
        if session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            record_audit(
                self.db,
                request,
                action="admin.session.revoke",
                actor_account_id=actor_account_id,
                target_type="auth_session",
                target_id=session.id,
                details={"account_id": session.account_id},
            )
            await self.db.commit()

    async def list_audit_logs(
        self,
        *,
        action: str | None,
        actor_account_id: str | None,
        offset: int,
        limit: int,
    ) -> list[AuditLogModel]:
        filters = []
        if action:
            filters.append(AuditLogModel.action == action)
        if actor_account_id:
            filters.append(AuditLogModel.actor_account_id == actor_account_id)
        statement = (
            select(AuditLogModel)
            .where(*filters)
            .order_by(AuditLogModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await self.db.scalars(statement)).all())

    async def overview(self) -> dict[str, int]:
        async def count_accounts(status: AccountStatus | None = None) -> int:
            statement = select(func.count(AccountModel.id))
            if status is not None:
                statement = statement.where(AccountModel.status == status)
            return int(await self.db.scalar(statement) or 0)

        account_count = await count_accounts()
        active = await count_accounts(AccountStatus.ACTIVE)
        disabled = await count_accounts(AccountStatus.DISABLED)
        locked = await count_accounts(AccountStatus.LOCKED)
        sessions = int(
            await self.db.scalar(
                select(func.count(AuthSessionModel.id)).where(
                    AuthSessionModel.revoked_at.is_(None),
                    AuthSessionModel.refresh_expires_at > datetime.now(UTC),
                )
            )
            or 0
        )
        audits = int(await self.db.scalar(select(func.count(AuditLogModel.id))) or 0)
        return {
            "account_count": account_count,
            "active_account_count": active,
            "disabled_account_count": disabled,
            "locked_account_count": locked,
            "active_session_count": sessions,
            "audit_event_count": audits,
        }

    async def list_tasks(
        self,
        *,
        search: str | None,
        status: TaskStatus | None,
        course_id: str | None,
        agent_id: str | None,
        user_id: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[TaskModel, AccountModel | None]], int]:
        filters = self._task_filters(
            search=search,
            status=status,
            course_id=course_id,
            agent_id=agent_id,
            user_id=user_id,
        )
        total = int(
            await self.db.scalar(
                select(func.count(TaskModel.id))
                .select_from(TaskModel)
                .outerjoin(AccountModel, AccountModel.id == TaskModel.user_id)
                .where(*filters)
            )
            or 0
        )
        statement = (
            select(TaskModel, AccountModel)
            .outerjoin(AccountModel, AccountModel.id == TaskModel.user_id)
            .where(*filters)
            .order_by(TaskModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.db.execute(statement)).all()
        return [
            (cast(TaskModel, row[0]), cast(AccountModel | None, row[1]))
            for row in rows
        ], total

    async def task_summary(self) -> dict[str, object]:
        rows = list(
            (
                await self.db.execute(
                    select(TaskModel.status, func.count(TaskModel.id)).group_by(
                        TaskModel.status
                    )
                )
            ).all()
        )
        counts = {str(status): int(count) for status, count in rows}
        active = sum(
            counts.get(item.value, 0)
            for item in (
                TaskStatus.CREATED,
                TaskStatus.QUEUED,
                TaskStatus.RUNNING,
                TaskStatus.WAITING_USER,
                TaskStatus.WAITING_REVIEW,
            )
        )
        return {
            "total": sum(counts.values()),
            "active": active,
            "completed": counts.get(TaskStatus.COMPLETED.value, 0),
            "failed": counts.get(TaskStatus.FAILED.value, 0),
            "status_counts": counts,
        }

    @staticmethod
    def _task_filters(
        *,
        search: str | None,
        status: TaskStatus | None,
        course_id: str | None,
        agent_id: str | None,
        user_id: str | None,
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    TaskModel.id.ilike(pattern),
                    TaskModel.intent.ilike(pattern),
                    TaskModel.agent_id.ilike(pattern),
                    AccountModel.login.ilike(pattern),
                    AccountModel.display_name.ilike(pattern),
                )
            )
        if status is not None:
            filters.append(TaskModel.status == status)
        if course_id:
            filters.append(TaskModel.course_id == course_id.strip())
        if agent_id:
            filters.append(TaskModel.agent_id == agent_id.strip())
        if user_id:
            filters.append(TaskModel.user_id == user_id.strip())
        return filters

    def _account_filters(
        self, *, search: str | None, role: str | None, status: str | None
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = []
        if search:
            term = f"%{search.strip().casefold()}%"
            filters.append(
                func.lower(AccountModel.login).like(term)
                | func.lower(AccountModel.display_name).like(term)
            )
        if role:
            filters.append(AccountModel.role == role)
        if status:
            filters.append(AccountModel.status == AccountStatus(status))
        return filters

    async def _ensure_admin_remains(
        self,
        account: AccountModel,
        *,
        role: str | None = None,
        status: str | None = None,
    ) -> None:
        removes_admin = account.role == "admin" and (
            (role is not None and role != "admin")
            or (status is not None and status != AccountStatus.ACTIVE.value)
        )
        if not removes_admin:
            return
        remaining = await self.db.scalar(
            select(func.count(AccountModel.id)).where(
                AccountModel.role == "admin",
                AccountModel.status == AccountStatus.ACTIVE,
                AccountModel.id != account.id,
            )
        )
        if not remaining:
            raise ConflictError("系统至少需要保留一个启用中的管理员账号")

    async def _revoke_sessions(self, account_id: str, now: datetime) -> int:
        result = cast(
            CursorResult[Any],
            await self.db.execute(
            update(AuthSessionModel)
            .where(
                AuthSessionModel.account_id == account_id,
                AuthSessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=now)
            ),
        )
        return int(result.rowcount or 0)
