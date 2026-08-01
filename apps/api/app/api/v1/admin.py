from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.admin import (
    AccountRole,
    AccountStatusValue,
    AdminAccountCreate,
    AdminAccountRead,
    AdminAccountUpdate,
    AdminOverviewRead,
    AdminPasswordReset,
    AdminSessionRead,
    AdminTaskRead,
    AdminTaskSummaryRead,
    AuditLogRead,
)
from app.dependencies import get_current_principal, get_db, require_admin_account
from app.models import TaskStatus
from app.services.admin_service import AdminService
from app.services.auth_service import Principal

router = APIRouter(
    prefix="/admin",
    tags=["management"],
    dependencies=[Depends(require_admin_account)],
)


def _service(request: Request, db: AsyncSession) -> AdminService:
    return AdminService(db, request.app.state.settings)


def _session_read(session: Any) -> AdminSessionRead:
    return AdminSessionRead(
        id=session.id,
        account_id=session.account_id,
        login=session.account.login,
        access_expires_at=session.access_expires_at,
        refresh_expires_at=session.refresh_expires_at,
        revoked_at=session.revoked_at,
        last_seen_at=session.last_seen_at,
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        created_at=session.created_at,
    )


@router.get("/overview", response_model=AdminOverviewRead)
async def overview(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminOverviewRead:
    return AdminOverviewRead(**(await _service(request, db).overview()))


def _task_read(task: Any, account: Any | None) -> AdminTaskRead:
    return AdminTaskRead(
        id=task.id,
        session_id=task.session_id,
        user_id=task.user_id,
        login=account.login if account is not None else None,
        display_name=account.display_name if account is not None else None,
        course_id=task.course_id,
        intent=task.intent,
        status=task.status,
        provider=task.provider,
        agent_id=task.agent_id,
        route_status=task.route_status,
        attempt=task.attempt,
        failure_category=task.failure_category,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )


@router.get("/task-summary", response_model=AdminTaskSummaryRead)
async def task_summary(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminTaskSummaryRead:
    data = await _service(request, db).task_summary()
    return AdminTaskSummaryRead(
        total=int(cast(int, data["total"])),
        active=int(cast(int, data["active"])),
        completed=int(cast(int, data["completed"])),
        failed=int(cast(int, data["failed"])),
        status_counts=cast(dict[str, int], data["status_counts"]),
    )


@router.get("/tasks")
async def list_tasks(
    request: Request,
    search: str | None = Query(default=None, max_length=255),
    status: TaskStatus | None = None,
    course_id: str | None = Query(default=None, max_length=32),
    agent_id: str | None = Query(default=None, max_length=64),
    user_id: str | None = Query(default=None, max_length=128),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    tasks, total = await _service(request, db).list_tasks(
        search=search,
        status=status,
        course_id=course_id,
        agent_id=agent_id,
        user_id=user_id,
        offset=offset,
        limit=limit,
    )
    return {
        "items": [_task_read(task, account) for task, account in tasks],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/accounts")
async def list_accounts(
    request: Request,
    search: str | None = Query(default=None, max_length=255),
    role: AccountRole | None = None,
    status: AccountStatusValue | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    accounts, total = await _service(request, db).list_accounts(
        search=search,
        role=role,
        status=status,
        offset=offset,
        limit=limit,
    )
    return {
        "items": [AdminAccountRead.model_validate(item) for item in accounts],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.post(
    "/accounts",
    response_model=AdminAccountRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    data: AdminAccountCreate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AdminAccountRead:
    account = await _service(request, db).create_account(
        data, actor_account_id=principal.account_id, request=request
    )
    return AdminAccountRead.model_validate(account)


@router.get("/accounts/{account_id}", response_model=AdminAccountRead)
async def get_account(
    account_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminAccountRead:
    account = await _service(request, db).get_account(account_id)
    return AdminAccountRead.model_validate(account)


@router.patch("/accounts/{account_id}", response_model=AdminAccountRead)
async def update_account(
    account_id: str,
    data: AdminAccountUpdate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AdminAccountRead:
    account = await _service(request, db).update_account(
        account_id,
        data,
        actor_account_id=principal.account_id,
        request=request,
    )
    return AdminAccountRead.model_validate(account)


@router.post("/accounts/{account_id}/reset-password", response_model=AdminAccountRead)
async def reset_password(
    account_id: str,
    data: AdminPasswordReset,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AdminAccountRead:
    account = await _service(request, db).reset_password(
        account_id,
        data,
        actor_account_id=principal.account_id,
        request=request,
    )
    return AdminAccountRead.model_validate(account)


@router.post("/accounts/{account_id}/revoke-sessions")
async def revoke_account_sessions(
    account_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    count = await _service(request, db).revoke_account_sessions(
        account_id,
        actor_account_id=principal.account_id,
        request=request,
    )
    return {"revoked_count": count}


@router.get("/sessions", response_model=list[AdminSessionRead])
async def list_sessions(
    request: Request,
    account_id: str | None = Query(default=None, max_length=64),
    active_only: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[AdminSessionRead]:
    sessions = await _service(request, db).list_sessions(
        account_id=account_id,
        active_only=active_only,
        offset=offset,
        limit=limit,
    )
    return [_session_read(item) for item in sessions]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _service(request, db).revoke_session(
        session_id,
        actor_account_id=principal.account_id,
        request=request,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/audit-logs", response_model=list[AuditLogRead])
async def list_audit_logs(
    request: Request,
    action: str | None = Query(default=None, max_length=96),
    actor_account_id: str | None = Query(default=None, max_length=64),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogRead]:
    items = await _service(request, db).list_audit_logs(
        action=action,
        actor_account_id=actor_account_id,
        offset=offset,
        limit=limit,
    )
    return [AuditLogRead.model_validate(item) for item in items]
