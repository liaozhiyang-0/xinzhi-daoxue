from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentEvent, AgentEventType
from app.core.errors import NotFoundError
from app.models import TaskEventModel, TaskModel
from app.repositories import TaskRepository

_EVENT_SEQUENCE_RETRIES = 3


async def append_task_event(
    db: AsyncSession,
    task_id: str,
    event_type: AgentEventType,
    *,
    agent_id: str = "",
    data: dict[str, Any] | None = None,
) -> TaskEventModel:
    repository = TaskRepository(db)
    if await repository.get(task_id, for_update=True) is None:
        raise NotFoundError("任务不存在", details={"task_id": task_id})
    for attempt in range(_EVENT_SEQUENCE_RETRIES):
        sequence = await repository.next_event_sequence(task_id)
        event = AgentEvent(
            task_id=task_id,
            sequence=sequence,
            type=event_type,
            agent_id=agent_id,
            data=data or {},
        )
        try:
            # MAX(sequence) + 1 is only a candidate under concurrent writers.
            # Keep the insert in a savepoint so a unique-key conflict does not
            # poison the caller's transaction before the next candidate read.
            async with db.begin_nested():
                stored = await repository.add_event(
                    TaskEventModel(
                        id=event.event_id,
                        task_id=task_id,
                        sequence=sequence,
                        event_type=event.type.value,
                        event_data=event.model_dump(mode="json"),
                        created_at=event.timestamp,
                    )
                )
        except IntegrityError:
            if attempt == _EVENT_SEQUENCE_RETRIES - 1:
                raise
            continue
        return stored

    raise AssertionError("event sequence allocation exhausted")


async def append_task_events(
    db: AsyncSession,
    task_id: str,
    events: Sequence[tuple[AgentEventType, dict[str, Any]]],
    *,
    agent_id: str = "",
    task: TaskModel | None = None,
) -> list[TaskEventModel]:
    """Append an ordered event batch with one sequence allocation."""

    if not events:
        return []
    repository = TaskRepository(db)
    if task is None:
        task = await repository.get(task_id, for_update=True)
    if task is None:
        raise NotFoundError("任务不存在", details={"task_id": task_id})
    for attempt in range(_EVENT_SEQUENCE_RETRIES):
        try:
            async with db.begin_nested():
                sequence = await repository.next_event_sequence(task_id)
                stored_events: list[TaskEventModel] = []
                for offset, (event_type, data) in enumerate(events):
                    event = AgentEvent(
                        task_id=task_id,
                        sequence=sequence + offset,
                        type=event_type,
                        agent_id=agent_id,
                        data=data,
                    )
                    stored_events.append(
                        await repository.add_event(
                            TaskEventModel(
                                id=event.event_id,
                                task_id=task_id,
                                sequence=event.sequence,
                                event_type=event.type.value,
                                event_data=event.model_dump(mode="json"),
                                created_at=event.timestamp,
                            )
                        )
                    )
        except IntegrityError:
            if attempt == _EVENT_SEQUENCE_RETRIES - 1:
                raise
            continue
        return stored_events

    raise AssertionError("event sequence batch allocation exhausted")
