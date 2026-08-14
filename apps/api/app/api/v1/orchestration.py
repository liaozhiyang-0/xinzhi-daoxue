from __future__ import annotations

import importlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import (
    AgentRequestV2,
    AgentResponse,
    AttachmentRef,
    ChatSubmission,
    Citation,
    CourseCode,
    ExecutionMode,
    ExecutionStatus,
    OrchestrationIntent,
    TaskFamily,
    WorkflowStatus,
)
from app.contracts.api import SessionCreate
from app.core.internal_workflows import (
    WORKFLOW_INTERNAL_AGENT_MAP,
    internal_workflow_models_configured,
)
from app.dependencies import (
    effective_user_id,
    get_current_principal,
    get_db,
    get_provider,
)
from app.models import TaskStatus
from app.providers.base import AgentProvider
from app.repositories import FileRepository, SessionRepository, TaskRepository
from app.services.auth_service import Principal
from app.services.scenario_catalog import ScenarioCatalogError
from app.services.session_service import SessionService
from app.services.task_creation_service import TaskCreationService

from .tasks import event_stream

router = APIRouter(tags=["orchestration"])

WORKFLOW_MODES: dict[str, ExecutionMode] = {
    "GENERAL_QUESTION_V1": ExecutionMode.LOCAL,
    "GENERAL_MODEL_FALLBACK_V1": ExecutionMode.LOCAL,
    "ROUTER_01_FALLBACK_V1": ExecutionMode.HYBRID,
    "LEARN_01_KNOWLEDGE_QA_V1": ExecutionMode.HYBRID,
    "ACADEMIC_PROBLEM_SOLVER": ExecutionMode.LOCAL,
    "SOLVER_CT_V1": ExecutionMode.HYBRID,
    "TEACH_01_LESSON_PREP_V1": ExecutionMode.HYBRID,
    "TEACH_02_ASSIGNMENT_REVIEW_V1": ExecutionMode.HYBRID,
    "RESEARCH_02_ACADEMIC_WRITING_V1": ExecutionMode.HYBRID,
    "RESEARCH_03_DATA_ANALYSIS_V1": ExecutionMode.HYBRID,
}


def _local_handler_available(path: str) -> bool:
    if not path or "." not in path:
        return False
    module_name, attribute = path.rsplit(".", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return False
    return hasattr(module, attribute)


async def _attachments(
    db: AsyncSession, payload: AgentRequestV2, principal: Principal
) -> list[AttachmentRef]:
    values: list[AttachmentRef] = []
    repository = FileRepository(db)
    for item in payload.files:
        model = await repository.get(item.file_id)
        if model is None:
            raise HTTPException(status_code=404, detail=f"附件不存在: {item.file_id}")
        if principal.has_identity and model.owner_user_id != principal.user_id:
            raise HTTPException(status_code=404, detail=f"附件不存在: {item.file_id}")
        if model.ingestion_status in {"pending", "processing"}:
            raise HTTPException(
                status_code=409, detail=f"附件仍在解析中: {model.filename}"
            )
        if model.ingestion_status == "failed":
            raise HTTPException(
                status_code=422,
                detail=model.extraction_error or f"附件解析失败: {model.filename}",
            )
        values.append(
            AttachmentRef(
                file_id=model.id,
                filename=model.filename,
                content_type=model.content_type,
                size_bytes=model.size_bytes,
                storage_key=model.storage_key,
                checksum_sha256=model.checksum_sha256,
                ingestion_status=str(model.ingestion_status),
                page_count=model.page_count,
                extracted_text=model.extracted_text[:200_000],
                extraction_metadata=model.extraction_metadata or {},
            )
        )
    return values


async def _submit(
    payload: AgentRequestV2,
    request: Request,
    db: AsyncSession,
    provider: AgentProvider,
    principal: Principal,
) -> tuple[Any, ChatSubmission]:
    user_id = effective_user_id(principal, payload.user_id) or "local-user"
    try:
        prepared_payload = request.app.state.scenario_catalog.enrich_request(payload)
    except ScenarioCatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.session_id:
        session = await SessionRepository(db).get(payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        session_id = session.id
    else:
        session = await SessionService(db).create(
            SessionCreate(
                user_id=user_id,
                course_id=(payload.course_hint or CourseCode.UNKNOWN).value,
                title=payload.message[:60],
            )
        )
        session_id = session.id
    attachment_refs = await _attachments(db, prepared_payload, principal)
    document_blocks = [
        f"【附件：{item.filename}】\n{item.extracted_text.strip()}"
        for item in attachment_refs
        if item.extracted_text.strip()
    ]
    if document_blocks:
        combined = "\n\n".join(document_blocks)
        message = "\n\n".join(
            part for part in (prepared_payload.message.strip(), combined) if part
        )
        prepared_payload = prepared_payload.model_copy(
            update={
                "message": message[
                    : request.app.state.settings.document_max_extracted_chars
                ]
            }
        )
    context = dict(getattr(session, "context_data", {}) or {})
    prepared = request.app.state.supervisor.prepare(
        prepared_payload,
        session_id=session_id,
        user_id=user_id,
        attachments=attachment_refs,
        session_context=context,
    )
    task = await TaskCreationService(
        db, provider.provider_name, request.app.state.settings
    ).create_queued(prepared.request, route=prepared.route)
    if task.status == TaskStatus.QUEUED:
        await request.app.state.task_executor.submit(task.id)
    submission = ChatSubmission(
        request_id=payload.request_id,
        session_id=session_id,
        task_id=task.id,
        trace_id=prepared.state["trace_id"],
        scenario_id=prepared_payload.scenario_id,
        status=task.status.value,
        stream_url=f"/api/v1/tasks/{task.id}/stream",
        result_url=f"/api/v1/chat/{task.id}",
    )
    return task, submission


@router.post(
    "/chat",
    response_model=ChatSubmission,
    status_code=status.HTTP_202_ACCEPTED,
    summary="通过本地 Supervisor 创建非阻塞对话任务",
)
async def create_chat(
    payload: AgentRequestV2,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> ChatSubmission:
    _, submission = await _submit(payload, request, db, provider, principal)
    return submission


@router.post("/chat/stream", summary="创建对话任务并通过 SSE 推送既有任务事件")
async def stream_chat(
    payload: AgentRequestV2,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> StreamingResponse:
    task, _ = await _submit(payload, request, db, provider, principal)
    return StreamingResponse(
        event_stream(request, task.id, cursor=0),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _citation(source_ref: str, index: int) -> Citation:
    path = source_ref.split("/", 1)[-1]
    filename = path.rsplit("/", 1)[-1] if path else source_ref
    return Citation(
        citation_id=f"S{index}",
        filename=filename,
        source_ref=source_ref,
    )


@router.get("/chat/{task_id}", response_model=AgentResponse)
async def get_chat_result(
    task_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> AgentResponse:
    async with request.app.state.session_factory() as db:
        task = await TaskRepository(db).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if principal.has_identity and task.user_id != principal.user_id:
        raise HTTPException(status_code=404, detail="任务不存在")
    result = dict(task.result_content or {})
    if task.status == TaskStatus.FAILED:
        execution_status = ExecutionStatus.FAILED
    elif task.status == TaskStatus.COMPLETED:
        execution_status = (
            ExecutionStatus.PARTIAL
            if result.get("fallback_used") or result.get("warnings")
            else ExecutionStatus.SUCCESS
        )
    else:
        execution_status = ExecutionStatus.PARTIAL
    try:
        course = CourseCode(task.course_id)
    except ValueError:
        course = CourseCode.UNKNOWN
    try:
        intent = OrchestrationIntent(task.intent)
    except ValueError:
        intent = OrchestrationIntent.UNKNOWN
    metrics = result.get("metrics", {})
    citations = [
        _citation(str(item), index)
        for index, item in enumerate(result.get("citations", []), start=1)
    ]
    return AgentResponse(
        request_id=str(result.get("request_id", task.id)),
        session_id=task.session_id,
        status=execution_status,
        agent_id=task.agent_id,
        course=course,
        intent=intent,
        answer_text=str(result.get("answer", task.error_message or "")),
        math_content=result.get("math_content"),
        structured_result=dict(result.get("structured_result", {})),
        citations=citations,
        assumptions=[str(item) for item in result.get("assumptions", [])],
        warnings=[str(item) for item in result.get("warnings", [])],
        confidence=float(result.get("confidence") or 0),
        trace_id=str(result.get("trace_id", "")),
        elapsed_ms=int(metrics.get("latency_ms") or 0),
    )


@router.get("/capabilities", response_model=dict[str, Any])
async def capabilities(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    internal = request.app.state.internal_agent_execution
    return {
        "supervisor": "XZD_SUPERVISOR",
        "courses": [item.value for item in CourseCode],
        "task_families": [item.value for item in TaskFamily],
        "intents": [item.value for item in OrchestrationIntent],
        "input_types": ["text", "image", "pdf", "mixed"],
        "local_knowledge_qa": settings.enable_local_knowledge_qa,
        "academic_problem_solver": internal.available("ACADEMIC_PROBLEM_SOLVER"),
        "course_packs": [
            item.summary() for item in request.app.state.course_registry.list_packs()
        ],
        "capability_packs": [
            {
                "capability_id": item.capability_id,
                "display_name": item.display_name,
                "tool_ids": list(item.tool_ids),
            }
            for item in request.app.state.capability_registry.list_capabilities()
        ],
        "tools": [
            {
                "tool_id": item.tool_id,
                "enabled": item.enabled,
                "deterministic": item.deterministic,
                "requires_sandbox": item.requires_sandbox,
            }
            for item in request.app.state.tool_registry.list_tools()
        ],
        "future_agent_slots": [
            "LEARN_PATH_PLANNER",
            "LEARN_EXERCISE_GENERATOR",
            "LEARN_ERROR_DIAGNOSIS",
            "LEARN_STUDY_COMPANION",
            "TEACH_QUESTION_GENERATOR",
            "TEACH_RUBRIC_BUILDER",
            "TEACH_LEARNING_ANALYTICS",
            "TEACH_CLASS_DIAGNOSIS",
            "RESEARCH_LITERATURE_REVIEW",
            "RESEARCH_EVIDENCE_AUDIT",
            "RESEARCH_FIGURE_ANALYSIS",
            "RESEARCH_CODE_REVIEW",
            "RESEARCH_EXPERIMENT_DESIGN",
            "SYSTEM_USER_PROFILE",
            "SYSTEM_MEMORY_MANAGER",
            "SYSTEM_SAFETY_AUDITOR",
        ],
        "spark_available": request.app.state.spark_provider.available,
        "xingchen_fallback": settings.enable_xingchen_fallback,
        "cpu_default": True,
        "workspace_features": [
            {
                "id": "course_qa",
                "label": "课程知识问答",
                "available": bool(settings.enable_local_knowledge_qa),
                "knowledge_enhanced": True,
            },
            {
                "id": "academic_problem_solving",
                "label": "多学科专业问题求解",
                "available": internal.available("ACADEMIC_PROBLEM_SOLVER"),
                "knowledge_enhanced": True,
            },
            {
                "id": "lesson_prep",
                "label": "教案设计",
                "available": internal.available("TEACH_01_LESSON_PREP_V1"),
                "knowledge_enhanced": True,
            },
            {
                "id": "assignment_review",
                "label": "作业初审",
                "available": internal.available("TEACH_02_ASSIGNMENT_REVIEW_V1"),
                "knowledge_enhanced": True,
            },
            {
                "id": "academic_writing",
                "label": "学术写作",
                "available": internal.available("RESEARCH_02_ACADEMIC_WRITING_V1"),
                "knowledge_enhanced": False,
            },
            {
                "id": "academic_search",
                "label": "科研前沿检索",
                "available": internal.available("RESEARCH_01_ACADEMIC_SEARCH_V1"),
                "knowledge_enhanced": False,
            },
            {
                "id": "data_analysis",
                "label": "数据分析",
                "available": bool(
                    settings.data_analysis_enabled
                    and internal.available("RESEARCH_03_DATA_ANALYSIS_V1")
                ),
                "knowledge_enhanced": False,
                "frozen": not settings.data_analysis_enabled,
                "unavailable_reason": (
                    "data_analysis_frozen"
                    if not settings.data_analysis_enabled
                    else ""
                ),
            },
        ],
    }


@router.get("/workflows", response_model=list[WorkflowStatus])
async def workflows(request: Request) -> list[WorkflowStatus]:
    registry = request.app.state.agent_registry
    settings = request.app.state.settings
    values: list[WorkflowStatus] = []
    for agent_id, execution_mode in WORKFLOW_MODES.items():
        try:
            definition = registry.get(agent_id)
        except KeyError:
            values.append(
                WorkflowStatus(
                    agent_id=agent_id,
                    execution_mode=ExecutionMode.DISABLED,
                    enabled=False,
                    flow_configured=False,
                    local_handler_available=False,
                    available=False,
                    unavailable_reason="registry_entry_missing",
                )
            )
            continue
        execution_mode = ExecutionMode(definition.execution_mode)
        flow_configured = bool(registry.resolve_flow_id(agent_id, settings))
        local_handler_available = _local_handler_available(definition.local_handler)
        local_available = local_handler_available
        if agent_id in WORKFLOW_INTERNAL_AGENT_MAP:
            local_available = (
                local_handler_available
                and internal_workflow_models_configured(settings, agent_id)
            )
        frozen = (
            agent_id == "RESEARCH_03_DATA_ANALYSIS_V1"
            and not settings.data_analysis_enabled
        )
        available = bool(
            definition.enabled
            and not frozen
            and (local_available or (flow_configured and settings.xingchen_enabled))
        )
        reason = None
        if not definition.enabled:
            reason = "agent_disabled"
        elif frozen:
            reason = "data_analysis_frozen"
        elif not available:
            reason = (
                "model_api_or_legacy_provider_missing"
                if agent_id in WORKFLOW_INTERNAL_AGENT_MAP
                else "flow_id_or_credentials_missing"
            )
        values.append(
            WorkflowStatus(
                agent_id=agent_id,
                execution_mode=execution_mode,
                enabled=definition.enabled,
                flow_configured=flow_configured,
                local_handler_available=local_handler_available,
                available=available,
                unavailable_reason=reason,
            )
        )
    return values
