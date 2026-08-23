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

    async def latest_summary_for_course(
        self, session_id: str, course_id: str
    ) -> SessionSummaryModel | None:
        """Return the newest summary explicitly bound to one course.

        A session can legitimately switch courses, so the globally newest
        summary is not necessarily safe to use for the current task. The
        course is stored in JSON structured state; filter after the bounded
        newest-first query to keep this compatible with SQLite and Postgres.
        """

        query = (
            select(SessionSummaryModel)
            .where(
                SessionSummaryModel.session_id == session_id,
                SessionSummaryModel.status == "completed",
            )
            .order_by(desc(SessionSummaryModel.version))
        )
        rows = list((await self.session.scalars(query)).all())
        normalized_course = course_id.strip().upper()
        for item in rows:
            state = (
                item.structured_state
                if isinstance(item.structured_state, dict)
                else {}
            )
            if (
                str(state.get("course_id", "")).strip().upper()
                == normalized_course
            ):
                return item
        return None

    async def next_summary_version(self, session_id: str) -> int:
        value = await self.session.scalar(
            select(func.max(SessionSummaryModel.version)).where(
                SessionSummaryModel.session_id == session_id
            )
        )
        return int(value or 0) + 1
