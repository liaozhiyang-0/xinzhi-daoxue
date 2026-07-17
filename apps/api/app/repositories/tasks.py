from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import TaskEventModel, TaskModel


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, model: TaskModel) -> TaskModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get(
        self,
        task_id: str,
        *,
        with_artifacts: bool = False,
        for_update: bool = False,
    ) -> TaskModel | None:
        query = select(TaskModel).where(TaskModel.id == task_id)
        if with_artifacts:
            query = query.options(selectinload(TaskModel.artifacts))
        if for_update:
            query = query.with_for_update()
        return cast(TaskModel | None, await self.session.scalar(query))

    async def next_event_sequence(self, task_id: str) -> int:
        value = await self.session.scalar(
            select(func.max(TaskEventModel.sequence)).where(
                TaskEventModel.task_id == task_id
            )
        )
        return int(value or 0) + 1

    async def add_event(self, event: TaskEventModel) -> TaskEventModel:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_events(
        self, task_id: str, *, after: int = 0
    ) -> list[TaskEventModel]:
        query = (
            select(TaskEventModel)
            .where(
                TaskEventModel.task_id == task_id,
                TaskEventModel.sequence > after,
            )
            .order_by(TaskEventModel.sequence)
        )
        return list((await self.session.scalars(query)).all())
