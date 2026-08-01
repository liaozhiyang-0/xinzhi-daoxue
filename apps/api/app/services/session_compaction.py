from __future__ import annotations

import hashlib
import logging
from time import perf_counter
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.memory import MemoryCreate, MemoryScope, MemoryType
from app.core.config import Settings
from app.models import SessionModel, SessionSummaryModel
from app.models.entities import utc_now
from app.repositories import ConversationRepository, RuntimeContextRepository
from app.services.context_budget import ContextBudgetManager
from app.services.memory_service import MemoryService
from app.services.model_service import ModelService
from app.services.runtime_safety import (
    contains_sensitive_information,
    sanitize_runtime_text,
)

logger = logging.getLogger(__name__)


class ConversationMemoryExtraction(BaseModel):
    """Strict, bounded output for the post-answer memory model call."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1600)
    current_goal: str = Field(default="", max_length=300)
    key_facts: list[str] = Field(default_factory=list, max_length=12)
    explicit_user_preferences: list[str] = Field(default_factory=list, max_length=8)
    unresolved_items: list[str] = Field(default_factory=list, max_length=8)


class SessionCompactionService:
    """Create a rolling model summary after each completed answer.

    The task result is committed before this service runs. A provider or parsing
    failure therefore cannot turn a valid answer into a failed task.
    """

    def __init__(
        self,
        settings: Settings,
        budget: ContextBudgetManager,
        model_service: ModelService | None = None,
    ) -> None:
        self.settings = settings
        self.budget = budget
        self.model_service = model_service

    async def summarize_completed_turn(
        self,
        db: AsyncSession,
        *,
        session: SessionModel,
        source_task_id: str,
    ) -> tuple[SessionSummaryModel | None, float]:
        if (
            not self.settings.conversation_memory_summary_enabled
            or not session.memory_enabled
        ):
            return None, 0

        started = perf_counter()
        runtime = RuntimeContextRepository(db)
        previous = await runtime.latest_summary(session.id)
        through = session.message_count
        if through <= 0 or (
            previous is not None and previous.covers_through_sequence >= through
        ):
            return None, (perf_counter() - started) * 1000

        from_sequence = (
            previous.covers_through_sequence + 1 if previous is not None else 1
        )
        rows = await ConversationRepository(db).list_range(
            session.id,
            user_id=session.user_id,
            from_sequence=from_sequence,
            through_sequence=through,
        )
        rows = [
            item
            for item in rows
            if item.status not in {"failed", "cancelled", "superseded"}
        ]
        if not rows:
            return None, (perf_counter() - started) * 1000

        transcript = "\n".join(
            f"{'用户' if item.role == 'user' else '助手'}："
            f"{sanitize_runtime_text(item.content_text, max_chars=4000)}"
            for item in rows
        )[: self.settings.conversation_memory_summary_max_turn_chars]
        extraction, model_name, generation_method = await self._extract(
            previous_summary=previous.summary_text if previous else "",
            transcript=transcript,
            source_task_id=source_task_id,
        )
        structured = self._structured(extraction)
        summary_text = self._summary_text(extraction)

        source_ids = list(
            dict.fromkeys(
                [
                    *(previous.source_message_ids if previous else []),
                    *(item.id for item in rows),
                ]
            )
        )
        checksum = hashlib.sha256(
            "|".join(
                [
                    previous.source_checksum if previous else "",
                    *(f"{item.id}:{item.updated_at.isoformat()}" for item in rows),
                ]
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
            structured_state=structured,
            source_message_ids=source_ids,
            source_checksum=checksum,
            generation_method=generation_method,
            model_name=model_name,
            token_estimate=self.budget.estimate_text(summary_text),
            status="completed",
            created_at=utc_now(),
        )
        db.add(model)
        if session.auto_memory_enabled:
            await self._save_explicit_preferences(
                db,
                session=session,
                extraction=extraction,
                source_message_id=rows[-1].id,
            )
        session.session_revision += 1
        session.updated_at = utc_now()
        await db.flush()
        return model, (perf_counter() - started) * 1000

    async def _extract(
        self,
        *,
        previous_summary: str,
        transcript: str,
        source_task_id: str,
    ) -> tuple[ConversationMemoryExtraction, str, str]:
        if self.model_service is not None:
            try:
                previous_for_prompt = (
                    sanitize_runtime_text(previous_summary, max_chars=4000) or "无"
                )
                response = await self.model_service.generate_json_for_task(
                    "conversation_memory_summary",
                    request_id=f"memory_{source_task_id}",
                    schema=ConversationMemoryExtraction,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "你是会话记忆整理器。只总结输入中明确出现的信息，"
                                "不要补充推断、答案或新事实。保留后续追问所需的目标、"
                                "关键数值、变量含义、用户纠正和未完成事项。"
                                "explicit_user_preferences 只能包含用户明确表达的"
                                "稳定偏好，"
                                "不能从单次提问猜测。不得保存密码、令牌、连接串、"
                                "身份证件、联系方式或其他敏感信息。输出严格 JSON。"
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                "已有会话摘要：\n"
                                f"{previous_for_prompt}"
                                "\n\n本轮新增对话：\n"
                                f"{transcript}"
                            ),
                        },
                    ],
                )
                extraction = ConversationMemoryExtraction.model_validate_json(
                    response.content
                )
                return self._sanitize_extraction(extraction), response.model, "model"
            except Exception:
                logger.warning(
                    "conversation_memory_model_degraded task_id=%s",
                    source_task_id,
                    exc_info=True,
                )

        fallback = ConversationMemoryExtraction(
            summary=sanitize_runtime_text(
                " ".join(
                    part
                    for part in (
                        previous_summary,
                        transcript.replace("\n", " "),
                    )
                    if part
                ),
                max_chars=1600,
            )
            or "本轮对话已完成，未生成可用摘要。",
        )
        return fallback, "", "deterministic_fallback"

    def _sanitize_extraction(
        self, extraction: ConversationMemoryExtraction
    ) -> ConversationMemoryExtraction:
        limit = self.settings.conversation_memory_summary_max_items

        def safe_items(values: list[str], *, max_chars: int = 300) -> list[str]:
            cleaned: list[str] = []
            for value in values:
                item = sanitize_runtime_text(value, max_chars=max_chars)
                if not item or contains_sensitive_information(item):
                    continue
                cleaned.append(item)
            return list(dict.fromkeys(cleaned))[:limit]

        summary = sanitize_runtime_text(extraction.summary, max_chars=1600)
        if contains_sensitive_information(summary):
            summary = "本轮包含不适合写入记忆的信息，已省略敏感内容。"
        goal = sanitize_runtime_text(extraction.current_goal, max_chars=300)
        if contains_sensitive_information(goal):
            goal = ""
        return extraction.model_copy(
            update={
                "summary": summary or "本轮对话已完成。",
                "current_goal": goal,
                "key_facts": safe_items(extraction.key_facts),
                "explicit_user_preferences": safe_items(
                    extraction.explicit_user_preferences
                ),
                "unresolved_items": safe_items(extraction.unresolved_items),
            }
        )

    @staticmethod
    def _structured(
        extraction: ConversationMemoryExtraction,
    ) -> dict[str, object]:
        return extraction.model_dump(mode="json")

    @staticmethod
    def _summary_text(extraction: ConversationMemoryExtraction) -> str:
        sections = [extraction.summary]
        if extraction.current_goal:
            sections.append(f"当前目标：{extraction.current_goal}")
        if extraction.key_facts:
            sections.append("关键事实：" + "；".join(extraction.key_facts))
        if extraction.unresolved_items:
            sections.append("待继续：" + "；".join(extraction.unresolved_items))
        return "\n".join(sections)

    @staticmethod
    async def _save_explicit_preferences(
        db: AsyncSession,
        *,
        session: SessionModel,
        extraction: ConversationMemoryExtraction,
        source_message_id: str,
    ) -> None:
        memory = MemoryService(db)
        for preference in extraction.explicit_user_preferences:
            try:
                await memory.create(
                    MemoryCreate(
                        user_id=session.user_id,
                        memory_type=MemoryType.LEARNING_PREFERENCE,
                        scope=MemoryScope.GLOBAL,
                        content=preference,
                        content_data={
                            "capture_mode": "model_summary_explicit_preference"
                        },
                        source_session_id=session.id,
                        source_message_id=source_message_id,
                    )
                )
            except Exception:
                logger.info(
                    "conversation_memory_preference_rejected session_id=%s",
                    session.id,
                    exc_info=True,
                )
