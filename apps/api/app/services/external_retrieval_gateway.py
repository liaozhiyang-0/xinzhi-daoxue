from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts import (
    AgentEventType,
    AgentRequest,
    ExternalRetrievalPolicy,
    ExternalRetrievalResult,
)
from app.services.event_service import append_task_event
from app.services.external_retrieval_execution import (
    ExternalRetrievalExecutionService,
)


class ExternalRetrievalGateway:
    """Expose retrieval and its task events as one Runtime dependency."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        execution: ExternalRetrievalExecutionService,
    ) -> None:
        self.session_factory = session_factory
        self.execution = execution

    async def retrieve(
        self,
        request: AgentRequest,
        policy: ExternalRetrievalPolicy,
        *,
        allow_degraded_review: bool = False,
    ) -> ExternalRetrievalResult:
        return await self.execution.retrieve(
            request,
            policy,
            allow_degraded_review=allow_degraded_review,
        )

    async def retrieve_with_deadline(
        self,
        request: AgentRequest,
        policy: ExternalRetrievalPolicy,
        *,
        allow_degraded_review: bool = False,
    ) -> ExternalRetrievalResult:
        return await self.execution.retrieve_with_deadline(
            request,
            policy,
            allow_degraded_review=allow_degraded_review,
            retrieval=self.retrieve,
        )

    async def append_event(
        self,
        task_id: str,
        agent_id: str,
        event_type: AgentEventType,
        data: dict[str, object],
    ) -> None:
        async with self.session_factory() as db:
            await append_task_event(
                db,
                task_id,
                event_type,
                agent_id=agent_id,
                data=data,
            )
            await db.commit()

    async def shutdown(self) -> None:
        await self.execution.shutdown()
