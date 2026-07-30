from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import (
    AgentEventType,
    AgentRequest,
    Intent,
    RouteDecision,
    RouteStatus,
    UserRole,
)
from app.contracts.conversation import MessageStatus
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.models import TaskModel, TaskStatus
from app.repositories import FileRepository, SessionRepository, TaskRepository
from app.services.conversation_message_service import ConversationMessageService
from app.services.event_service import append_task_event
from app.services.session_context import SessionContextService
from app.services.session_working_state import SessionWorkingStateService
from app.services.teaching_input import normalize_teaching_options


class TaskCreationService:
    def __init__(
        self, db: AsyncSession, provider_name: str, settings: Settings | None = None
    ) -> None:
        self.db = db
        self.provider_name = provider_name
        self.settings = settings or Settings()
        self.repository = TaskRepository(db)

    async def create_queued(
        self,
        request: AgentRequest,
        *,
        route: RouteDecision,
        parent_task_id: str | None = None,
        attempt: int = 1,
        existing_user_message_id: str | None = None,
    ) -> TaskModel:
        teaching_options, _, _ = normalize_teaching_options(request.options)
        request = request.model_copy(update={"options": teaching_options})
        request = self._with_route_context(request, route)
        session = await SessionRepository(self.db).get_for_user(
            request.session_id, request.user_id, for_update=True
        )
        if session is None:
            raise NotFoundError(
                "任务引用的会话不存在",
                details={"session_id": request.session_id},
            )
        request = SessionContextService(self.settings).apply(session, request)
        idempotency_key = str(request.options.get("idempotency_key", "")).strip()
        if idempotency_key:
            if not 8 <= len(idempotency_key) <= 128:
                raise ValidationAppError("idempotency_key 长度必须为 8 到 128")
            existing = await self.repository.get_by_idempotency_key(
                request.user_id, idempotency_key
            )
            if existing is not None:
                return existing
        if await self.repository.get(request.task_id) is not None:
            raise ConflictError(
                "task_id 已存在，拒绝重复执行",
                details={"task_id": request.task_id},
            )
        image_count = sum(
            item.content_type.startswith("image/") for item in request.attachments
        )
        if image_count > self.settings.upload_max_images:
            raise ValidationAppError(
                f"一次任务最多支持 {self.settings.upload_max_images} 张图片",
                details={
                    "image_count": image_count,
                    "max_images": self.settings.upload_max_images,
                },
            )
        files = []
        for attachment in request.attachments:
            file_model = await FileRepository(self.db).get(attachment.file_id)
            if file_model is None:
                raise NotFoundError(
                    "附件不存在", details={"file_id": attachment.file_id}
                )
            if (
                file_model.filename != attachment.filename
                or file_model.content_type != attachment.content_type
                or file_model.size_bytes != attachment.size_bytes
                or file_model.storage_key != attachment.storage_key
                or file_model.checksum_sha256 != attachment.checksum_sha256
            ):
                raise ValidationAppError(
                    "附件元数据与服务器记录不一致",
                    details={"file_id": attachment.file_id},
                )
            if file_model.task_id and file_model.task_id != request.task_id:
                raise ConflictError(
                    "附件已关联其他任务",
                    details={"file_id": attachment.file_id},
                )
            files.append(file_model)

        persisted_request = self._without_transient_context(request)
        task = TaskModel(
            id=request.task_id,
            session_id=request.session_id,
            user_id=request.user_id,
            course_id=request.course_id,
            intent=request.intent.value,
            status=TaskStatus.CREATED,
            provider=(
                self.provider_name if route.provider_required else "local_agent"
            ),
            agent_id=route.agent_id,
            route_status=route.route_status.value,
            route_reason=route.reason,
            input_content=persisted_request.model_dump(mode="json"),
            parent_task_id=parent_task_id,
            attempt=attempt,
            idempotency_key=idempotency_key or None,
            max_attempts=max(1, min(10, int(request.options.get("max_attempts", 3)))),
        )
        await self.repository.add(task)
        if existing_user_message_id:
            task.user_message_id = existing_user_message_id
        else:
            user_message = await ConversationMessageService(
                self.db
            ).append_user_for_task(task, request, session=session)
            task.user_message_id = user_message.id
            await SessionWorkingStateService(self.db).update_from_user(
                request, user_message.id
            )
        for file_model in files:
            file_model.task_id = task.id
            file_model.expires_at = None
        await append_task_event(self.db, task.id, AgentEventType.TASK_CREATED)
        route_event = (
            AgentEventType.ROUTE_SELECTED
            if route.route_status == RouteStatus.SELECTED
            else AgentEventType.ROUTE_UNSUPPORTED
        )
        await append_task_event(
            self.db,
            task.id,
            route_event,
            agent_id=route.agent_id,
            data=route.model_dump(mode="json"),
        )
        if route.route_status != RouteStatus.SELECTED:
            task.status = TaskStatus.FAILED
            task.error_message = route.reason
            await append_task_event(
                self.db,
                task.id,
                AgentEventType.TASK_FAILED,
                agent_id=route.agent_id,
                data={"error_code": "route_unresolved"},
            )
            failure_message = await ConversationMessageService(
                self.db
            ).append_terminal_failure(
                task,
                status=MessageStatus.FAILED,
                reason=route.reason,
            )
            task.assistant_message_id = (
                failure_message.id if failure_message is not None else None
            )
            await self.db.commit()
            return task
        task.status = TaskStatus.QUEUED
        await append_task_event(self.db, task.id, AgentEventType.TASK_QUEUED)
        await self.db.commit()
        return task

    @staticmethod
    def _with_route_context(
        request: AgentRequest, route: RouteDecision
    ) -> AgentRequest:
        options = dict(request.options)
        options["_routing"] = route.model_dump(mode="json")
        options["task_subtype"] = route.task_subtype
        options["secondary_intents"] = list(route.secondary_intents)
        options["requires_pipeline"] = route.requires_pipeline
        options["available_agents"] = [
            item.agent_id for item in route.candidate_agents if item.available
        ]
        options["candidate_agents"] = [
            item.model_dump(mode="json") for item in route.candidate_agents
        ]
        options["local_confidence"] = route.local_confidence
        options["_material_extraction"] = dict(route.material_extraction)
        extracted = route.material_extraction.get("materials", {})
        if isinstance(extracted, dict):
            options.update({str(key): value for key, value in extracted.items()})
        canonical_input = dict(request.canonical_input)
        if isinstance(extracted, dict):
            for key, value in extracted.items():
                canonical_input.setdefault(str(key), value)
        if route.fallback_used and route.fallback_instruction:
            for key in ("text", "question", "problem", "query", "prompt"):
                value = canonical_input.get(key)
                if isinstance(value, str) and value.strip():
                    canonical_input[key] = (
                        f"{route.fallback_instruction}\n\n{value.strip()}"
                    )
                    break
        updates: dict[str, object] = {
            "canonical_input": canonical_input,
            "options": options,
            "course_id": route.course_id,
            "intent": Intent(route.intent),
        }
        if route.inferred_user_role:
            updates["user_role"] = UserRole(route.inferred_user_role)
        return request.model_copy(update=updates)

    @staticmethod
    def _without_transient_context(request: AgentRequest) -> AgentRequest:
        options = dict(request.options)
        for key in (
            "conversation_context",
            "recent_messages",
            "active_memories",
            "working_state",
        ):
            options.pop(key, None)
        conversation_summary = str(options.get("conversation_summary", ""))
        options["conversation_summary"] = conversation_summary[:800]
        return request.model_copy(update={"options": options})
