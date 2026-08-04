from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.admin import (
    AccountRole,
    AccountStatusValue,
    AdminAccountCreate,
    AdminAccountRead,
    AdminAccountUpdate,
    AdminEvaluationAttachmentResidueRead,
    AdminFeatureSettingRead,
    AdminFeatureSettingUpdate,
    AdminFileRead,
    AdminFileSummaryRead,
    AdminOverviewRead,
    AdminPasswordReset,
    AdminSessionRead,
    AdminTaskObservabilityRead,
    AdminTaskRead,
    AdminTaskSummaryRead,
    AuditLogRead,
)
from app.dependencies import get_current_principal, get_db, require_admin_account
from app.models import TaskStatus
from app.services.admin_service import AdminService
from app.services.auth_service import Principal
from app.services.evaluation_attachment_cleanup import EVALUATION_ATTACHMENT_PURPOSE

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


@router.get("/settings/features", response_model=list[AdminFeatureSettingRead])
async def list_feature_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[AdminFeatureSettingRead]:
    items = await _service(request, db).list_feature_settings()
    return [AdminFeatureSettingRead.model_validate(item) for item in items]


@router.patch(
    "/settings/features/{key}", response_model=AdminFeatureSettingRead
)
async def update_feature_setting(
    key: str,
    data: AdminFeatureSettingUpdate,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AdminFeatureSettingRead:
    item = await _service(request, db).update_feature_setting(
        key,
        data.enabled,
        actor_account_id=principal.account_id,
        request=request,
    )
    return AdminFeatureSettingRead.model_validate(item)


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


def _file_read(file: Any) -> AdminFileRead:
    return AdminFileRead(
        id=file.id,
        filename=file.filename,
        owner_user_id=file.owner_user_id,
        task_id=file.task_id,
        content_type=file.content_type,
        detected_content_type=file.detected_content_type,
        size_bytes=file.size_bytes,
        checksum_sha256=file.checksum_sha256,
        purpose=file.purpose,
        ingestion_status=file.ingestion_status,
        page_count=file.page_count,
        extracted_text=file.extracted_text,
        extraction_metadata=file.extraction_metadata or {},
        extraction_error=file.extraction_error,
        extraction_version=file.extraction_version,
        created_at=file.created_at,
        extraction_started_at=file.extraction_started_at,
        extraction_completed_at=file.extraction_completed_at,
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
        failure_category_counts=cast(
            dict[str, int], data["failure_category_counts"]
        ),
        provider_counts=cast(dict[str, int], data["provider_counts"]),
        route_status_counts=cast(dict[str, int], data["route_status_counts"]),
        cancellation_requested_count=int(
            cast(int, data["cancellation_requested_count"])
        ),
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


@router.get("/task-observability", response_model=AdminTaskObservabilityRead)
async def task_observability(
    request: Request,
    window_start: datetime | None = Query(default=None),
    window_end: datetime | None = Query(default=None),
    row_limit: int = Query(default=2_000, ge=1, le=20_000),
    db: AsyncSession = Depends(get_db),
) -> AdminTaskObservabilityRead:
    end = window_end or datetime.now(UTC)
    start = window_start or end - timedelta(days=30)
    if start >= end:
        raise HTTPException(
            status_code=422, detail="window_start must be before window_end"
        )
    data = await _service(request, db).task_observability(
        window_start=start,
        window_end=end,
        row_limit=row_limit,
    )
    return AdminTaskObservabilityRead.model_validate(data)


@router.get("/file-summary", response_model=AdminFileSummaryRead)
async def file_summary(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminFileSummaryRead:
    return AdminFileSummaryRead(**(await _service(request, db).file_summary()))


@router.get(
    "/evaluation-attachment-residue",
    response_model=AdminEvaluationAttachmentResidueRead,
)
async def evaluation_attachment_residue(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminEvaluationAttachmentResidueRead:
    report = await _service(request, db).evaluation_attachment_residue()
    return AdminEvaluationAttachmentResidueRead(
        purpose=EVALUATION_ATTACHMENT_PURPOSE,
        as_of=report.as_of,
        grace_seconds=report.grace_seconds,
        cutoff=report.cutoff,
        total_file_count=report.total_file_count,
        total_bytes=report.total_bytes,
        unbound_file_count=report.unbound_file_count,
        active_task_file_count=report.active_task_file_count,
        terminal_task_file_count=report.terminal_task_file_count,
        missing_task_file_count=report.missing_task_file_count,
        cleanup_candidate_count=report.cleanup_candidate_count,
        cleanup_candidate_bytes=report.cleanup_candidate_bytes,
        oldest_created_at=report.oldest_created_at,
    )


@router.get("/files")
async def list_files(
    request: Request,
    search: str | None = Query(default=None, max_length=255),
    ingestion_status: str | None = Query(default=None, max_length=32),
    content_type: str | None = Query(default=None, max_length=128),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    files, total = await _service(request, db).list_files(
        search=search,
        ingestion_status=ingestion_status,
        content_type=content_type,
        offset=offset,
        limit=limit,
    )
    return {
        "items": [_file_read(item) for item in files],
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
