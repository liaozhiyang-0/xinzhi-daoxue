from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts import ExternalRetrievalResult
from app.models import TaskStatus
from app.repositories import SessionRepository, TaskRepository
from app.services.research_knowledge import ResearchKnowledgeService
from app.services.session_compaction import SessionCompactionService

logger = logging.getLogger(__name__)


class TaskPostProcessingService:
    """Run optional post-answer work outside the Runtime execution boundary."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        session_compaction: SessionCompactionService | None = None,
        research_knowledge: ResearchKnowledgeService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.session_compaction = session_compaction
        self.research_knowledge = research_knowledge
        self._memory_tasks: dict[str, asyncio.Task[None]] = {}
        self._research_tasks: dict[str, asyncio.Task[None]] = {}
        self._summary_locks: dict[str, asyncio.Lock] = {}
        self._summary_lock_users: dict[str, int] = {}

    def schedule_memory_summary(self, task_id: str, session_id: str) -> None:
        if self.session_compaction is None:
            return
        existing = self._memory_tasks.get(task_id)
        if existing is not None and not existing.done():
            return
        background = asyncio.create_task(
            self._summarize_completed_task(task_id, session_id),
            name=f"xzd-memory-{task_id}",
        )
        self._track(self._memory_tasks, task_id, background)

    def schedule_research_ingest(
        self,
        result: ExternalRetrievalResult,
        *,
        query: str,
        task_id: str,
    ) -> None:
        if self.research_knowledge is None or not result.items:
            return
        existing = self._research_tasks.get(task_id)
        if existing is not None and not existing.done():
            return
        background = asyncio.create_task(
            self._ingest_research_evidence(result, query, task_id),
            name=f"xzd-research-ingest-{task_id}",
        )
        self._track(self._research_tasks, task_id, background)

    async def shutdown(self) -> None:
        active = [
            task
            for task in (*self._memory_tasks.values(), *self._research_tasks.values())
            if not task.done()
        ]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        self._memory_tasks.clear()
        self._research_tasks.clear()
        self._summary_locks.clear()
        self._summary_lock_users.clear()

    async def _ingest_research_evidence(
        self,
        result: ExternalRetrievalResult,
        query: str,
        task_id: str,
    ) -> None:
        service = self.research_knowledge
        if service is None:
            return
        try:
            await service.ingest(result, query=query, task_id=task_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "research_knowledge_ingest_background_failed task_id=%s",
                task_id,
                exc_info=True,
            )

    async def _summarize_completed_task(
        self,
        task_id: str,
        session_id: str,
    ) -> None:
        compaction = self.session_compaction
        if compaction is None:
            return
        lock = self._summary_locks.setdefault(session_id, asyncio.Lock())
        self._summary_lock_users[session_id] = (
            self._summary_lock_users.get(session_id, 0) + 1
        )
        try:
            async with lock:
                async with self.session_factory() as db:
                    task = await TaskRepository(db).get(task_id)
                    if task is None or task.status != TaskStatus.COMPLETED:
                        return
                    session = await SessionRepository(db).get_for_user(
                        session_id,
                        task.user_id,
                        for_update=True,
                    )
                    if session is None:
                        return
                    summary, latency_ms = await compaction.summarize_completed_turn(
                        db,
                        session=session,
                        source_task_id=task_id,
                    )
                    payload = dict(task.result_content or {})
                    usage = dict(payload.get("context_usage") or {})
                    usage.update(
                        {
                            "summary_refresh_status": (
                                "completed" if summary is not None else "not_required"
                            ),
                            "summary_refresh_latency_ms": latency_ms,
                            "generated_summary_version": (
                                summary.version if summary is not None else 0
                            ),
                            "summary_generation_method": (
                                summary.generation_method if summary is not None else ""
                            ),
                        }
                    )
                    payload["context_usage"] = usage
                    task.result_content = payload
                    await db.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "post_answer_memory_degraded task_id=%s",
                task_id,
                exc_info=True,
            )
            await self._mark_summary_refresh_failed(task_id)
        finally:
            remaining = self._summary_lock_users.get(session_id, 1) - 1
            if remaining <= 0:
                self._summary_lock_users.pop(session_id, None)
                if self._summary_locks.get(session_id) is lock:
                    self._summary_locks.pop(session_id, None)
            else:
                self._summary_lock_users[session_id] = remaining

    async def _mark_summary_refresh_failed(self, task_id: str) -> None:
        try:
            async with self.session_factory() as db:
                task = await TaskRepository(db).get(task_id)
                if task is None:
                    return
                payload = dict(task.result_content or {})
                usage = dict(payload.get("context_usage") or {})
                usage["summary_refresh_status"] = "failed"
                payload["context_usage"] = usage
                task.result_content = payload
                await db.commit()
        except Exception:
            logger.warning(
                "summary_refresh_status_update_failed task_id=%s",
                task_id,
                exc_info=True,
            )

    @staticmethod
    def _track(
        tasks: dict[str, asyncio.Task[None]],
        task_id: str,
        background: asyncio.Task[None],
    ) -> None:
        tasks[task_id] = background
        background.add_done_callback(
            lambda completed: TaskPostProcessingService._remove_if_current(
                tasks,
                task_id,
                completed,
            )
        )

    @staticmethod
    def _remove_if_current(
        tasks: dict[str, asyncio.Task[None]],
        task_id: str,
        completed: asyncio.Task[None],
    ) -> None:
        if tasks.get(task_id) is completed:
            tasks.pop(task_id, None)
