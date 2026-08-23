from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.tasks.query import TaskQueryService
from app.contracts.api import (
    SessionCreate,
    SessionRead,
    SessionTaskHistoryItem,
    SessionUpdate,
)
from app.contracts.conversation import ConversationMessage, SessionSummaryRead
from app.dependencies import effective_user_id, get_current_principal, get_db
from app.models import TaskModel
from app.repositories import ConversationRepository, RuntimeContextRepository
from app.services.auth_service import Principal
from app.services.conversation_message_service import ConversationMessageService
from app.services.course_material_manifest import (
    REVOCATION_STATE_UNAVAILABLE,
    collect_material_source_refs,
    filter_revoked_material_result,
    load_revoked_material_ids,
    material_id_from_source_ref,
)
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    data = data.model_copy(
        update={"user_id": effective_user_id(principal, data.user_id)}
    )
    return SessionRead.model_validate(await SessionService(db).create(data))


@router.get("", response_model=list[SessionRead])
async def list_sessions(
    user_id: str,
    principal: Principal = Depends(get_current_principal),
    include_archived: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[SessionRead]:
    user_id = effective_user_id(principal, user_id)
    rows = await SessionService(db).list(
        user_id,
        include_archived=include_archived,
        offset=offset,
        limit=limit,
    )
    return [SessionRead.model_validate(item) for item in rows]


@router.get("/search", response_model=list[SessionRead])
async def search_sessions(
    user_id: str,
    principal: Principal = Depends(get_current_principal),
    q: str = Query(min_length=1, max_length=100),
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[SessionRead]:
    user_id = effective_user_id(principal, user_id)
    rows = await SessionService(db).list(
        user_id,
        include_archived=include_archived,
        query=q,
        limit=limit,
    )
    return [SessionRead.model_validate(item) for item in rows]


@router.get("/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: str,
    principal: Principal = Depends(get_current_principal),
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    user_id = effective_user_id(principal, user_id)
    service = SessionService(db)
    model = (
        await service.get_for_user(session_id, user_id)
        if user_id
        else await service.get(session_id)
    )
    return SessionRead.model_validate(model)


@router.patch("/{session_id}", response_model=SessionRead)
async def update_session(
    session_id: str,
    data: SessionUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    data = data.model_copy(
        update={"user_id": effective_user_id(principal, data.user_id)}
    )
    return SessionRead.model_validate(await SessionService(db).update(session_id, data))


@router.post("/{session_id}/archive", response_model=SessionRead)
async def archive_session(
    session_id: str,
    user_id: str,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    user_id = effective_user_id(principal, user_id)
    return SessionRead.model_validate(
        await SessionService(db).archive(session_id, user_id, archived=True)
    )


@router.post("/{session_id}/restore", response_model=SessionRead)
async def restore_session(
    session_id: str,
    user_id: str,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    user_id = effective_user_id(principal, user_id)
    return SessionRead.model_validate(
        await SessionService(db).archive(session_id, user_id, archived=False)
    )


@router.get("/{session_id}/messages", response_model=list[ConversationMessage])
async def list_session_messages(
    session_id: str,
    user_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationMessage]:
    user_id = effective_user_id(principal, user_id)
    rows = await ConversationMessageService(db).list_user_visible(
        session_id,
        user_id=user_id,
        after_sequence=after_sequence,
        limit=limit,
    )
    revoked_material_ids = load_revoked_material_ids(
        request.app.state.settings.knowledge_index_path
    )
    return [_public_message(item, revoked_material_ids) for item in rows]


@router.get(
    "/{session_id}/summary",
    response_model=SessionSummaryRead | None,
)
async def get_session_summary(
    session_id: str,
    user_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> SessionSummaryRead | None:
    user_id = effective_user_id(principal, user_id)
    await SessionService(db).get_for_user(session_id, user_id)
    summary = await RuntimeContextRepository(db).latest_summary(session_id)
    if summary is None:
        return None
    source_refs: list[str] = []
    source_ids = (
        list(summary.source_message_ids)
        if isinstance(summary.source_message_ids, list)
        else []
    )
    for message in await ConversationRepository(db).list_by_ids(
        session_id,
        user_id=user_id,
        message_ids=source_ids,
    ):
        for ref in collect_material_source_refs(
            {
                "metadata": message.metadata_data,
                "content_data": message.content_data,
            }
        ):
            if ref not in source_refs and len(source_refs) < 100:
                source_refs.append(ref)
    return _public_summary(
        summary,
        load_revoked_material_ids(request.app.state.settings.knowledge_index_path),
        source_refs=source_refs,
    )


def _history_item(
    task: TaskModel,
    *,
    revoked_material_ids: set[str] | None = None,
) -> SessionTaskHistoryItem:
    canonical = task.input_content.get("canonical_input", {})
    if not isinstance(canonical, dict):
        canonical = {}
    question = next(
        (
            str(canonical[key]).strip()
            for key in ("text", "question", "problem", "query", "prompt")
            if str(canonical.get(key, "")).strip()
        ),
        "已提交材料任务",
    )
    result = filter_revoked_material_result(
        task.result_content if isinstance(task.result_content, dict) else {},
        revoked_material_ids or set(),
    ) or {}
    structured = result.get("structured_result")
    structured_data = structured if isinstance(structured, dict) else {}
    revocation_notice = (
        structured_data.get("revocation_notice")
    )
    raw_refs = collect_material_source_refs(task.result_content)
    raw_revoked = any(
        REVOCATION_STATE_UNAVAILABLE in (revoked_material_ids or set())
        or material_id_from_source_ref(ref) in (revoked_material_ids or set())
        for ref in raw_refs
    )
    answer = str(result.get("answer", ""))
    if isinstance(revocation_notice, dict) or raw_revoked:
        answer = f"【课程资料已撤回，需复核】\n{answer}".strip()
    presentation = structured_data.get("presentation", {})
    presentation = presentation if isinstance(presentation, dict) else {}
    math_quality = structured_data.get("math_quality", {})
    math_quality = math_quality if isinstance(math_quality, dict) else {}
    formula_contract = structured_data.get("formula_output_contract", {})
    formula_contract = (
        formula_contract if isinstance(formula_contract, dict) else {}
    )
    scenario_contract = structured_data.get("scenario_contract", {})
    scenario_contract = (
        scenario_contract if isinstance(scenario_contract, dict) else {}
    )
    model_synthesis = scenario_contract.get("model_synthesis", {})
    model_synthesis = (
        model_synthesis if isinstance(model_synthesis, dict) else {}
    )
    publishable = model_synthesis.get("publishable")
    if not isinstance(publishable, bool):
        requires_review = bool(presentation.get("requires_review", False))
        blocked_quality = math_quality.get("status") in {
            "blocked",
            "needs_review",
        }
        blocked_formula = formula_contract.get("status") in {
            "blocked",
            "needs_review",
        }
        publishable = (
            False
            if requires_review or blocked_quality or blocked_formula
            else None
        )
    requires_review = bool(presentation.get("requires_review", False))
    return SessionTaskHistoryItem(
        id=task.id,
        course_id=task.course_id,
        intent=task.intent,
        status=task.status,
        provider=task.provider,
        agent_id=task.agent_id,
        question=question,
        answer=answer,
        error_message=task.error_message,
        fallback_used=bool(result.get("fallback_used", False)),
        fallback_reason=str(result.get("fallback_reason", "")),
        answer_quality_status=str(
            presentation.get("answer_quality_status", "not_available")
        ),
        requires_review=requires_review,
        publishable=publishable,
        math_quality_status=str(math_quality.get("status", "not_available")),
        formula_contract_status=str(
            formula_contract.get("status", "not_available")
        ),
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


def _public_message(
    message: object,
    revoked_material_ids: set[str],
) -> ConversationMessage:
    model = ConversationMessage.model_validate(message)
    filtered = filter_revoked_material_result(
        {"structured_result": model.content_data},
        revoked_material_ids,
    ) or {"structured_result": model.content_data}
    content_data = filtered.get("structured_result", {})
    if not isinstance(content_data, dict):
        content_data = {}
    notice = content_data.get("revocation_notice")
    content_text = model.content_text
    if isinstance(notice, dict):
        content_text = f"【课程资料已撤回，需复核】\n{content_text}".strip()
    return model.model_copy(
        update={"content_text": content_text, "content_data": content_data}
    )


def _public_summary(
    summary: object,
    revoked_material_ids: set[str],
    *,
    source_refs: list[str] | None = None,
) -> SessionSummaryRead:
    model = SessionSummaryRead.model_validate(summary)
    structured_state = dict(model.structured_state or {})
    if source_refs:
        structured_state["course_material_source_refs"] = list(
            dict.fromkeys(
                [
                    *collect_material_source_refs(structured_state),
                    *source_refs,
                ]
            )
        )[:100]
    filtered = filter_revoked_material_result(
        {
            "answer": model.summary_text,
            "structured_result": structured_state,
        },
        revoked_material_ids,
    ) or {}
    structured = filtered.get("structured_result", {})
    if not isinstance(structured, dict):
        structured = {}
    summary_text = str(filtered.get("answer", model.summary_text))
    if isinstance(structured.get("revocation_notice"), dict):
        summary_text = f"【课程资料已撤回，需复核】\n{summary_text}".strip()
    return model.model_copy(
        update={"summary_text": summary_text, "structured_state": structured}
    )


@router.get("/{session_id}/tasks", response_model=list[SessionTaskHistoryItem])
async def list_session_tasks(
    session_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    user_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[SessionTaskHistoryItem]:
    user_id = effective_user_id(principal, user_id)
    service = SessionService(db)
    if user_id:
        await service.get_for_user(session_id, user_id)
    else:
        await service.get(session_id)
    tasks = await TaskQueryService(db).list_for_session(session_id, limit=limit)
    revoked_material_ids = load_revoked_material_ids(
        request.app.state.settings.knowledge_index_path
    )
    return [
        _history_item(task, revoked_material_ids=revoked_material_ids)
        for task in tasks
    ]
