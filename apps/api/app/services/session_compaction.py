from __future__ import annotations

import hashlib
from time import perf_counter
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.conversation import ConversationContextBundle
from app.core.config import Settings
from app.models import SessionModel, SessionSummaryModel
from app.models.entities import utc_now
from app.repositories import ConversationRepository, RuntimeContextRepository
from app.services.context_budget import ContextBudgetManager
from app.services.runtime_safety import sanitize_runtime_text
from app.services.session_working_state import SessionWorkingStateService


class SessionCompactionService:
    def __init__(self, settings: Settings, budget: ContextBudgetManager) -> None:
        self.settings = settings
        self.budget = budget

    async def compact_if_needed(
        self,
        db: AsyncSession,
        *,
        session: SessionModel,
        bundle: ConversationContextBundle,
    ) -> tuple[SessionSummaryModel | None, float]:
        ratio = bundle.token_estimate / max(1, bundle.budget)
        if (
            not session.context_compaction_enabled
            or (
                session.message_count < self.settings.context_summary_message_trigger
                and ratio < self.settings.context_compaction_trigger_ratio
            )
        ):
            return None, 0
        started = perf_counter()
        through = max(
            0, session.message_count - self.settings.context_recent_message_limit
        )
        runtime = RuntimeContextRepository(db)
        previous = await runtime.latest_summary(session.id)
        if through <= (previous.covers_through_sequence if previous else 0):
            return None, (perf_counter() - started) * 1000
        from_sequence = (previous.covers_through_sequence + 1) if previous else 1
        rows = await ConversationRepository(db).list_range(
            session.id,
            user_id=session.user_id,
            from_sequence=from_sequence,
            through_sequence=through,
        )
        if not rows:
            return None, (perf_counter() - started) * 1000
        state = await SessionWorkingStateService(db).get(session.id)
        turns = [
            f"{'用户' if item.role == 'user' else '助手'}："
            f"{sanitize_runtime_text(item.content_text, max_chars=500)}"
            for item in rows
            if item.status not in {"failed", "cancelled", "superseded"}
        ]
        sections = [
            f"既有历史摘要：{previous.summary_text}" if previous else "",
            f"当前目标：{state.current_goal}" if state.current_goal else "",
            "已确认事实：" + "；".join(state.confirmed_facts)
            if state.confirmed_facts
            else "",
            "用户纠正：" + "；".join(state.user_corrections)
            if state.user_corrections
            else "",
            "未完成事项：" + "；".join(state.unresolved_items)
            if state.unresolved_items
            else "",
            "历史要点：" + " ".join(turns),
        ]
        summary_text = "\n".join(item for item in sections if item)
        max_chars = self.settings.context_summary_target_tokens * 2
        summary_text = summary_text[:max_chars]
        source_ids = [
            *(previous.source_message_ids if previous else []),
            *(item.id for item in rows),
        ]
        checksum = hashlib.sha256(
            (
                (previous.source_checksum if previous else "")
                + "|"
                + "|".join(
                    f"{item.id}:{item.updated_at.isoformat()}" for item in rows
                )
            ).encode()
        ).hexdigest()
        model = SessionSummaryModel(
            id=f"summary_{uuid4().hex}",
            session_id=session.id,
            version=await runtime.next_summary_version(session.id),
            covers_from_sequence=(
                previous.covers_from_sequence if previous else from_sequence
            ),
            covers_through_sequence=through,
            summary_text=summary_text,
            structured_state=state.model_dump(mode="json"),
            source_message_ids=source_ids,
            source_checksum=checksum,
            generation_method="deterministic",
            model_name="",
            token_estimate=self.budget.estimate_text(summary_text),
            status="completed",
            created_at=utc_now(),
        )
        db.add(model)
        session.session_revision += 1
        session.updated_at = utc_now()
        await db.flush()
        return model, (perf_counter() - started) * 1000
