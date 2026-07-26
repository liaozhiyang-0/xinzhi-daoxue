from __future__ import annotations

from typing import cast

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SessionSummaryModel, SessionWorkingStateModel


class RuntimeContextRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_working_state(
        self, session_id: str
    ) -> SessionWorkingStateModel | None:
        return cast(
            SessionWorkingStateModel | None,
            await self.session.get(SessionWorkingStateModel, session_id),
        )

    async def latest_summary(
        self, session_id: str
    ) -> SessionSummaryModel | None:
        query = (
            select(SessionSummaryModel)
            .where(
                SessionSummaryModel.session_id == session_id,
                SessionSummaryModel.status == "completed",
            )
            .order_by(desc(SessionSummaryModel.version))
            .limit(1)
        )
        return cast(SessionSummaryModel | None, await self.session.scalar(query))

    async def next_summary_version(self, session_id: str) -> int:
        value = await self.session.scalar(
            select(func.max(SessionSummaryModel.version)).where(
                SessionSummaryModel.session_id == session_id
            )
        )
        return int(value or 0) + 1
