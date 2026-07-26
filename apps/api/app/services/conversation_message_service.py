from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentRequest, AgentResult
from app.contracts.conversation import (
    MessageRole,
    MessageStatus,
    MessageVisibility,
)
from app.core.errors import NotFoundError
from app.models import ConversationMessageModel, SessionModel, TaskModel
from app.models.entities import utc_now
from app.repositories import ConversationRepository, SessionRepository
from app.services.runtime_safety import sanitize_runtime_text


class ConversationMessageService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = ConversationRepository(db)
        self.sessions = SessionRepository(db)

    async def append(
        self,
        *,
        session: SessionModel,
        user_id: str,
        role: MessageRole,
        status: MessageStatus,
        content_text: str,
        content_data: dict[str, Any] | None = None,
        source_task_id: str | None = None,
        reply_to_message_id: str | None = None,
        revision_of_message_id: str | None = None,
        attachment_ids: list[str] | None = None,
        visibility: MessageVisibility | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationMessageModel:
        existing = (
            await self.repository.get_for_task_role(source_task_id, role.value)
            if source_task_id
            else None
        )
        if existing is not None:
            return existing
        now = utc_now()
        session.message_count = int(session.message_count or 0) + 1
        session.session_revision = int(session.session_revision or 0) + 1
        session.last_message_at = now
        session.updated_at = now
        message = ConversationMessageModel(
            id=f"message_{uuid4().hex}",
            session_id=session.id,
            user_id=user_id,
            sequence=session.message_count,
            role=role.value,
            status=status.value,
            visibility=(
                visibility
                or (
                    MessageVisibility.INTERNAL
                    if role == MessageRole.TOOL
                    else MessageVisibility.USER_VISIBLE
                )
            ).value,
            content_text=sanitize_runtime_text(content_text),
            content_data=dict(content_data or {}),
            source_task_id=source_task_id,
            reply_to_message_id=reply_to_message_id,
            revision_of_message_id=revision_of_message_id,
            attachment_ids=list(attachment_ids or []),
            metadata_data=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        await self.repository.add(message)
        if role == MessageRole.USER:
            self._set_initial_title(session, message.content_text)
        return message

    async def append_user_for_task(
        self,
        task: TaskModel,
        request: AgentRequest,
        *,
        session: SessionModel,
    ) -> ConversationMessageModel:
        question = self.question_text(request)
        return await self.append(
            session=session,
            user_id=request.user_id,
            role=MessageRole.USER,
            status=MessageStatus.COMPLETED,
            content_text=question or "已提交材料任务",
            source_task_id=task.id,
            attachment_ids=[item.file_id for item in request.attachments],
            metadata={
                "course_id": request.course_id.upper(),
                "intent": request.intent.value,
            },
        )

    async def append_assistant_for_task(
        self,
        task: TaskModel,
        result: AgentResult,
        *,
        session: SessionModel,
    ) -> ConversationMessageModel:
        revision_of = None
        if task.parent_task_id:
            parent = await self.db.get(TaskModel, task.parent_task_id)
            if parent and parent.assistant_message_id:
                previous = await self.repository.get(parent.assistant_message_id)
                if previous is not None:
                    previous.status = MessageStatus.SUPERSEDED.value
                    revision_of = previous.id
        structured = result.structured_result or {}
        content_data = {
            key: structured.get(key)
            for key in (
                "presentation",
                "execution_summary",
                "evidence_view",
                "math_content",
                "business_view",
            )
            if structured.get(key) is not None
        }
        return await self.append(
            session=session,
            user_id=task.user_id,
            role=MessageRole.ASSISTANT,
            status=MessageStatus.COMPLETED,
            content_text=result.answer,
            content_data=content_data,
            source_task_id=task.id,
            reply_to_message_id=task.user_message_id,
            revision_of_message_id=revision_of,
            metadata={"course_id": task.course_id, "intent": task.intent},
        )

    async def append_terminal_failure(
        self,
        task: TaskModel,
        *,
        status: MessageStatus,
        reason: str,
    ) -> ConversationMessageModel | None:
        session = await self.sessions.get_for_user(
            task.session_id, task.user_id, for_update=True
        )
        if session is None:
            return None
        return await self.append(
            session=session,
            user_id=task.user_id,
            role=MessageRole.ASSISTANT,
            status=status,
            content_text=reason,
            content_data={"task_status": status.value},
            source_task_id=task.id,
            reply_to_message_id=task.user_message_id,
            metadata={"course_id": task.course_id, "intent": task.intent},
        )

    async def list_user_visible(
        self,
        session_id: str,
        *,
        user_id: str,
        after_sequence: int = 0,
        limit: int = 50,
    ) -> list[ConversationMessageModel]:
        session = await self.sessions.get_for_user(session_id, user_id)
        if session is None:
            raise NotFoundError("会话不存在", details={"session_id": session_id})
        return await self.repository.list_for_session(
            session_id,
            user_id=user_id,
            after_sequence=after_sequence,
            limit=limit,
            visible_only=True,
        )

    @staticmethod
    def question_text(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _set_initial_title(session: SessionModel, text: str) -> None:
        if session.title_source not in {"default", "automatic"}:
            return
        cleaned = sanitize_runtime_text(text, max_chars=120).strip(" \t\r\n，。！？")
        if not cleaned:
            return
        session.title = cleaned[:32] + ("…" if len(cleaned) > 32 else "")
        session.title_source = "automatic"
