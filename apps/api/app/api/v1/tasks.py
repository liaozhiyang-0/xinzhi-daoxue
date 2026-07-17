from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentRequest
from app.contracts.api import EventRead, TaskRead
from app.core.config import Settings
from app.dependencies import get_db, get_provider, get_settings_from_app
from app.models import TaskModel, TaskStatus
from app.providers.base import AgentProvider
from app.repositories.tasks import TaskRepository
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])
TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}


def task_read(task: TaskModel) -> TaskRead:
    model = TaskRead.model_validate(task)
    model.artifact_ids = [artifact.id for artifact in task.artifacts]
    return model


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: AgentRequest,
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings_from_app),
) -> TaskRead:
    task = await TaskService(db, provider, settings=settings).create_and_run(data)
    return task_read(task)


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings_from_app),
) -> TaskRead:
    task = await TaskService(db, provider, settings=settings).get(task_id)
    return task_read(task)


@router.get("/{task_id}/events", response_model=list[EventRead])
async def get_task_events(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    provider: AgentProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings_from_app),
) -> list[EventRead]:
    events = await TaskService(db, provider, settings=settings).list_events(task_id)
    return [EventRead.model_validate(event) for event in events]


async def event_stream(request: Request, task_id: str) -> AsyncGenerator[str, None]:
    last_event_id: str | None = None
    heartbeat_seconds = 10.0
    while not await request.is_disconnected():
        async with request.app.state.session_factory() as db:
            repository = TaskRepository(db)
            task = await repository.get(task_id)
            if task is None:
                payload = json.dumps(
                    {"error": {"code": "not_found", "message": "任务不存在"}},
                    ensure_ascii=False,
                )
                yield f"event: error\ndata: {payload}\n\n"
                return
            events = await repository.list_events(task_id, after=last_event_id)
            for event in events:
                last_event_id = event.id
                payload = json.dumps(event.event_data, ensure_ascii=False)
                yield (
                    f"id: {event.id}\nevent: {event.event_type}\ndata: {payload}\n\n"
                )
            if task.status in TERMINAL_STATUSES and not events:
                return
            if task.status in TERMINAL_STATUSES:
                continue
        yield ": heartbeat\n\n"
        await asyncio.sleep(heartbeat_seconds)


@router.get("/{task_id}/stream")
async def stream_task(request: Request, task_id: str) -> StreamingResponse:
    return StreamingResponse(
        event_stream(request, task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
