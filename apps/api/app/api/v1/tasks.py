from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentRequest, UserRole
from app.contracts.api import EventRead, TaskRead
from app.contracts.conversation import ConversationContextBundle
from app.core.errors import NotFoundError
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
from app.services.answer_disclosure import public_teaching_result
from app.services.auth_service import Principal
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
    updates: dict[str, object] = {
        "user_id": effective_user_id(principal, data.user_id)
    }
    if principal.has_identity:
        try:
            updates["user_role"] = UserRole(principal.role)
        except ValueError:
            updates["user_role"] = UserRole.STUDENT
    data = data.model_copy(update=updates)
    data = await _hydrate_document_attachments(data, principal, db, request)
    session = await SessionRepository(db).get(data.session_id)
    if session is not None:
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
            extracted_blocks.append(f"【附件：{model.filename}】\n{model.extracted_text.strip()}")
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
    task = await TaskControlService(db, provider).retry(task_id)
    request.app.state.task_runner.submit(task.id)
    return task_read(task)


@router.post("/{task_id}/cancel", response_model=TaskRead)
async def cancel_task(
    task_id: str,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    await _get_owned_task(db, task_id, principal)
    return task_read(await TaskControlService(db, provider).cancel(task_id))


async def _get_owned_task(
    db: AsyncSession, task_id: str, principal: Principal
) -> TaskModel:
    task = await TaskQueryService(db).get(task_id)
    if principal.has_identity and task.user_id != principal.user_id:
        raise NotFoundError("任务不存在")
    return task


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
