from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import NoReturn, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.learning import (
    LearnerKnowledgeState,
    LearningActionRequest,
    LearningActionResponse,
    LearningMetricsRead,
    LearningRuntimeApprovalRequest,
    LearningRuntimeCapabilityRead,
    LearningRuntimeControlAction,
    LearningRuntimeControlProjectionRead,
    LearningRuntimeControlRead,
    LearningRuntimeControlRequest,
    LearningRuntimeControlResultRead,
    LearningRuntimeReadinessRead,
    LearningRuntimeStatusRead,
    RetestPlanV1,
    StudentAttemptV2,
)
from app.core.errors import ConflictError
from app.dependencies import effective_user_id, get_current_principal, get_db
from app.services.audit_service import record_audit
from app.services.auth_service import Principal
from app.services.learning_loop import LearningLoopService
from app.services.learning_metrics import LearningMetricsService
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from app.services.runtime_release_authorization import (
    RuntimeReleaseAuthorizationRegistry,
)

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
_LEARNING_RUNTIME_CONTROL_ACTIONS: tuple[LearningRuntimeControlAction, ...] = (
    "approve",
    "pause",
    "resume",
    "input",
)
_LEARNING_RUNTIME_UNSUPPORTED_CONTROL_REASONS: dict[
    LearningRuntimeControlAction, tuple[str, str]
] = {
    "pause": (
        "learning_runtime_pause_not_available",
        "LearningLoop Runtime cannot pause from the current checkpoint state",
    ),
    "resume": (
        "learning_runtime_resume_not_available",
        "LearningLoop Runtime cannot resume from the current checkpoint state",
    ),
    "input": (
        "learning_runtime_input_not_available",
        "LearningLoop Runtime is not waiting for user input",
    ),
}


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
    "/runtime/{run_id}/controls",
    response_model=LearningRuntimeControlProjectionRead,
    summary="Read LearningLoop Runtime operator controls",
)
async def learning_runtime_controls(
    run_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> LearningRuntimeControlProjectionRead:
    """Project the domain control boundary without advancing the Run."""

    user_id = effective_user_id(principal, None)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    status = await service.runtime_status(db, run_id, user_id=user_id)
    return _project_learning_runtime_controls(status)


@router.post(
    "/runtime/{run_id}/control",
    response_model=LearningRuntimeControlResultRead,
    summary="Apply an explicit LearningLoop Runtime operator control",
)
async def control_learning_runtime(
    run_id: str,
    data: LearningRuntimeControlRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> LearningRuntimeControlResultRead:
    """Apply one durable LearningLoop control with a state-version CAS.

    The status projection performs ownership and checkpoint checks before any
    action is considered.  ``approve`` is delegated to the existing
    LearningLoop approval flow so its LearningAction result contract remains
    unchanged; pause/resume/input use the durable checkpoint control method.
    """

    _require_learning_runtime_operator(request, principal)
    user_id = effective_user_id(principal, None)
    service = cast(LearningLoopService, request.app.state.learning_loop)
    current = await service.runtime_status(db, run_id, user_id=user_id)
    control = next(
        item
        for item in _project_learning_runtime_controls(current).controls
        if item.action == data.action
    )
    if not control.available:
        await _reject_learning_runtime_control(
            db,
            request,
            principal,
            current,
            action=data.action,
            reason_code=control.reason_code,
            reason=control.reason,
        )

    try:
        result: LearningActionResponse | None
        if data.action == "approve":
            result = await service.approve_runtime_interaction(
                db,
                run_id,
                user_id=user_id,
                expected_state_version=data.expected_state_version,
            )
            control_result = None
        else:
            control_result = await service.control_runtime_interaction(
                db,
                run_id,
                action=data.action,
                user_id=user_id,
                expected_state_version=data.expected_state_version,
                data=data.data,
                idempotency_key=data.idempotency_key,
            )
            result = control_result.response
    except ConflictError as exc:
        await _reject_learning_runtime_control(
            db,
            request,
            principal,
            current,
            action=data.action,
            reason_code=(
                "learning_runtime_approval_rejected"
                if data.action == "approve"
                else "learning_runtime_control_rejected"
            ),
            reason=str(exc)[:500],
        )

    updated = await service.runtime_status(db, run_id, user_id=user_id)
    return LearningRuntimeControlResultRead(
        run_id=run_id,
        action=data.action,
        status=updated.status,
        state_version=updated.state_version,
        result=result,
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
    release_registry = getattr(readiness, "release_registry", None)
    release_authorization_registry = getattr(
        readiness, "release_authorization_registry", None
    )
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
        capability = _project_learning_runtime_descriptor(
            descriptor,
            release_registry=(
                release_registry
                if isinstance(release_registry, RuntimeCanaryReleaseRegistry)
                else None
            ),
            release_authorization_registry=(
                release_authorization_registry
                if isinstance(
                    release_authorization_registry,
                    RuntimeReleaseAuthorizationRegistry,
                )
                else None
            ),
        )
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


def _require_learning_runtime_operator(
    request: Request, principal: Principal
) -> None:
    if not request.app.state.settings.auth_required:
        return
    if not principal.authenticated or principal.role not in {"teacher", "admin"}:
        raise HTTPException(
            status_code=403,
            detail=(
                "LearningLoop Runtime operator control requires teacher or "
                "admin role"
            ),
        )


def _project_learning_runtime_controls(
    status: LearningRuntimeStatusRead,
) -> LearningRuntimeControlProjectionRead:
    available = set(status.available_controls)
    controls: list[LearningRuntimeControlRead] = []
    for action in _LEARNING_RUNTIME_CONTROL_ACTIONS:
        if action in available:
            controls.append(
                LearningRuntimeControlRead(action=action, available=True)
            )
            continue
        if action in _LEARNING_RUNTIME_UNSUPPORTED_CONTROL_REASONS:
            reason_code, reason = _LEARNING_RUNTIME_UNSUPPORTED_CONTROL_REASONS[
                action
            ]
        else:
            reason_code = "learning_runtime_approval_not_available"
            reason = (
                "LearningLoop Runtime approval is available only while the "
                "checkpoint is waiting for approval"
            )
        controls.append(
            LearningRuntimeControlRead(
                action=action,
                available=False,
                reason_code=reason_code,
                reason=reason,
            )
        )
    return LearningRuntimeControlProjectionRead(
        run_id=status.run_id,
        runtime_id=status.runtime_id,
        run_kind=status.run_kind,
        status=status.status,
        state_version=status.state_version,
        controls=controls,
        available_controls=list(status.available_controls),
    )


async def _reject_learning_runtime_control(
    db: AsyncSession,
    request: Request,
    principal: Principal,
    status: LearningRuntimeStatusRead,
    *,
    action: LearningRuntimeControlAction,
    reason_code: str,
    reason: str,
) -> NoReturn:
    safe_reason = reason.strip()[:500] or "LearningLoop Runtime control was rejected"
    details = {
        "run_id": status.run_id,
        "runtime_id": status.runtime_id,
        "run_kind": status.run_kind,
        "control_scope": status.control_scope,
        "action": action,
        "reason_code": reason_code,
        "reason": safe_reason,
        "status": status.status,
        "state_version": status.state_version,
        "provider_called": False,
    }
    record_audit(
        db,
        request,
        action="learning_runtime.control_rejected",
        actor_account_id=principal.account_id or None,
        target_type="agent_run",
        target_id=status.run_id,
        details=details,
    )
    await db.commit()
    raise ConflictError("LearningLoop Runtime control rejected", details=details)


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
    *,
    release_registry: RuntimeCanaryReleaseRegistry | None,
    release_authorization_registry: RuntimeReleaseAuthorizationRegistry | None,
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

    runtime_plan_version = (
        _descriptor_text(descriptor, "runtime_plan_version") or version
    )
    # The current Agent version must be declared by the capability itself.
    # Never infer it from a release artifact: doing so would allow an old
    # artifact to satisfy the release gate for an otherwise unversioned
    # capability.
    agent_version = _descriptor_text(descriptor, "agent_version") or ""
    (
        structural_release_eligible,
        semantic_release_eligible,
        canary_release_eligible,
        canary_reason,
    ) = _learning_canary_readiness(
        capability_id=capability_id,
        agent_version=agent_version,
        runtime_plan_version=runtime_plan_version,
        release_registry=release_registry,
        release_authorization_registry=release_authorization_registry,
    )

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
        agent_version=agent_version,
        runtime_plan_version=runtime_plan_version,
        structural_release_eligible=structural_release_eligible,
        semantic_release_eligible=semantic_release_eligible,
        canary_release_eligible=canary_release_eligible,
        canary_reason=canary_reason,
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


def _learning_canary_readiness(
    *,
    capability_id: str,
    agent_version: str,
    runtime_plan_version: str,
    release_registry: RuntimeCanaryReleaseRegistry | None,
    release_authorization_registry: RuntimeReleaseAuthorizationRegistry | None,
 ) -> tuple[bool, bool, bool, str]:
    """Project the shared release gate without entering an execution path."""

    if release_registry is None:
        return False, False, False, "canary_release_registry_missing"
    if not agent_version.strip() or not runtime_plan_version.strip():
        return False, False, False, "canary_artifact_version_expectation_missing"

    expected_agent_version = agent_version.strip()
    expected_runtime_plan_version = runtime_plan_version.strip()
    structural_eligible = release_registry.structural_eligible(
        capability_id,
        expected_agent_version=expected_agent_version,
        expected_runtime_plan_version=expected_runtime_plan_version,
    )
    semantic_eligible = release_registry.release_eligible(
        capability_id,
        expected_agent_version=expected_agent_version,
        expected_runtime_plan_version=expected_runtime_plan_version,
    )
    reason = release_registry.reason(
        capability_id,
        expected_agent_version=expected_agent_version,
        expected_runtime_plan_version=expected_runtime_plan_version,
    )
    if semantic_eligible:
        if release_authorization_registry is None:
            reason = "release_authorization_missing"
        else:
            report = release_registry.report(capability_id)
            if report is None:
                reason = "canary_release_evidence_missing"
            else:
                reason = (
                    release_authorization_registry.reason(
                        capability_id,
                        suite_id=report.suite_id,
                        launch_mode="canary",
                        expected_agent_version=expected_agent_version,
                        expected_runtime_plan_version=expected_runtime_plan_version,
                    )
                    or "canary_release_evidence_approved"
                )
    canary_release_eligible = (
        semantic_eligible and reason == "canary_release_evidence_approved"
    )
    return (
        structural_eligible,
        semantic_eligible,
        canary_release_eligible,
        reason,
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
