from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents import AgentRegistry
from app.contracts import AgentEventType, AgentRequest, KnowledgeHit
from app.core.errors import AppError, ProviderCancelledError
from app.models import AgentRunModel, ArtifactModel, TaskStatus
from app.providers.base import AgentProvider
from app.repositories import TaskRepository
from app.services.event_service import append_task_event
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_qa_service import (
    KnowledgeQAExecution,
    KnowledgeQAService,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def elapsed_ms(started: datetime, completed: datetime) -> int:
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=UTC)
    return max(0, int((completed - started).total_seconds() * 1000))


class TaskRunner:
    """In-process runner with a submit API that a future worker can replace."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: AgentProvider,
        knowledge_base: KnowledgeBaseService,
        agent_registry: AgentRegistry,
        knowledge_qa: KnowledgeQAService,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self.knowledge_base = knowledge_base
        self.agent_registry = agent_registry
        self.knowledge_qa = knowledge_qa
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def submit(self, task_id: str) -> bool:
        existing = self._tasks.get(task_id)
        if existing is not None and not existing.done():
            return False
        background = asyncio.create_task(self.run(task_id), name=f"xzd-task-{task_id}")
        self._tasks[task_id] = background
        background.add_done_callback(lambda _: self._tasks.pop(task_id, None))
        return True

    async def shutdown(self) -> None:
        active = [task for task in self._tasks.values() if not task.done()]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)

    async def run(self, task_id: str) -> None:
        request: AgentRequest
        started_at = utc_now()
        try:
            async with self.session_factory() as db:
                repository = TaskRepository(db)
                task = await repository.get(task_id, for_update=True)
                if task is None or task.status != TaskStatus.QUEUED:
                    return
                if task.cancellation_requested:
                    await self._mark_cancelled(db, task_id, "任务在执行前已取消")
                    return
                agent_id = task.agent_id
                agent_definition = self.agent_registry.get(agent_id)
                active_provider = (
                    "local"
                    if agent_definition.mode == "retrieval_only"
                    else self.provider.provider_name
                )
                task.status = TaskStatus.RUNNING
                task.started_at = started_at
                task.updated_at = started_at
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.TASK_RUNNING,
                    agent_id=task.agent_id,
                    data={"attempt": task.attempt},
                )
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.AGENT_STARTED,
                    agent_id=task.agent_id,
                    data={"provider": active_provider},
                )
                request = AgentRequest.model_validate(task.input_content)
                await db.commit()

            knowledge_hits: list[KnowledgeHit] = []
            retrieval_attempted = False
            if agent_definition.mode == "retrieval_only":
                execution = await asyncio.to_thread(
                    self.knowledge_qa.run, agent_id, request
                )
                await self._append_local_knowledge_events(task_id, agent_id, execution)
                result = execution.result
                provider_latency_ms = 0
            else:
                knowledge_hits, retrieval_attempted = await self._retrieve_knowledge(
                    request
                )
                if retrieval_attempted:
                    await self._append_retrieval_event(
                        task_id, agent_id, request.course_id, len(knowledge_hits)
                    )
                provider_started = perf_counter()
                result = await self.provider.run(agent_id, request, stream=True)
                provider_latency_ms = int((perf_counter() - provider_started) * 1000)
                if retrieval_attempted:
                    result.metrics.retrieval_calls += 1
            if knowledge_hits:
                hit_payloads = [hit.model_dump(mode="json") for hit in knowledge_hits]
                result.structured_result["knowledge"] = {
                    "mode": "local_lexical",
                    "hits": hit_payloads,
                }
                result.citations = list(
                    dict.fromkeys(
                        [*result.citations, *(hit.source_ref for hit in knowledge_hits)]
                    )
                )
                for artifact in result.artifacts:
                    artifact.source_refs = list(
                        dict.fromkeys(
                            [
                                *artifact.source_refs,
                                *(hit.source_ref for hit in knowledge_hits),
                            ]
                        )
                    )
                    artifact.content["knowledge_sources"] = artifact.source_refs

            async with self.session_factory() as db:
                repository = TaskRepository(db)
                task = await repository.get(task_id, for_update=True)
                if task is None:
                    return
                if task.cancellation_requested:
                    await self._mark_cancelled(
                        db, task_id, "任务在 Provider 返回前收到取消请求"
                    )
                    return

                completed_at = utc_now()
                total_latency_ms = elapsed_ms(started_at, completed_at)
                result.metrics.latency_ms = total_latency_ms
                result.metrics.queue_latency_ms = elapsed_ms(
                    task.created_at, started_at
                )
                result.metrics.provider_latency_ms = provider_latency_ms
                task.result_content = result.model_dump(mode="json")
                task.status = TaskStatus.COMPLETED
                task.completed_at = completed_at
                task.updated_at = completed_at

                for artifact in result.artifacts:
                    db.add(
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
                    await append_task_event(
                        db,
                        task.id,
                        AgentEventType.ARTIFACT_CREATED,
                        agent_id=task.agent_id,
                        data={"artifact_id": artifact.artifact_id},
                    )

                db.add(
                    AgentRunModel(
                        task_id=task.id,
                        agent_id=task.agent_id,
                        provider=result.provider,
                        status=result.status.value,
                        latency_ms=total_latency_ms,
                        model_calls=result.metrics.model_calls,
                        tool_calls=result.metrics.tool_calls,
                        retrieval_calls=result.metrics.retrieval_calls,
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                )
                await append_task_event(
                    db,
                    task.id,
                    AgentEventType.AGENT_OUTPUT,
                    agent_id=task.agent_id,
                    data={
                        "provider": result.provider,
                        "mock": result.provider == "mock",
                    },
                )
                await append_task_event(
                    db,
                    task.id,
                    AgentEventType.TASK_COMPLETED,
                    agent_id=task.agent_id,
                    data={
                        "artifact_count": len(result.artifacts),
                        "latency_ms": total_latency_ms,
                    },
                )
                await db.commit()
        except ProviderCancelledError as exc:
            await self._cancel_after_exception(task_id, exc.message)
        except asyncio.CancelledError:
            await self._fail_after_exception(
                task_id, "进程内任务因应用关闭而中断", "runner_shutdown"
            )
            raise
        except Exception as exc:
            message = exc.message if isinstance(exc, AppError) else "后台任务执行失败"
            code = exc.code if isinstance(exc, AppError) else "background_task_error"
            await self._fail_after_exception(task_id, message, code)

    async def _retrieve_knowledge(
        self, request: AgentRequest
    ) -> tuple[list[KnowledgeHit], bool]:
        if not self.knowledge_base.settings.knowledge_enabled:
            return [], False
        query = self._knowledge_query(request)
        if not query:
            return [], False
        try:
            hits = await asyncio.to_thread(
                self.knowledge_base.search,
                query,
                [request.course_id],
                self.knowledge_base.settings.knowledge_default_top_k,
            )
            return hits, True
        except Exception as exc:
            logger.warning(
                "knowledge_retrieval_failed task_id=%s session_id=%s "
                "course_id=%s error=%s",
                request.task_id,
                request.session_id,
                request.course_id,
                type(exc).__name__,
            )
            return [], True

    @staticmethod
    def _knowledge_query(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    async def _append_retrieval_event(
        self, task_id: str, agent_id: str, course_id: str, hit_count: int
    ) -> None:
        async with self.session_factory() as db:
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_RETRIEVED,
                agent_id=agent_id,
                data={"course_id": course_id, "hit_count": hit_count},
            )
            await db.commit()

    async def _append_local_knowledge_events(
        self,
        task_id: str,
        agent_id: str,
        execution: KnowledgeQAExecution,
    ) -> None:
        async with self.session_factory() as db:
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_QUERY_NORMALIZED,
                agent_id=agent_id,
                data={"normalized_query": execution.retrieval.normalized_query},
            )
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_RETRIEVED,
                agent_id=agent_id,
                data={
                    "course_id": execution.context.course_id,
                    "hit_count": len(execution.retrieval.hits),
                    "confidence": execution.retrieval.confidence,
                    "retrieval_mode": execution.retrieval.retrieval_mode,
                },
            )
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_CONTEXT_BUILT,
                agent_id=agent_id,
                data={
                    "evidence_count": len(execution.context.evidence),
                    "evidence_status": execution.context.evidence_status,
                    "source_refs": execution.context.source_refs,
                },
            )
            if execution.context.evidence_status in {"insufficient", "unavailable"}:
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.KNOWLEDGE_INSUFFICIENT,
                    agent_id=agent_id,
                    data={"warnings": execution.context.warnings},
                )
            await append_task_event(
                db,
                task_id,
                AgentEventType.ANSWER_RETRIEVAL_ONLY_CREATED,
                agent_id=agent_id,
                data={"mode": "retrieval_only"},
            )
            await db.commit()

    async def _mark_cancelled(
        self, db: AsyncSession, task_id: str, reason: str
    ) -> None:
        task = await TaskRepository(db).get(task_id, for_update=True)
        if task is None:
            return
        now = utc_now()
        task.status = TaskStatus.CANCELLED
        task.completed_at = now
        task.updated_at = now
        task.error_message = reason
        if task.started_at:
            db.add(
                AgentRunModel(
                    task_id=task.id,
                    agent_id=task.agent_id,
                    provider=self.provider.provider_name,
                    status=TaskStatus.CANCELLED.value,
                    latency_ms=elapsed_ms(task.started_at, now),
                    started_at=task.started_at,
                    completed_at=now,
                )
            )
        await append_task_event(
            db,
            task_id,
            AgentEventType.TASK_CANCELLED,
            agent_id=task.agent_id,
            data={"reason": reason},
        )
        await db.commit()

    async def _cancel_after_exception(self, task_id: str, reason: str) -> None:
        async with self.session_factory() as db:
            await self._mark_cancelled(db, task_id, reason)

    async def _fail_after_exception(
        self, task_id: str, message: str, code: str
    ) -> None:
        async with self.session_factory() as db:
            task = await TaskRepository(db).get(task_id, for_update=True)
            if task is None or task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
            }:
                return
            now = utc_now()
            task.status = TaskStatus.FAILED
            task.error_message = message
            task.completed_at = now
            task.updated_at = now
            db.add(
                AgentRunModel(
                    task_id=task.id,
                    agent_id=task.agent_id,
                    provider=self.provider.provider_name,
                    status=TaskStatus.FAILED.value,
                    latency_ms=(
                        elapsed_ms(task.started_at, now) if task.started_at else None
                    ),
                    started_at=task.started_at,
                    completed_at=now,
                )
            )
            await append_task_event(
                db,
                task.id,
                AgentEventType.TASK_FAILED,
                agent_id=task.agent_id,
                data={"error_code": code},
            )
            await db.commit()
            logger.warning(
                "task_failed task_id=%s session_id=%s agent_id=%s "
                "provider=%s attempt=%s error_code=%s",
                task.id,
                task.session_id,
                task.agent_id,
                self.provider.provider_name,
                task.attempt,
                code,
            )
