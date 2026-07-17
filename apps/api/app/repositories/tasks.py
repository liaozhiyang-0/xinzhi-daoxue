from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import TaskEventModel, TaskModel, TaskStatus


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, model: TaskModel) -> TaskModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get(
        self, task_id: str, *, with_artifacts: bool = False
    ) -> TaskModel | None:
        query = select(TaskModel).where(TaskModel.id == task_id)
        if with_artifacts:
            query = query.options(selectinload(TaskModel.artifacts))
        return await self.session.scalar(query)

    async def add_event(self, event: TaskEventModel) -> TaskEventModel:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_events(
        self, task_id: str, *, after: str | None = None
    ) -> list[TaskEventModel]:
        query = (
            select(TaskEventModel)
            .where(TaskEventModel.task_id == task_id)
            .order_by(TaskEventModel.created_at, TaskEventModel.id)
        )
        if after:
            query = query.where(TaskEventModel.id > after)
        return list((await self.session.scalars(query)).all())

    async def latest_completed_for_session(self, session_id: str) -> TaskModel | None:
        query = (
            select(TaskModel)
            .where(
                TaskModel.session_id == session_id,
                TaskModel.status == TaskStatus.COMPLETED,
            )
            .order_by(TaskModel.completed_at.desc(), TaskModel.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(query)
