from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

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
from app.contracts.api import EventRead, TaskRead
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
from app.models import TaskModel, TaskStatus
from app.providers.base import AgentProvider
from app.repositories import FileRepository, TaskRepository
from app.repositories.sessions import SessionRepository
from app.runtime import RuntimePlanProposal
from app.services.answer_disclosure import public_teaching_result
from app.services.auth_service import Principal
from app.services.event_service import append_task_event
from app.services.research_analysis_review import ResearchAnalysisReviewService
from app.services.runtime_plan_proposals import RuntimePlanProposalService
from app.services.scenario_catalog import ScenarioCatalogError
from app.services.session_context import SessionContextService
from app.services.task_control_service import TaskControlService
from app.services.task_creation_service import TaskCreationService
from app.services.task_query_service import TaskQueryService

router = APIRouter(prefix="/tasks", tags=["tasks"])
TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}


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
    try:
        data = request.app.state.scenario_catalog.enrich_legacy_request(data)
    except ScenarioCatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    updates: dict[str, object] = {"user_id": effective_user_id(principal, data.user_id)}
    if principal.has_identity:
        try:
            updates["user_role"] = UserRole(principal.role)
        except ValueError:
            updates["user_role"] = UserRole.STUDENT
    data = data.model_copy(update=updates)
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
    task = await TaskCreationService(
        db, provider.provider_name, request.app.state.settings
    ).create_queued(data, route=decision)
    if task.status == TaskStatus.QUEUED:
        request.app.state.task_executor.submit(task.id)
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
    request.app.state.task_runner.submit(task.id)
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
    request.app.state.task_runner.submit(task.id)
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
    approval_actor = _require_runtime_approval(request, principal)
    await _get_runtime_approval_task(db, task_id, principal)
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
        request.app.state.task_runner.submit(task.id)
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
    request.app.state.task_runner.submit(task.id)
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
    request.app.state.task_runner.submit(task.id)
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
    approval_actor = _require_runtime_approval(request, principal)
    await _get_runtime_approval_task(db, task_id, principal)
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
    request.app.state.task_runner.submit(task.id)
    return task_read(task)


async def _get_owned_task(
    db: AsyncSession, task_id: str, principal: Principal
) -> TaskModel:
    task = await TaskQueryService(db).get(task_id)
    if principal.has_identity and task.user_id != principal.user_id:
        raise NotFoundError("任务不存在")
    return task


def _require_runtime_approval(
    request: Request, principal: Principal
) -> tuple[str, str]:
    """Return the existing Principal identity allowed to approve Runtime work."""

    if not principal.authenticated:
        if request.app.state.settings.auth_required:
            raise AuthenticationRequiredError(
                "Runtime approval requires authentication"
            )
        if principal.has_identity:
            raise HTTPException(
                status_code=403,
                detail="Runtime approval requires a teacher or administrator",
            )
        return "anonymous", "anonymous"
    if principal.role not in {"teacher", "admin"}:
        raise HTTPException(
            status_code=403,
            detail="Runtime approval requires a teacher or administrator",
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
    while not await request.is_disconnected():
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
