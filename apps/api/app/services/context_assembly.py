from __future__ import annotations

from time import perf_counter
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.conversation import (
    ContextMessage,
    ConversationContextBundle,
    MessageRole,
)
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.models.entities import LearnerKnowledgeStateModel
from app.repositories import (
    ConversationRepository,
    MemoryRepository,
    RuntimeContextRepository,
    SessionRepository,
)
from app.services.context_budget import ContextBudgetManager
from app.services.context_cache import ContextAssemblyCache
from app.services.session_working_state import SessionWorkingStateService


class ContextAssemblyService:
    def __init__(
        self,
        settings: Settings,
        cache: ContextAssemblyCache,
        budget: ContextBudgetManager,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self.budget = budget

    async def assemble(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        user_id: str,
        current_message_id: str | None,
        course_id: str,
        task_family: str,
        agent_id: str,
        rag_context_version: str = "",
    ) -> ConversationContextBundle:
        started = perf_counter()
        sessions = SessionRepository(db)
        session = await sessions.get_for_user(session_id, user_id)
        if session is None:
            raise NotFoundError("会话不存在", details={"session_id": session_id})
        runtime = RuntimeContextRepository(db)
        memories = MemoryRepository(db)
        summary = await runtime.latest_summary(session_id)
        memory_revision = await memories.max_revision(user_id)
        cache_key = self.cache.key(
            {
                "session_id": session_id,
                "session_revision": session.session_revision,
                "current_message_id": current_message_id or "",
                "task_family": task_family,
                "course_id": course_id.upper(),
                "agent_id": agent_id,
                "context_config_version": self.settings.context_config_version,
                "memory_revision": memory_revision,
                "summary_version": summary.version if summary else 0,
                "rag_context_version": rag_context_version,
            }
        )
        cached, backend = await self.cache.get(cache_key)
        if cached is not None:
            return cached.model_copy(
                update={
                    "cache_status": "hit",
                    "cache_backend": backend,
                    "build_latency_ms": (perf_counter() - started) * 1000,
                }
            )

        messages = ConversationRepository(db)
        recent_models = await messages.list_recent(
            session_id,
            user_id=user_id,
            limit=self.settings.context_recent_message_limit,
        )
        course = course_id.upper()
        recent = [
            self._context_message(item)
            for item in recent_models
            if not item.metadata_data.get("course_id")
            or str(item.metadata_data.get("course_id", "")).upper() == course
        ]
        oldest_sequence = recent_models[0].sequence if recent_models else 1
        older_models = await messages.list_older(
            session_id,
            user_id=user_id,
            before_sequence=oldest_sequence,
            limit=self.settings.context_relevant_older_limit * 3,
        )
        older = self._select_relevant(
            [self._context_message(item) for item in older_models],
            recent[-1].content_text if recent else "",
            course,
        )[: self.settings.context_relevant_older_limit]
        state = await SessionWorkingStateService(db).get(session_id)
        memory_models = (
            await memories.list_for_user(
                user_id,
                course_id=course,
                limit=self.settings.context_memory_limit,
            )
            if session.memory_enabled
            else []
        )
        memory_items: list[dict[str, object]] = [
            {
                "memory_id": item.id,
                "memory_type": item.memory_type,
                "scope": item.scope,
                "course_id": item.course_id,
                "content": item.content,
            }
            for item in memory_models
        ]
        learner_context = await self._learner_context(db, user_id, course)
        summary_text = summary.summary_text if summary else ""
        fixed_text = "\n".join(
            [
                summary_text,
                state.current_goal,
                *state.confirmed_facts,
                *state.user_corrections,
            ]
        )
        decision = self.budget.apply(
            fixed_text=fixed_text,
            recent_messages=recent,
            older_messages=older,
            memories=memory_items,
        )
        ratio = decision.token_estimate / max(1, decision.budget)
        bundle = ConversationContextBundle(
            session_id=session_id,
            current_message_id=current_message_id,
            session_summary=summary_text,
            summary_id=summary.id if summary else None,
            summary_version=summary.version if summary else 0,
            recent_messages=decision.recent_messages,
            relevant_earlier_messages=decision.older_messages,
            active_memories=decision.memories,
            learner_context=learner_context,
            working_state=state,
            pinned_facts=list(state.confirmed_facts),
            unresolved_items=list(state.unresolved_items),
            token_estimate=decision.token_estimate,
            budget=decision.budget,
            estimation_method=decision.estimation_method,
            compaction_applied=bool(summary) and ratio >= 0,
            context_trimmed=decision.trimmed,
            cache_status="miss",
            cache_backend="memory",
            build_latency_ms=(perf_counter() - started) * 1000,
            source_message_ids=[
                item.message_id
                for item in decision.recent_messages + decision.older_messages
            ],
            source_memory_ids=[
                str(item.get("memory_id", "")) for item in decision.memories
            ],
        )
        backend = await self.cache.set(cache_key, bundle)
        return bundle.model_copy(update={"cache_backend": backend})

    @staticmethod
    def _context_message(model: Any) -> ContextMessage:
        text = model.content_text
        return ContextMessage(
            message_id=model.id,
            sequence=model.sequence,
            role=MessageRole(model.role),
            content_text=text[:4000],
            course_id=str(model.metadata_data.get("course_id", "")),
            is_correction=any(
                marker in text for marker in ("纠正", "不是", "改为", "应为")
            ),
        )

    @staticmethod
    def _select_relevant(
        messages: list[ContextMessage], current_text: str, course_id: str
    ) -> list[ContextMessage]:
        tokens = {item for item in current_text if "\u4e00" <= item <= "\u9fff"}
        candidates = [
            item
            for item in messages
            if not item.course_id or item.course_id.upper() == course_id
        ]
        return sorted(
            candidates,
            key=lambda item: (
                item.is_correction,
                len(tokens.intersection(item.content_text)),
                item.sequence,
            ),
            reverse=True,
        )

    @staticmethod
    async def _learner_context(
        db: AsyncSession, user_id: str, course_id: str
    ) -> dict[str, Any]:
        query = (
            select(LearnerKnowledgeStateModel)
            .where(
                LearnerKnowledgeStateModel.user_id == user_id,
                LearnerKnowledgeStateModel.course_id == course_id,
            )
            .order_by(desc(LearnerKnowledgeStateModel.updated_at))
            .limit(5)
        )
        rows = list((await db.scalars(query)).all())
        return {
            "source": "LearnerKnowledgeState",
            "items": [
                {
                    "knowledge_point": item.knowledge_point,
                    "mastery_score": item.mastery_score,
                }
                for item in rows
            ],
        }
