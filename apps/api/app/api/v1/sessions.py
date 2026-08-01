from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.api import (
    SessionCreate,
    SessionRead,
    SessionTaskHistoryItem,
    SessionUpdate,
)
from app.contracts.conversation import ConversationMessage, SessionSummaryRead
from app.dependencies import effective_user_id, get_current_principal, get_db
from app.models import TaskModel
from app.repositories import RuntimeContextRepository
from app.services.auth_service import Principal
from app.services.conversation_message_service import ConversationMessageService
from app.services.session_service import SessionService
from app.services.task_query_service import TaskQueryService

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
    return [ConversationMessage.model_validate(item) for item in rows]


@router.get(
    "/{session_id}/summary",
    response_model=SessionSummaryRead | None,
)
async def get_session_summary(
    session_id: str,
    user_id: str,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> SessionSummaryRead | None:
    user_id = effective_user_id(principal, user_id)
    await SessionService(db).get_for_user(session_id, user_id)
    summary = await RuntimeContextRepository(db).latest_summary(session_id)
    return SessionSummaryRead.model_validate(summary) if summary is not None else None


def _history_item(task: TaskModel) -> SessionTaskHistoryItem:
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
    result = task.result_content if isinstance(task.result_content, dict) else {}
    return SessionTaskHistoryItem(
        id=task.id,
        course_id=task.course_id,
        intent=task.intent,
        status=task.status,
        provider=task.provider,
        agent_id=task.agent_id,
        question=question,
        answer=str(result.get("answer", "")),
        error_message=task.error_message,
        fallback_used=bool(result.get("fallback_used", False)),
        fallback_reason=str(result.get("fallback_reason", "")),
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


@router.get("/{session_id}/tasks", response_model=list[SessionTaskHistoryItem])
async def list_session_tasks(
    session_id: str,
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
    return [_history_item(task) for task in tasks]
