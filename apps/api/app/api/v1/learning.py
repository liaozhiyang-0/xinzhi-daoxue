from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.learning import (
    LearnerKnowledgeState,
    LearningActionRequest,
    LearningActionResponse,
    LearningMetricsRead,
    LearningRuntimeApprovalRequest,
    LearningRuntimeCapabilityRead,
    LearningRuntimeReadinessRead,
    LearningRuntimeStatusRead,
    RetestPlanV1,
    StudentAttemptV2,
)
from app.dependencies import effective_user_id, get_current_principal, get_db
from app.services.auth_service import Principal
from app.services.learning_loop import LearningLoopService
from app.services.learning_metrics import LearningMetricsService

router = APIRouter(prefix="/learning", tags=["learning"])

_LEARNING_RUNTIME_CAPABILITY_IDS = (
    "TEACHING_INTERACTION_V1",
    "LEARNING_PROGRESS_V1",
)
_LEARNING_RUNTIME_BLOCKERS = (
    ("supports_pause", "learning_runtime_pause_not_implemented"),
    ("supports_resume", "learning_runtime_resume_not_implemented"),
    ("supports_input", "learning_runtime_input_not_implemented"),
)
_LEARNING_RUNTIME_EVIDENCE_BLOCKER = (
    "learning_runtime_authorized_paired_evidence_missing"
)
_LEARNING_RUNTIME_DISABLED_BLOCKER = "learning_runtime_disabled"
_LEARNING_RUNTIME_DESCRIPTOR_MISSING_BLOCKER = "learning_runtime_descriptor_missing"
_LEARNING_RUNTIME_DESCRIPTOR_INVALID_BLOCKER = "learning_runtime_descriptor_invalid"


def _require_metrics_manager(request: Request, principal: Principal) -> None:
    if not request.app.state.settings.auth_required:
        return
    if not principal.authenticated or principal.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="需要教师或管理员权限")


@router.post("/actions", response_model=LearningActionResponse)
async def learning_action(
    data: LearningActionRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> LearningActionResponse:
    data = data.model_copy(
        update={"user_id": effective_user_id(principal, data.user_id)}
    )
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.act(db, data)


@router.post(
    "/runtime/{run_id}/approve",
    response_model=LearningActionResponse,
    summary="Approve a teaching interaction Runtime run",
)
async def approve_learning_runtime(
    run_id: str,
    data: LearningRuntimeApprovalRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> LearningActionResponse:
    user_id = effective_user_id(principal, None)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.approve_runtime_interaction(
        db,
        run_id,
        user_id=user_id,
        expected_state_version=data.expected_state_version,
    )


@router.get(
    "/runtime/{run_id}",
    response_model=LearningRuntimeStatusRead,
    summary="Read a redacted LearningLoop Runtime checkpoint",
)
async def learning_runtime_status(
    run_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> LearningRuntimeStatusRead:
    user_id = effective_user_id(principal, None)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.runtime_status(db, run_id, user_id=user_id)


@router.get(
    "/runtime-readiness",
    response_model=LearningRuntimeReadinessRead,
    summary="Read LearningLoop Runtime capability readiness",
)
async def learning_runtime_readiness(
    request: Request,
) -> LearningRuntimeReadinessRead:
    """Project LearningLoop descriptors without entering an execution path."""

    readiness = getattr(request.app.state, "runtime_agent_readiness", None)
    descriptors = getattr(readiness, "capability_descriptors", ())
    selected: dict[str, object] = {}
    if _is_descriptor_collection(descriptors):
        for descriptor in descriptors:
            capability_id = _descriptor_text(descriptor, "capability_id")
            domain = _descriptor_text(descriptor, "domain")
            if (
                domain == "learning_loop"
                and capability_id in _LEARNING_RUNTIME_CAPABILITY_IDS
                and capability_id not in selected
            ):
                selected[capability_id] = descriptor

    capabilities: list[LearningRuntimeCapabilityRead] = []
    blockers: list[str] = []
    for capability_id in _LEARNING_RUNTIME_CAPABILITY_IDS:
        descriptor = selected.get(capability_id)
        if descriptor is None:
            blockers.append(_LEARNING_RUNTIME_DESCRIPTOR_MISSING_BLOCKER)
            continue
        capability = _project_learning_runtime_descriptor(descriptor)
        if capability is None:
            blockers.append(_LEARNING_RUNTIME_DESCRIPTOR_INVALID_BLOCKER)
            continue
        capabilities.append(capability)
        for blocker in capability.blockers:
            if blocker not in blockers:
                blockers.append(blocker)

    return LearningRuntimeReadinessRead(
        provider_called=False,
        capabilities=capabilities,
        blockers=blockers,
    )


def _is_descriptor_collection(value: object) -> bool:
    return isinstance(value, Iterable) and not isinstance(
        value, (str, bytes, Mapping)
    )


def _descriptor_value(descriptor: object, field_name: str) -> object:
    if isinstance(descriptor, Mapping):
        return descriptor.get(field_name)
    return getattr(descriptor, field_name, None)


def _descriptor_text(descriptor: object, field_name: str) -> str | None:
    value = _descriptor_value(descriptor, field_name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _descriptor_bool(descriptor: object, field_name: str) -> bool:
    value = _descriptor_value(descriptor, field_name)
    return value if isinstance(value, bool) else False


def _descriptor_actions(descriptor: object) -> list[str]:
    value = _descriptor_value(descriptor, "supported_actions")
    if isinstance(value, str):
        values: Iterable[object] = (value,)
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        values = value
    else:
        return []
    actions: list[str] = []
    for item in values:
        if isinstance(item, str) and item.strip() and item.strip() not in actions:
            actions.append(item.strip())
    return actions


def _project_learning_runtime_descriptor(
    descriptor: object,
) -> LearningRuntimeCapabilityRead | None:
    capability_id = _descriptor_text(descriptor, "capability_id")
    runtime_id = _descriptor_text(descriptor, "runtime_id")
    version = _descriptor_text(descriptor, "version")
    control_scope = _descriptor_text(descriptor, "control_scope")
    result_contract = _descriptor_text(descriptor, "result_contract")
    if not all((capability_id, runtime_id, version, control_scope, result_contract)):
        return None
    assert capability_id is not None
    assert runtime_id is not None
    assert version is not None
    assert control_scope is not None
    assert result_contract is not None

    supports = {
        field_name: _descriptor_bool(descriptor, field_name)
        for field_name, _ in _LEARNING_RUNTIME_BLOCKERS
    }
    supports["supports_approval"] = _descriptor_bool(
        descriptor, "supports_approval"
    )
    capability_blockers: list[str] = []
    if not supports["supports_approval"]:
        capability_blockers.append("learning_runtime_approval_not_implemented")
    for field_name, blocker in _LEARNING_RUNTIME_BLOCKERS:
        if not supports[field_name]:
            capability_blockers.append(blocker)
    capability_blockers.append(_LEARNING_RUNTIME_EVIDENCE_BLOCKER)
    if not _descriptor_bool(descriptor, "enabled"):
        capability_blockers.append(_LEARNING_RUNTIME_DISABLED_BLOCKER)

    return LearningRuntimeCapabilityRead(
        capability_id=capability_id,
        runtime_id=runtime_id,
        version=version,
        enabled=_descriptor_bool(descriptor, "enabled"),
        supported_actions=_descriptor_actions(descriptor),
        supports_pause=supports["supports_pause"],
        supports_resume=supports["supports_resume"],
        supports_approval=supports["supports_approval"],
        supports_input=supports["supports_input"],
        control_scope=control_scope,
        result_contract=result_contract,
        blockers=capability_blockers,
    )


@router.get("/states", response_model=list[LearnerKnowledgeState])
async def learning_states(
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    principal: Principal = Depends(get_current_principal),
    course_id: str | None = Query(default=None, max_length=32),
    db: AsyncSession = Depends(get_db),
) -> list[LearnerKnowledgeState]:
    user_id = effective_user_id(principal, user_id)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.list_states(db, user_id, course_id)


@router.get("/attempts", response_model=list[StudentAttemptV2])
async def learning_attempts(
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    principal: Principal = Depends(get_current_principal),
    source_task_id: str | None = Query(default=None, max_length=64),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[StudentAttemptV2]:
    user_id = effective_user_id(principal, user_id)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.attempts.list(
        db,
        user_id=user_id,
        source_task_id=source_task_id,
        offset=offset,
        limit=limit,
    )


@router.get("/attempts/{attempt_id}", response_model=StudentAttemptV2)
async def learning_attempt(
    attempt_id: str,
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> StudentAttemptV2:
    user_id = effective_user_id(principal, user_id)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.attempts.get(db, attempt_id=attempt_id, user_id=user_id)


@router.get("/retests", response_model=list[RetestPlanV1])
async def learning_retests(
    request: Request,
    user_id: str = Query(min_length=1, max_length=128),
    principal: Principal = Depends(get_current_principal),
    status: str | None = Query(
        default=None,
        pattern="^(scheduled|due|completed|cancelled|superseded)$",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[RetestPlanV1]:
    user_id = effective_user_id(principal, user_id)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    return await service.retests.list(
        db,
        user_id=user_id,
        status=status,
        offset=offset,
        limit=limit,
    )


@router.get("/metrics", response_model=LearningMetricsRead)
async def learning_metrics(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    course_id: str | None = Query(default=None, max_length=32),
    window_start: datetime | None = Query(default=None),
    window_end: datetime | None = Query(default=None),
    row_limit: int = Query(
        default=LearningMetricsService.DEFAULT_ROW_LIMIT, ge=1, le=20_000
    ),
    db: AsyncSession = Depends(get_db),
) -> LearningMetricsRead:
    _require_metrics_manager(request, principal)
    end = window_end or datetime.now(UTC)
    start = window_start or end - timedelta(days=30)
    if start >= end:
        raise HTTPException(
            status_code=422, detail="window_start must be before window_end"
        )
    return await LearningMetricsService().aggregate(
        db,
        course_id=course_id,
        window_start=start,
        window_end=end,
        row_limit=row_limit,
    )
