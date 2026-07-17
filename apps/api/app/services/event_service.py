from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentEvent, AgentEventType
from app.core.errors import NotFoundError
from app.models import TaskEventModel
from app.repositories import TaskRepository


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
    sequence = await repository.next_event_sequence(task_id)
    event = AgentEvent(
        task_id=task_id,
        sequence=sequence,
        type=event_type,
        agent_id=agent_id,
        data=data or {},
    )
    return await repository.add_event(
        TaskEventModel(
            id=event.event_id,
            task_id=task_id,
            sequence=sequence,
            event_type=event.type.value,
            event_data=event.model_dump(mode="json"),
            created_at=event.timestamp,
        )
    )
