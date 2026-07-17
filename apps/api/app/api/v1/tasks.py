from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentRequest
from app.contracts.api import EventRead, TaskRead
from app.core.errors import NotFoundError
from app.dependencies import get_db, get_provider
from app.models import TaskModel, TaskStatus
from app.providers.base import AgentProvider
from app.repositories import TaskRepository
from app.services.task_control_service import TaskControlService
from app.services.task_creation_service import TaskCreationService
from app.services.task_query_service import TaskQueryService

router = APIRouter(prefix="/tasks", tags=["tasks"])
TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}


def task_read(task: TaskModel) -> TaskRead:
    model = TaskRead.model_validate(task)
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
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    decision = request.app.state.task_router.route(data)
    task = await TaskCreationService(db, provider.provider_name).create_queued(
        data, route=decision
    )
    if task.status == TaskStatus.QUEUED:
        request.app.state.task_runner.submit(task.id)
    return task_read(task)


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    return task_read(await TaskQueryService(db).get(task_id))


@router.get("/{task_id}/events", response_model=list[EventRead])
async def get_task_events(
    task_id: str,
    after: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[EventRead]:
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
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    task = await TaskControlService(db, provider).retry(task_id)
    request.app.state.task_runner.submit(task.id)
    return task_read(task)


@router.post("/{task_id}/cancel", response_model=TaskRead)
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
) -> TaskRead:
    return task_read(await TaskControlService(db, provider).cancel(task_id))


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
        if await TaskRepository(db).get(task_id) is None:
            raise NotFoundError("任务不存在", details={"task_id": task_id})
    return StreamingResponse(
        event_stream(request, task_id, cursor=cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
