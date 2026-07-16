from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentEvent, AgentEventType, AgentRequest
from app.core.errors import AppError, NotFoundError, ProviderError
from app.models import (
    AgentRunModel,
    ArtifactModel,
    TaskEventModel,
    TaskModel,
    TaskStatus,
)
from app.providers.base import AgentProvider
from app.repositories import SessionRepository, TaskRepository

logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self, db: AsyncSession, provider: AgentProvider) -> None:
        self.db = db
        self.provider = provider
        self.repository = TaskRepository(db)

    async def _event(
        self,
        task_id: str,
        event_type: AgentEventType,
        *,
        agent_id: str = "",
        data: dict[str, Any] | None = None,
    ) -> None:
        event = AgentEvent(
            task_id=task_id,
            type=event_type,
            agent_id=agent_id,
            data=data or {},
        )
        await self.repository.add_event(
            TaskEventModel(
                id=event.event_id,
                task_id=task_id,
                event_type=event.type.value,
                event_data=event.model_dump(mode="json"),
                created_at=event.timestamp,
            )
        )

    async def create_and_run(
        self, request: AgentRequest, *, agent_id: str = "SOLVER_CT_V1"
    ) -> TaskModel:
        if await SessionRepository(self.db).get(request.session_id) is None:
            raise NotFoundError(
                "任务引用的会话不存在", details={"session_id": request.session_id}
            )

        provider_name = self.provider.__class__.__name__.replace(
            "AgentProvider", ""
        ).replace("CloudProvider", "").lower()
        if provider_name == "":
            provider_name = "unknown"
        if provider_name.startswith("mock"):
            provider_name = "mock"
        if provider_name.startswith("xingchen"):
            provider_name = "xingchen"

        task = TaskModel(
            id=request.task_id,
            session_id=request.session_id,
            user_id=request.user_id,
            course_id=request.course_id,
            intent=request.intent.value,
            status=TaskStatus.CREATED,
            provider=provider_name,
            agent_id=agent_id,
            input_content=request.model_dump(mode="json"),
        )
        await self.repository.add(task)
        await self._event(task.id, AgentEventType.TASK_CREATED)
        task.status = TaskStatus.RUNNING
        task.started_at = AgentEvent(
            task_id=task.id, type=AgentEventType.AGENT_STARTED
        ).timestamp
        await self._event(task.id, AgentEventType.AGENT_STARTED, agent_id=agent_id)
        await self.db.commit()

        started = perf_counter()
        try:
            result = await self.provider.run(agent_id, request, stream=True)
            latency_ms = int((perf_counter() - started) * 1000)
            task.result_content = result.model_dump(mode="json")
            task.status = TaskStatus.COMPLETED
            task.completed_at = AgentEvent(
                task_id=task.id, type=AgentEventType.TASK_COMPLETED
            ).timestamp
            for artifact in result.artifacts:
                self.db.add(
                    ArtifactModel(
                        id=artifact.artifact_id,
                        task_id=task.id,
                        artifact_type=artifact.artifact_type.value,
                        version=artifact.version,
                        content=artifact.content,
                        confidence=artifact.confidence,
                        created_at=artifact.created_at,
                    )
                )
            self.db.add(
                AgentRunModel(
                    task_id=task.id,
                    agent_id=agent_id,
                    provider=result.provider,
                    status=result.status.value,
                    latency_ms=latency_ms,
                    model_calls=int(result.metrics.get("model_calls", 0)),
                    tool_calls=int(result.metrics.get("tool_calls", 0)),
                    retrieval_calls=int(result.metrics.get("retrieval_calls", 0)),
                )
            )
            await self._event(
                task.id,
                AgentEventType.TASK_COMPLETED,
                agent_id=agent_id,
                data={
                    "artifact_count": len(result.artifacts),
                    "latency_ms": latency_ms,
                },
            )
        except Exception as exc:
            latency_ms = int((perf_counter() - started) * 1000)
            task.status = TaskStatus.FAILED
            task.error_message = (
                exc.message if isinstance(exc, AppError) else "Provider 执行失败"
            )
            task.completed_at = AgentEvent(
                task_id=task.id, type=AgentEventType.TASK_FAILED
            ).timestamp
            self.db.add(
                AgentRunModel(
                    task_id=task.id,
                    agent_id=agent_id,
                    provider=provider_name,
                    status=TaskStatus.FAILED.value,
                    latency_ms=latency_ms,
                )
            )
            await self._event(
                task.id,
                AgentEventType.TASK_FAILED,
                agent_id=agent_id,
                data={
                    "error_code": (
                        exc.code if isinstance(exc, AppError) else ProviderError.code
                    )
                },
            )
            logger.warning(
                "task_failed task_id=%s session_id=%s agent_id=%s error=%s",
                task.id,
                task.session_id,
                agent_id,
                type(exc).__name__,
            )

        await self.db.commit()
        return await self.get(task.id)

    async def get(self, task_id: str) -> TaskModel:
        task = await self.repository.get(task_id, with_artifacts=True)
        if task is None:
            raise NotFoundError("任务不存在", details={"task_id": task_id})
        return task

    async def list_events(self, task_id: str) -> list[TaskEventModel]:
        if await self.repository.get(task_id) is None:
            raise NotFoundError("任务不存在", details={"task_id": task_id})
        return await self.repository.list_events(task_id)
