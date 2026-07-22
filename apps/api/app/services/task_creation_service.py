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
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.models import TaskModel, TaskStatus
from app.repositories import FileRepository, SessionRepository, TaskRepository
from app.services.event_service import append_task_event
from app.services.session_context import SessionContextService


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
    ) -> TaskModel:
        request = self._with_route_context(request, route)
        session = await SessionRepository(self.db).get(request.session_id)
        if session is None:
            raise NotFoundError(
                "任务引用的会话不存在",
                details={"session_id": request.session_id},
            )
        request = SessionContextService(self.settings).apply(session, request)
        if await self.repository.get(request.task_id) is not None:
            raise ConflictError(
                "task_id 已存在，拒绝重复执行",
                details={"task_id": request.task_id},
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

        task = TaskModel(
            id=request.task_id,
            session_id=request.session_id,
            user_id=request.user_id,
            course_id=request.course_id,
            intent=request.intent.value,
            status=TaskStatus.CREATED,
            provider=self.provider_name,
            agent_id=route.agent_id,
            route_status=route.route_status.value,
            route_reason=route.reason,
            input_content=request.model_dump(mode="json"),
            parent_task_id=parent_task_id,
            attempt=attempt,
        )
        await self.repository.add(task)
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
