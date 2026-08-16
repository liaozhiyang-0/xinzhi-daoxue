from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Literal, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import (
    AgentEventType,
    AgentRequest,
    RuntimeApprovalAudit,
    RuntimeApprovalSubmission,
    RuntimeInputSubmission,
    RuntimePlanProposalDecisionSubmission,
    RuntimeReconciliationSubmission,
    UserRole,
)
from app.contracts.api import (
    EventRead,
    TaskRead,
    TaskRuntimeControlProjectionRead,
    TaskRuntimeControlRead,
    TaskRuntimePlanProposalRead,
)
from app.contracts.conversation import ConversationContextBundle
from app.contracts.research_analysis import (
    ResearchReviewDecision,
    ResearchReviewSubmission,
)
from app.core.errors import AuthenticationRequiredError, NotFoundError
from app.dependencies import (
    effective_user_id,
    get_current_principal,
    get_db,
    get_provider,
)
from app.models import AgentRunModel, TaskModel, TaskStatus
from app.providers.base import AgentProvider
from app.repositories import (
    AgentRunRepository,
    FileRepository,
    RuntimePlanProposalRepository,
    TaskRepository,
)
from app.repositories.sessions import SessionRepository
from app.runtime import RuntimePlanProposal
from app.services.answer_disclosure import public_teaching_result
from app.services.auth_service import Principal
from app.services.event_service import append_task_event
from app.services.intent_recognition import IntentRecognitionService
from app.services.research_analysis_review import ResearchAnalysisReviewService
from app.services.runtime_control_policy import control_policy_for_runtime_kind
from app.services.runtime_plan_proposals import RuntimePlanProposalService
from app.services.scenario_catalog import ScenarioCatalogError
from app.services.session_context import SessionContextService
from app.services.task_control_service import RETRYABLE_FAILURES, TaskControlService
from app.services.task_creation_service import TaskCreationService
from app.services.task_query_service import TaskQueryService

router = APIRouter(prefix="/tasks", tags=["tasks"])
TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}
TaskRuntimeControlAction = Literal["pause", "resume", "approve", "input"]
_TASK_RUNTIME_CONTROL_ACTIONS: tuple[TaskRuntimeControlAction, ...] = (
    "pause",
    "resume",
    "approve",
    "input",
)
_RESEARCH_RUNTIME_APPROVAL_AGENT_IDS = frozenset(
    {
        "RESEARCH_01_ACADEMIC_SEARCH_V1",
        "RESEARCH_02_ACADEMIC_WRITING_V1",
    }
)

_AUTO_SCENARIO_BY_INTENT = {
    "lesson_prep": "faculty_course_copilot_v1",
    "assignment_review": "assessment_diagnosis_v1",
    "learning_advice": "student_learning_path_v1",
    "academic_search": "research_frontier_radar_v1",
}


def _bind_auto_scenario(data: AgentRequest) -> AgentRequest:
    """Attach a bounded showcase contract when the user did not choose one.

    The workspace normally supplies ``scenario_id`` for showcase buttons, but
    pasted or bookmarked prompts must receive the same contract.  Only the
    recognizer's high-confidence business intents are eligible; ordinary
    questions stay on the normal route.
    """

    if data.scenario_id:
        return data
    recognizer = IntentRecognitionService()
    recognition = recognizer.recognize(data)
    intent = recognition.intent
    if intent == "summarize_knowledge" and recognizer.is_knowledge_governance(
        data.input_text()
    ):
        scenario_id: str | None = "department_knowledge_governance_v1"
    else:
        scenario_id = _AUTO_SCENARIO_BY_INTENT.get(intent)
    if not scenario_id:
        return data
    return data.model_copy(update={"scenario_id": scenario_id})


def task_read(
    task: TaskModel,
    *,
    requester_user_id: str | None = None,
) -> TaskRead:
    if requester_user_id is not None and task.user_id != requester_user_id:
        raise NotFoundError("任务不存在")
    model = TaskRead.model_validate(task)
    payload = dict(model.input_content)
    options = dict(payload.get("options") or {})
    for key in (
        "conversation_context",
        "recent_messages",
        "active_memories",
        "working_state",
    ):
        options.pop(key, None)
    v2_options = options.get("research_analysis_v2")
    if isinstance(v2_options, dict):
        v2_request = v2_options.get("request")
        design = v2_request.get("design") if isinstance(v2_request, dict) else ""
        options["research_analysis_v2"] = {
            "enabled": True,
            "execute": bool(v2_options.get("execute", False)),
            "design": str(design or ""),
        }
    payload["options"] = options
    model.input_content = payload
    model.result_content = public_teaching_result(
        model.result_content,
        include_private_teaching=requester_user_id == task.user_id,
    )
    model.retryable = bool(
        task.status == TaskStatus.FAILED
        and task.failure_category in RETRYABLE_FAILURES
        and task.attempt < task.max_attempts
    )
    artifacts = task.__dict__.get("artifacts")
    model.artifact_ids = [artifact.id for artifact in artifacts or []]
    return model


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建非阻塞任务",
)
async def create_task(
    data: AgentRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    updates: dict[str, object] = {"user_id": effective_user_id(principal, data.user_id)}
    if principal.has_identity:
        try:
            updates["user_role"] = UserRole(principal.role)
        except ValueError:
            updates["user_role"] = UserRole.STUDENT
    data = data.model_copy(update=updates)
    data = _bind_auto_scenario(data)
    if (
        data.intent.value == "data_analysis"
        and not request.app.state.settings.data_analysis_enabled
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="数据分析功能当前已冻结，暂不接受新任务；已有任务和数据未被修改。",
        )
    # Bind scenarios after principal attribution so a transient request role
    # cannot affect scenario selection before the Task boundary normalizes it.
    try:
        data = request.app.state.scenario_catalog.enrich_legacy_request(data)
    except ScenarioCatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    data = await _hydrate_document_attachments(data, principal, db, request)
    session = await SessionRepository(db).get_for_user(data.session_id, data.user_id)
    if session is not None:
        # Routing must see the durable session continuity state.  Previously
        # this projection happened only inside TaskCreationService, after the
        # route had already been selected, so short follow-ups lost the prior
        # agent and external-evidence context.
        data = SessionContextService(request.app.state.settings).apply(session, data)
        bundle = await request.app.state.context_assembly.assemble(
            db,
            session_id=data.session_id,
            user_id=data.user_id,
            current_message_id=None,
            course_id=(
                session.course_id
                if data.course_id.upper() in {"", "AUTO", "UNKNOWN"}
                else data.course_id
            ),
            task_family=data.intent.value,
            agent_id="router",
        )
        data = _with_conversation_context(data, bundle)
    decision = request.app.state.task_router.route(data)
    if (
        decision.agent_id == "RESEARCH_03_DATA_ANALYSIS_V1"
        and not request.app.state.settings.data_analysis_enabled
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="数据分析功能当前已冻结，暂不接受新任务；已有任务和数据未被修改。",
        )
    task = await TaskCreationService(
        db, provider.provider_name, request.app.state.settings
    ).create_queued(data, route=decision)
    if task.status == TaskStatus.QUEUED:
        await request.app.state.task_executor.submit(task.id)
    return task_read(task, requester_user_id=data.user_id)


async def _hydrate_document_attachments(
    data: AgentRequest,
    principal: Principal,
    db: AsyncSession,
    request: Request,
) -> AgentRequest:
    if not data.attachments:
        return data
    if len(data.attachments) > request.app.state.settings.document_max_files_per_task:
        raise HTTPException(
            status_code=422,
            detail=(
                "一次最多上传 "
                f"{request.app.state.settings.document_max_files_per_task} 个文件"
            ),
        )
    repository = FileRepository(db)
    hydrated = []
    extracted_blocks: list[str] = []
    for attachment in data.attachments:
        model = await repository.get(attachment.file_id)
        if model is None or (
            principal.has_identity and model.owner_user_id != principal.user_id
        ):
            raise HTTPException(status_code=404, detail="附件不存在")
        if model.ingestion_status in {"pending", "processing"}:
            raise HTTPException(
                status_code=409, detail=f"附件仍在解析中: {model.filename}"
            )
        if model.ingestion_status == "failed":
            raise HTTPException(
                status_code=422,
                detail=model.extraction_error or f"附件解析失败: {model.filename}",
            )
        updated = attachment.model_copy(
            update={
                "ingestion_status": str(model.ingestion_status),
                "page_count": model.page_count,
                "extracted_text": model.extracted_text[:200_000],
                "extraction_metadata": model.extraction_metadata or {},
            }
        )
        hydrated.append(updated)
        if model.extracted_text.strip():
            extracted_blocks.append(
                f"【附件：{model.filename}】\n{model.extracted_text.strip()}"
            )
    if not extracted_blocks:
        return data.model_copy(update={"attachments": hydrated})
    canonical = dict(data.canonical_input)
    original_text = str(
        canonical.get("text") or canonical.get("question") or ""
    ).strip()
    combined = "\n\n".join(
        part for part in (original_text, "\n\n".join(extracted_blocks)) if part
    )
    canonical["text"] = combined[
        : request.app.state.settings.document_max_extracted_chars
    ]
    canonical["uploaded_text"] = "\n\n".join(extracted_blocks)[
        : request.app.state.settings.document_max_extracted_chars
    ]
    return data.model_copy(
        update={"attachments": hydrated, "canonical_input": canonical}
    )


def _with_conversation_context(
    data: AgentRequest, bundle: ConversationContextBundle
) -> AgentRequest:
    options = dict(data.options)
    options.update(
        {
            "conversation_context": bundle.model_dump(mode="json"),
            "conversation_summary": bundle.safe_prompt_text(),
            "recent_messages": [
                item.model_dump(mode="json") for item in bundle.recent_messages[-6:]
            ],
            "active_memories": list(bundle.active_memories),
            "working_state": bundle.working_state.model_dump(mode="json"),
            "context_cache_status": bundle.cache_status,
        }
    )
    return data.model_copy(update={"options": options})


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: str,
    principal: Principal = Depends(get_current_principal),
    user_id: str | None = Query(default=None, min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    return task_read(
        await TaskQueryService(db).get(task_id),
        requester_user_id=effective_user_id(principal, user_id) or None,
    )


@router.post(
    "/{task_id}/research-review",
    response_model=ResearchReviewDecision,
    summary="提交科研分析人工复核签字",
)
async def submit_research_review(
    task_id: str,
    submission: ResearchReviewSubmission,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ResearchReviewDecision:
    if principal.has_identity and principal.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="只有教师或管理员可以提交科研复核")
    if principal.has_identity and submission.reviewer_id != principal.user_id:
        raise HTTPException(status_code=403, detail="复核人必须与当前认证身份一致")
    if request.app.state.settings.auth_required and not principal.has_identity:
        raise HTTPException(status_code=403, detail="科研复核需要已认证身份")
    task = await _get_owned_task(db, task_id, principal)
    if task.agent_id != "RESEARCH_03_DATA_ANALYSIS_V1":
        raise HTTPException(status_code=422, detail="任务不是科研数据分析任务")
    payload = dict(task.result_content or {})
    structured = payload.get("structured_result")
    if not isinstance(structured, dict) or not structured.get("analysis_v2"):
        raise HTTPException(status_code=422, detail="任务没有可复核的科研分析 V2 结果")
    business_data = payload.get("business_data")
    if not isinstance(business_data, dict) or business_data.get("status") != "executed":
        raise HTTPException(status_code=422, detail="只有已执行的科研分析结果可以签字")
    existing_checklist = business_data.get("review_checklist")
    if not isinstance(existing_checklist, dict):
        raise HTTPException(status_code=422, detail="科研分析结果缺少复核清单")
    expected_items = existing_checklist.get("items")
    if not isinstance(expected_items, list):
        raise HTTPException(status_code=422, detail="科研分析复核清单格式无效")
    expected_by_id = {
        str(item.get("review_id")): item
        for item in expected_items
        if isinstance(item, dict)
    }
    submitted_by_id = {item.review_id: item for item in submission.items}
    if set(expected_by_id) != set(submitted_by_id):
        raise HTTPException(status_code=422, detail="提交的复核项必须完整匹配任务清单")
    for review_id, expected in expected_by_id.items():
        submitted = submitted_by_id[review_id]
        if (
            submitted.category != expected.get("category")
            or submitted.question != expected.get("question")
        ):
            raise HTTPException(status_code=422, detail="复核项内容不能脱离原始清单")
    decision = ResearchAnalysisReviewService().persist_submission(
        request.app.state.settings.research_analysis_artifact_root,
        task_id,
        submission,
    )
    payload["research_review_decision"] = decision.model_dump(mode="json")
    task.result_content = payload
    await db.commit()
    return decision


@router.get(
    "/{task_id}/research-review",
    response_model=ResearchReviewDecision,
    summary="读取科研分析人工复核签字",
)
async def get_research_review(
    task_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ResearchReviewDecision:
    await _get_owned_task(db, task_id, principal)
    decision = ResearchAnalysisReviewService.load_decision(
        request.app.state.settings.research_analysis_artifact_root,
        task_id,
    )
    if decision is None:
        raise HTTPException(status_code=404, detail="科研复核签字尚未提交")
    return decision


@router.get("/{task_id}/events", response_model=list[EventRead])
async def get_task_events(
    task_id: str,
    principal: Principal = Depends(get_current_principal),
    after: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[EventRead]:
    if principal.has_identity:
        await _get_owned_task(db, task_id, principal)
    events = await TaskQueryService(db).list_events(task_id, after=after)
    return [EventRead.model_validate(event) for event in events]


@router.get(
    "/{task_id}/runtime-controls",
    response_model=TaskRuntimeControlProjectionRead,
    summary="Read redacted Runtime controls for a task",
)
async def task_runtime_controls(
    task_id: str,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TaskRuntimeControlProjectionRead:
    """Return only the state-aware task controls available to its owner.

    The normal workspace must not scrape the debug execution endpoint for
    checkpoint details. This projection is intentionally small and performs
    no Runtime mutation or Provider call.
    """

    # Runtime approval is a reviewer operation.  Teachers/admins may review
    # a learner-owned task, matching the approval endpoint's authorization
    # boundary; task owners retain the normal self-service projection.
    task = await _get_runtime_control_task(db, task_id, principal)
    runtime = await AgentRunRepository(db).get_for_task(task.id)
    plan_proposal = None
    if runtime is not None:
        proposal_id = (runtime.control_data or {}).get("plan_proposal_id")
        if isinstance(proposal_id, str) and proposal_id:
            candidate = await RuntimePlanProposalRepository(db).get(proposal_id)
            if (
                candidate is not None
                and candidate.task_id == task.id
                and candidate.run_id == runtime.id
                and candidate.status == "pending"
            ):
                plan_proposal = candidate
    return _project_task_runtime_controls(
        task.id,
        runtime,
        plan_proposal=plan_proposal,
    )


@router.post(
    "/{task_id}/retry",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_task(
    task_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    await _get_owned_task(db, task_id, principal)
    task = await TaskControlService(db, provider, request.app.state.settings).retry(
        task_id
    )
    await request.app.state.task_executor.submit(task.id)
    return task_read(task)


@router.post("/{task_id}/cancel", response_model=TaskRead)
async def cancel_task(
    task_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    await _get_owned_task(db, task_id, principal)
    return task_read(
        await TaskControlService(db, provider, request.app.state.settings).cancel(
            task_id
        )
    )


@router.post("/{task_id}/pause", response_model=TaskRead)
async def pause_task(
    task_id: str,
    request: Request,
    runtime_run_id: str | None = Query(default=None, max_length=64),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    await _get_owned_task(db, task_id, principal)
    return task_read(
        await TaskControlService(db, provider, request.app.state.settings).pause(
            task_id,
            runtime_run_id=runtime_run_id,
        )
    )


@router.post("/{task_id}/resume", response_model=TaskRead)
async def resume_task(
    task_id: str,
    request: Request,
    runtime_run_id: str | None = Query(default=None, max_length=64),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    await _get_owned_task(db, task_id, principal)
    task = await TaskControlService(
        db, provider, request.app.state.settings
    ).resume(task_id, runtime_run_id=runtime_run_id)
    await request.app.state.task_executor.submit(task.id)
    return task_read(task)


@router.post("/{task_id}/approve", response_model=TaskRead)
async def approve_task(
    task_id: str,
    request: Request,
    submission: RuntimeApprovalSubmission | None = None,
    runtime_run_id: str | None = Query(default=None, max_length=64),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    approval_task = await _get_runtime_approval_task(db, task_id, principal)
    approval_actor = _require_runtime_approval(request, principal, approval_task)
    task = await TaskControlService(
        db, provider, request.app.state.settings
    ).approve(
        task_id,
        runtime_run_id=runtime_run_id,
        approver_id=approval_actor[0],
        approver_role=approval_actor[1],
        submission=submission,
    )
    if task.status == TaskStatus.QUEUED:
        await request.app.state.task_executor.submit(task.id)
    return task_read(task)


@router.post("/{task_id}/input", response_model=TaskRead)
async def submit_runtime_input(
    task_id: str,
    submission: RuntimeInputSubmission,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    await _get_owned_task(db, task_id, principal)
    task = await TaskControlService(
        db, provider, request.app.state.settings
    ).submit_input(task_id, submission)
    await request.app.state.task_executor.submit(task.id)
    return task_read(task)


@router.post("/{task_id}/reconcile", response_model=TaskRead)
async def reconcile_runtime_node(
    task_id: str,
    submission: RuntimeReconciliationSubmission,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    await _get_owned_task(db, task_id, principal)
    task = await TaskControlService(
        db, provider, request.app.state.settings
    ).reconcile(task_id, submission)
    await request.app.state.task_executor.submit(task.id)
    return task_read(task)


@router.get(
    "/{task_id}/runtime-plan-proposals",
    response_model=list[RuntimePlanProposal],
)
async def list_runtime_plan_proposals(
    task_id: str,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[RuntimePlanProposal]:
    await _get_owned_task(db, task_id, principal)
    return await RuntimePlanProposalService(db).list(task_id)


@router.post(
    "/{task_id}/runtime-plan-proposals/{proposal_id}/decision",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def decide_runtime_plan_proposal(
    task_id: str,
    proposal_id: str,
    submission: RuntimePlanProposalDecisionSubmission,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    approval_task = await _get_runtime_approval_task(db, task_id, principal)
    approval_actor = _require_runtime_approval(request, principal, approval_task)
    proposals = await RuntimePlanProposalService(db).list(task_id)
    proposal = next(
        (item for item in proposals if item.proposal_id == proposal_id),
        None,
    )
    if proposal is None:
        raise NotFoundError("plan proposal not found")
    approval_audit = RuntimeApprovalAudit(
        decision=submission.decision,
        approver_id=approval_actor[0],
        approver_role=approval_actor[1],
        scope="runtime.plan_proposal",
        state_version=proposal.state_version,
    )
    task = await RuntimePlanProposalService(db).decide(
        task_id,
        proposal_id,
        approved=submission.decision == "approved",
        reason=submission.reason,
        expected_state_version=submission.expected_state_version,
    )
    await append_task_event(
        db,
        task.id,
        AgentEventType.AGENT_PROGRESS,
        agent_id=task.agent_id,
        data={
            "stage_id": "runtime_approval",
            "status": f"{submission.decision}_submitted",
            "proposal_id": proposal_id,
            **approval_audit.model_dump(mode="json"),
            "approval": approval_audit.model_dump(mode="json"),
        },
    )
    await db.commit()
    await request.app.state.task_executor.submit(task.id)
    return task_read(task)


def _project_task_runtime_controls(
    task_id: str,
    runtime: AgentRunModel | None,
    *,
    plan_proposal: object | None = None,
) -> TaskRuntimeControlProjectionRead:
    """Return a fail-closed, checkpoint-free task control projection."""

    if runtime is None:
        return TaskRuntimeControlProjectionRead(
            task_id=task_id,
            controls=[
                TaskRuntimeControlRead(
                    action=action,
                    available=False,
                    reason_code="runtime_not_started",
                    reason="This task has no controllable Runtime run.",
                )
                for action in _TASK_RUNTIME_CONTROL_ACTIONS
            ],
        )

    proposal_projection = None
    if plan_proposal is not None:
        proposal_projection = TaskRuntimePlanProposalRead(
            proposal_id=str(getattr(plan_proposal, "id", "")),
            status=cast(
                Literal["pending", "approved", "rejected", "applied"],
                str(getattr(plan_proposal, "status", "pending")),
            ),
            state_version=int(getattr(plan_proposal, "state_version", 0)),
            base_iteration=int(getattr(plan_proposal, "base_iteration", 0)),
            target_iteration=int(getattr(plan_proposal, "target_iteration", 1)),
            reason_codes=list(getattr(plan_proposal, "reason_codes", []) or []),
            affected_node_ids=list(
                getattr(plan_proposal, "affected_node_ids", []) or []
            ),
        )
        controls = [
            TaskRuntimeControlRead(
                action=action,
                available=False,
                reason_code="runtime_plan_proposal_requires_explicit_decision",
                reason=(
                    "A pending Runtime plan proposal must be approved or "
                    "rejected through the explicit plan-proposal decision API."
                ),
            )
            for action in _TASK_RUNTIME_CONTROL_ACTIONS
        ]
    else:
        policy = control_policy_for_runtime_kind(runtime.run_kind)
        available = set(policy.available_controls(runtime.status))
        if runtime.control_request:
            available.discard("pause")

        controls = [
            TaskRuntimeControlRead(
                action=action,
                available=action in available,
                reason_code=(
                    ""
                    if action in available
                    else _task_runtime_control_reason_code(
                        action,
                        runtime_status=runtime.status,
                        control_request=runtime.control_request,
                        declared_controls=policy.declared_controls,
                    )
                ),
                reason=(
                    ""
                    if action in available
                    else _task_runtime_control_reason(
                        action,
                        runtime_status=runtime.status,
                        control_request=runtime.control_request,
                        declared_controls=policy.declared_controls,
                    )
                ),
            )
            for action in _TASK_RUNTIME_CONTROL_ACTIONS
        ]
    return TaskRuntimeControlProjectionRead(
        task_id=task_id,
        runtime_run_id=runtime.id,
        run_kind=runtime.run_kind,
        status=runtime.status,
        state_version=runtime.state_version,
        control_request=runtime.control_request,
        control_scope=(
            "runtime_plan_proposal"
            if proposal_projection is not None
            else "runtime"
        ),
        plan_proposal=proposal_projection,
        controls=controls,
    )


def _task_runtime_control_reason_code(
    action: str,
    *,
    runtime_status: str,
    control_request: str,
    declared_controls: tuple[str, ...],
) -> str:
    if action not in declared_controls:
        return "runtime_control_not_supported"
    if action == "pause" and control_request:
        return "runtime_control_pending"
    if runtime_status in {"completed", "failed", "cancelled"}:
        return "runtime_terminal"
    return "runtime_control_not_available_for_status"


def _task_runtime_control_reason(
    action: str,
    *,
    runtime_status: str,
    control_request: str,
    declared_controls: tuple[str, ...],
) -> str:
    code = _task_runtime_control_reason_code(
        action,
        runtime_status=runtime_status,
        control_request=control_request,
        declared_controls=declared_controls,
    )
    messages = {
        "runtime_control_not_supported": "This Runtime does not declare this control.",
        "runtime_control_pending": "A Runtime control request is already pending.",
        "runtime_terminal": "Terminal Runtime runs cannot be controlled.",
        "runtime_control_not_available_for_status": (
            "This action is not available for the current Runtime status."
        ),
    }
    return messages[code]


async def _get_owned_task(
    db: AsyncSession, task_id: str, principal: Principal
) -> TaskModel:
    task = await TaskQueryService(db).get(task_id)
    if principal.has_identity and task.user_id != principal.user_id:
        raise NotFoundError("任务不存在")
    return task


async def _get_runtime_control_task(
    db: AsyncSession, task_id: str, principal: Principal
) -> TaskModel:
    if principal.authenticated and principal.role in {"teacher", "admin"}:
        return await TaskQueryService(db).get(task_id)
    return await _get_owned_task(db, task_id, principal)


def _require_runtime_approval(
    request: Request,
    principal: Principal,
    task: TaskModel | None = None,
) -> tuple[str, str]:
    """Return the Principal identity allowed to approve this Runtime work."""

    if not principal.authenticated:
        if request.app.state.settings.auth_required:
            raise AuthenticationRequiredError(
                "Runtime approval requires authentication"
            )
        if principal.has_identity:
            raise HTTPException(
                status_code=403,
                detail="Runtime approval requires an authorized reviewer",
            )
        return "anonymous", "anonymous"
    research_reviewer = (
        principal.role == "researcher"
        and task is not None
        and task.agent_id in _RESEARCH_RUNTIME_APPROVAL_AGENT_IDS
    )
    if principal.role not in {"teacher", "admin"} and not research_reviewer:
        raise HTTPException(
            status_code=403,
            detail="Runtime approval is not permitted for this role or Agent",
        )
    return principal.user_id or principal.account_id, principal.role


async def _get_runtime_approval_task(
    db: AsyncSession, task_id: str, principal: Principal
) -> TaskModel:
    if principal.authenticated and principal.role in {"teacher", "admin"}:
        return await TaskQueryService(db).get(task_id)
    return await _get_owned_task(db, task_id, principal)


async def event_stream(
    request: Request,
    task_id: str,
    *,
    cursor: int,
) -> AsyncGenerator[str, None]:
    heartbeat_seconds = request.app.state.settings.sse_heartbeat_seconds
    while True:
        async with request.app.state.session_factory() as db:
            repository = TaskRepository(db)
            task = await repository.get(task_id)
            if task is None:
                return
            events = await repository.list_events(task_id, after=cursor)
            for event in events:
                cursor = event.sequence
                payload = json.dumps(event.event_data, ensure_ascii=False)
                yield (
                    f"id: {event.sequence}\n"
                    f"event: {event.event_type}\n"
                    f"data: {payload}\n\n"
                )
            if task.status in TERMINAL_STATUSES:
                return
        # A completed Task must close its historical SSE response without
        # waiting on a client-disconnect probe. In-process ASGI clients can
        # keep that probe pending after the request body is exhausted, which
        # otherwise leaves terminal event replay open indefinitely.
        if await request.is_disconnected():
            return
        if not events:
            yield ": heartbeat\n\n"
            await asyncio.sleep(heartbeat_seconds)


@router.get(
    "/{task_id}/stream",
    summary="按 sequence 推送任务事件，支持 Last-Event-ID 重连",
)
async def stream_task(
    request: Request,
    task_id: str,
    principal: Principal = Depends(get_current_principal),
    after: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    cursor = after
    if last_event_id is not None:
        try:
            cursor = max(0, int(last_event_id))
        except ValueError:
            cursor = after
    async with request.app.state.session_factory() as db:
        await _get_owned_task(db, task_id, principal)
    return StreamingResponse(
        event_stream(request, task_id, cursor=cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
