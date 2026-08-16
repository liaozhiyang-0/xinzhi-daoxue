from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts import AgentEventType
from app.services.event_service import append_task_event


class TaskProgressReporter:
    """Persist public stage progress without exposing model reasoning."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def append(
        self,
        task_id: str,
        agent_id: str,
        *,
        db: AsyncSession | None = None,
        stage_id: str,
        status: str,
        label: str,
        progress: float,
        elapsed_ms: int | None = None,
        detail: str = "",
    ) -> None:
        data: dict[str, object] = {
            "stage_id": stage_id,
            "status": status,
            "label": label,
            "progress": max(0.0, min(1.0, progress)),
        }
        if elapsed_ms is not None:
            data["elapsed_ms"] = max(0, elapsed_ms)
        if detail:
            data["detail"] = detail[:240]
        if db is not None:
            await append_task_event(
                db,
                task_id,
                AgentEventType.AGENT_PROGRESS,
                agent_id=agent_id,
                data=data,
            )
            return
        async with self.session_factory() as progress_db:
            await append_task_event(
                progress_db,
                task_id,
                AgentEventType.AGENT_PROGRESS,
                agent_id=agent_id,
                data=data,
            )
            await progress_db.commit()
