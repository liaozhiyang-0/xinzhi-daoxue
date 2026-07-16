from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import TaskEventModel, TaskModel
from app.repositories import TaskRepository


class TaskQueryService:
    def __init__(self, db: AsyncSession) -> None:
        self.repository = TaskRepository(db)

    async def get(self, task_id: str) -> TaskModel:
        task = await self.repository.get(task_id, with_artifacts=True)
        if task is None:
            raise NotFoundError("任务不存在", details={"task_id": task_id})
        return task

    async def list_events(
        self, task_id: str, *, after: int = 0
    ) -> list[TaskEventModel]:
        if await self.repository.get(task_id) is None:
            raise NotFoundError("任务不存在", details={"task_id": task_id})
        return await self.repository.list_events(task_id, after=after)
