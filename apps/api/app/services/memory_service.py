from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.memory import (
    MemoryCreate,
    MemoryScope,
    MemoryStatus,
    MemoryType,
    MemoryUpdate,
)
from app.core.errors import NotFoundError, ValidationAppError
from app.models import MemoryModel
from app.repositories import MemoryRepository, SessionRepository
from app.services.runtime_safety import (
    contains_sensitive_information,
    sanitize_runtime_text,
)

REMEMBER_PATTERNS = (
    re.compile(r"^(?:请)?记住[：:\s]*(.+)$"),
    re.compile(r"^以后(.+)$"),
)
FORGET_PATTERN = re.compile(r"^(?:请)?忘记[：:\s]*(.*)$")
AUTO_MEMORY_PATTERNS = (
    re.compile(
        r"^(?:我(?:更)?(?:喜欢|希望|习惯|偏好)|"
        r"以后(?:回答|讲解|解题)(?:时)?(?:请)?)[：:\s]*(.+)$"
    ),
)
AUTO_PREFERENCE_MARKERS = (
    "回答",
    "讲解",
    "公式",
    "步骤",
    "思路",
    "提示",
    "答案",
    "语言",
    "中文",
    "英文",
    "latex",
    "单位",
    "详细",
    "简洁",
)


class MemoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = MemoryRepository(db)

    async def create(self, data: MemoryCreate) -> MemoryModel:
        content = sanitize_runtime_text(data.content, max_chars=1000)
        self._validate_content(content)
        conflict_key = self._conflict_key(content)
        existing_memories = await self.repository.list_for_user(
            data.user_id,
            statuses=(MemoryStatus.ACTIVE.value,),
            limit=100,
        )
        for existing in existing_memories:
            if self._normalize(existing.content) == self._normalize(content):
                return existing
        if conflict_key:
            for existing in existing_memories:
                if existing.content_data.get("conflict_key") == conflict_key:
                    existing.status = MemoryStatus.SUPERSEDED.value
                    existing.revision += 1
                    existing.updated_at = datetime.now(UTC)
        now = datetime.now(UTC)
        model = MemoryModel(
            id=f"memory_{uuid4().hex}",
            user_id=data.user_id,
            memory_type=data.memory_type.value,
            scope=data.scope.value,
            course_id=data.course_id.upper() if data.course_id else None,
            content=content,
            content_data={
                **data.content_data,
                **({"conflict_key": conflict_key} if conflict_key else {}),
            },
            tags=list(dict.fromkeys(data.tags))[:20],
            source_session_id=data.source_session_id,
            source_message_id=data.source_message_id,
            confidence=1.0,
            importance=0.8,
            status=MemoryStatus.ACTIVE.value,
            created_at=now,
            updated_at=now,
            revision=1,
        )
        await self.repository.add(model)
        await self._touch_source_session(data.source_session_id, data.user_id)
        return model

    async def update(
        self, memory_id: str, data: MemoryUpdate
    ) -> MemoryModel:
        model = await self.repository.get_for_user(memory_id, data.user_id)
        if model is None:
            raise NotFoundError("记忆不存在", details={"memory_id": memory_id})
        if data.content is not None:
            content = sanitize_runtime_text(data.content, max_chars=1000)
            self._validate_content(content)
            model.content = content
            model.content_data = {
                **model.content_data,
                "conflict_key": self._conflict_key(content),
            }
        if data.memory_type is not None:
            model.memory_type = data.memory_type.value
        if data.scope is not None:
            model.scope = data.scope.value
        if data.course_id is not None:
            model.course_id = data.course_id.upper() or None
        if data.tags is not None:
            model.tags = list(dict.fromkeys(data.tags))[:20]
        model.status = MemoryStatus.ACTIVE.value
        model.revision += 1
        model.updated_at = datetime.now(UTC)
        await self._touch_source_session(model.source_session_id, data.user_id)
        return model

    async def soft_delete(self, memory_id: str, user_id: str) -> MemoryModel:
        model = await self.repository.get_for_user(memory_id, user_id)
        if model is None:
            raise NotFoundError("记忆不存在", details={"memory_id": memory_id})
        model.status = MemoryStatus.DELETED.value
        model.revision += 1
        model.updated_at = datetime.now(UTC)
        await self._touch_source_session(model.source_session_id, user_id)
        return model

    async def restore(self, memory_id: str, user_id: str) -> MemoryModel:
        model = await self.repository.get_for_user(memory_id, user_id)
        if model is None:
            raise NotFoundError("记忆不存在", details={"memory_id": memory_id})
        model.status = MemoryStatus.ACTIVE.value
        model.revision += 1
        model.updated_at = datetime.now(UTC)
        await self._touch_source_session(model.source_session_id, user_id)
        return model

    async def forget(self, user_id: str, query: str, *, all_memories: bool) -> int:
        rows = await self.repository.list_for_user(
            user_id, statuses=(MemoryStatus.ACTIVE.value,), limit=1000
        )
        normalized = self._normalize(query)
        targets = (
            rows
            if all_memories
            else [
                item
                for item in rows
                if normalized
                and (
                    normalized in self._normalize(item.content)
                    or self._normalize(item.content) in normalized
                )
            ]
        )
        for item in targets:
            item.status = MemoryStatus.DELETED.value
            item.revision += 1
            item.updated_at = datetime.now(UTC)
        return len(targets)

    async def process_explicit_intent(
        self,
        *,
        user_id: str,
        session_id: str,
        message_id: str,
        text: str,
        course_id: str,
        memory_enabled: bool,
        auto_memory_enabled: bool = False,
    ) -> tuple[int, str]:
        if not memory_enabled:
            return 0, "disabled"
        normalized = " ".join(text.split())
        forget = FORGET_PATTERN.match(normalized)
        if forget:
            query = forget.group(1).strip()
            count = await self.forget(user_id, query, all_memories=not query)
            return count, "forgotten"
        for pattern in REMEMBER_PATTERNS:
            match = pattern.match(normalized)
            if not match:
                continue
            content = match.group(1).strip()
            if not content:
                return 0, "empty"
            await self.create(
                MemoryCreate(
                    user_id=user_id,
                    memory_type=self._memory_type(content),
                    scope=MemoryScope.GLOBAL,
                    course_id=None,
                    content=content,
                    source_session_id=session_id,
                    source_message_id=message_id,
                )
            )
            return 1, "remembered"
        if auto_memory_enabled:
            content = self._automatic_preference(normalized)
            if content:
                await self.create(
                    MemoryCreate(
                        user_id=user_id,
                        memory_type=self._memory_type(content),
                        scope=MemoryScope.GLOBAL,
                        course_id=None,
                        content=content,
                        content_data={"capture_mode": "automatic_opt_in"},
                        source_session_id=session_id,
                        source_message_id=message_id,
                    )
                )
                return 1, "auto_remembered"
        return 0, "none"

    @staticmethod
    def _validate_content(content: str) -> None:
        if contains_sensitive_information(content):
            raise ValidationAppError("该内容包含敏感信息，不能保存为长期记忆")

    @staticmethod
    def _normalize(content: str) -> str:
        return re.sub(r"[\s，。！？、；：,.!?;:]+", "", content).lower()

    @staticmethod
    def _conflict_key(content: str) -> str:
        rules = {
            "answer_detail": ("简短", "简洁", "完整推导", "详细推导", "详细回答"),
            "latex": ("latex", "公式格式"),
            "approximation": ("近似", "精确值"),
            "language": ("中文", "英文"),
            "teaching_style": ("先给思路", "提示式", "直接答案"),
        }
        lowered = content.lower()
        return next(
            (
                key
                for key, markers in rules.items()
                if any(item in lowered for item in markers)
            ),
            "",
        )

    @staticmethod
    def _memory_type(content: str) -> MemoryType:
        if any(item in content for item in ("讲解", "提示", "思路", "学习")):
            return MemoryType.LEARNING_PREFERENCE
        return MemoryType.PREFERENCE

    @staticmethod
    def _automatic_preference(text: str) -> str:
        if len(text) > 240 or not any(
            marker in text.casefold() for marker in AUTO_PREFERENCE_MARKERS
        ):
            return ""
        for pattern in AUTO_MEMORY_PATTERNS:
            match = pattern.match(text)
            if match and match.group(1).strip():
                return text
        return ""

    async def _touch_source_session(
        self, session_id: str | None, user_id: str
    ) -> None:
        if not session_id:
            return
        session = await SessionRepository(self.db).get_for_user(session_id, user_id)
        if session is not None:
            session.session_revision += 1
            session.updated_at = datetime.now(UTC)
