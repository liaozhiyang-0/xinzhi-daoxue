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
from app.services.course_material_manifest import (
    REVOCATION_STATE_UNAVAILABLE,
    collect_material_source_refs,
    load_material_revocation_version,
    load_revoked_material_ids,
    material_id_from_source_ref,
)
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
        course = course_id.upper()
        runtime = RuntimeContextRepository(db)
        memories = MemoryRepository(db)
        messages = ConversationRepository(db)
        revoked_material_ids = load_revoked_material_ids(
            self.settings.knowledge_index_path
        )
        material_revocation_version = load_material_revocation_version(
            self.settings.knowledge_index_path
        )
        # A session may legitimately switch courses.  Selecting the globally
        # newest summary first makes a newer AE summary hide an older, still
        # valid CT summary; that silently breaks follow-up continuity.  The
        # repository already performs the bounded course-safe selection.
        summary = await runtime.latest_summary_for_course(session_id, course)
        summary_source_ids = (
            list(summary.source_message_ids)
            if summary is not None
            and isinstance(summary.source_message_ids, list)
            else []
        )
        summary_source_models = (
            await messages.list_by_ids(
                session_id,
                user_id=user_id,
                message_ids=summary_source_ids,
            )
            if summary is not None
            else []
        )
        summary_sources_traceable = (
            bool(summary_source_ids)
            and len(summary_source_models) == len(set(summary_source_ids))
        )
        summary_contains_revoked_material = any(
            self._contains_revoked_material(item, revoked_material_ids)
            for item in summary_source_models
        )
        state = await SessionWorkingStateService(db).get(session_id)
        if summary is not None and (
            not self._summary_matches_course(summary, course)
            or self._contains_revoked_material(summary, revoked_material_ids)
            or not summary_sources_traceable
            or summary_contains_revoked_material
        ):
            summary = None
        memory_revision = (
            await memories.max_revision(user_id) if session.memory_enabled else 0
        )
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
                "revoked_material_ids": sorted(revoked_material_ids),
                "material_revocation_version": material_revocation_version,
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

        recent_models = await messages.list_recent(
            session_id,
            user_id=user_id,
            limit=self.settings.context_recent_message_limit,
        )
        filtered_recent_models = [
            item
            for item in recent_models
            if item.id != current_message_id
            and self._message_matches_course(item, course)
            and not self._contains_revoked_material(item, revoked_material_ids)
        ]
        recent = [
            self._context_message(item)
            for item in filtered_recent_models
        ]
        oldest_sequence = (
            filtered_recent_models[0].sequence
            if filtered_recent_models
            else 1
        )
        older_models = (
            await messages.list_older(
                session_id,
                user_id=user_id,
                before_sequence=oldest_sequence,
                limit=self.settings.context_relevant_older_limit * 3,
            )
            if (
                self.settings.context_relevant_older_limit > 0
                and len(recent_models) >= self.settings.context_recent_message_limit
                and oldest_sequence > 1
            )
            else []
        )
        older_models = [
            item
            for item in older_models
            if not self._contains_revoked_material(item, revoked_material_ids)
        ]
        older = self._select_relevant(
            [self._context_message(item) for item in older_models],
            recent[-1].content_text if recent else "",
            course,
        )[: self.settings.context_relevant_older_limit]
        memory_models = (
            await memories.list_for_user(
                user_id,
                course_id=course,
                limit=self.settings.context_memory_limit * 2,
            )
            if session.memory_enabled and self.settings.context_memory_limit > 0
            else []
        )
        memory_models = self._select_memories(
            memory_models,
            recent[-1].content_text if recent else "",
            course,
        )[: self.settings.context_memory_limit]
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
        metadata = model.metadata_data if isinstance(model.metadata_data, dict) else {}
        return ContextMessage(
            message_id=model.id,
            sequence=model.sequence,
            role=MessageRole(model.role),
            content_text=text[:4000],
            course_id=str(metadata.get("course_id", "")),
            is_correction=any(
                marker in text for marker in ("纠正", "不是", "改为", "应为")
            ),
        )

    @staticmethod
    def _message_matches_course(model: Any, course_id: str) -> bool:
        metadata = model.metadata_data if isinstance(model.metadata_data, dict) else {}
        message_course = str(metadata.get("course_id", "")).strip()
        return not message_course or message_course.upper() == course_id

    @staticmethod
    def _summary_matches_course(model: Any, course_id: str) -> bool:
        structured = (
            model.structured_state
            if isinstance(model.structured_state, dict)
            else {}
        )
        summary_course = str(structured.get("course_id", "")).strip()
        return bool(summary_course) and summary_course.upper() == course_id

    @staticmethod
    def _contains_revoked_material(
        model: Any,
        revoked_material_ids: set[str],
    ) -> bool:
        if not revoked_material_ids:
            return False
        refs = collect_material_source_refs(
            getattr(model, "structured_state", None)
            if hasattr(model, "structured_state")
            else {
                "metadata": getattr(model, "metadata_data", None),
                "content_data": getattr(model, "content_data", None),
            }
        )
        return any(
            material_id_from_source_ref(ref) in revoked_material_ids
            or (
                REVOCATION_STATE_UNAVAILABLE in revoked_material_ids
                and material_id_from_source_ref(ref) is not None
            )
            for ref in refs
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
    def _select_memories(
        memories: list[Any],
        current_text: str,
        course_id: str,
    ) -> list[Any]:
        query_tokens = {
            item for item in current_text.casefold() if item.isalnum()
        }

        def score(item: Any) -> tuple[int, int, float, int]:
            content = str(item.content)
            overlap = len(query_tokens.intersection(content.casefold()))
            stable_preference = int(
                item.memory_type
                in {
                    "preference",
                    "learning_preference",
                    "stable_profile",
                }
            )
            course_match = int(
                item.scope == "course"
                and str(item.course_id or "").upper() == course_id
            )
            return (
                course_match,
                stable_preference,
                float(item.importance),
                overlap,
            )

        return sorted(memories, key=score, reverse=True)

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
