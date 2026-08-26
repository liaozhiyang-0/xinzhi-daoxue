from __future__ import annotations

from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import (
    AgentEventType,
    AgentRequest,
    GoalContract,
    Intent,
    RouteDecision,
    RouteStatus,
    UserRole,
)
from app.contracts.conversation import MessageStatus
from app.contracts.intent import IntentExecutionPlan
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.models import TaskModel, TaskStatus
from app.repositories import FileRepository, SessionRepository, TaskRepository
from app.services.canonical_plan_adapter import CanonicalPlanAdapter
from app.services.conversation_message_service import ConversationMessageService
from app.services.evaluation_attachment_cleanup import (
    cleanup_evaluation_attachments,
)
from app.services.event_service import append_task_event
from app.services.intent_plan import IntentPlanCompiler
from app.services.planner import PlannerService, PlannerSnapshot
from app.services.production_execution_manifest import ProductionExecutionManifest
from app.services.session_context import SessionContextService
from app.services.session_working_state import SessionWorkingStateService
from app.services.task_audit import (
    audit_for_terminal,
    audit_from_task_input,
    build_task_audit,
    replace_task_audit,
    terminal_event_data,
)
from app.services.teaching_input import normalize_teaching_options
from app.services.unified_request_preparation import UnifiedRequestPreparationService


class TaskCreationService:
    def __init__(
        self,
        db: AsyncSession,
        provider_name: str,
        settings: Settings | None = None,
        planner: PlannerService | None = None,
        manifest: ProductionExecutionManifest | None = None,
    ) -> None:
        self.db = db
        self.provider_name = provider_name
        self.settings = settings or Settings()
        self.repository = TaskRepository(db)
        self.plan_compiler = IntentPlanCompiler()
        self.planner = planner or PlannerService(self.plan_compiler)
        self.manifest = manifest
        self.goal_preparation = UnifiedRequestPreparationService(self.settings)

    @staticmethod
    def _route_failure(route: RouteDecision) -> tuple[str, str] | None:
        if route.route_status != RouteStatus.SELECTED:
            return "route_unresolved", route.reason
        availability = route.availability
        capability_failures = (
            ("enabled", "agent_disabled", "当前 Agent 已停用，请稍后重试。"),
            (
                "published",
                "agent_not_published",
                "当前 Agent 尚未发布，暂不能执行该任务。",
            ),
            (
                "input_mode_supported",
                "agent_input_not_supported",
                "当前 Agent 不支持该输入类型，请改用文字或切换支持图片的 Agent。",
            ),
            (
                "course_supported",
                "agent_course_not_supported",
                "当前 Agent 不支持该课程，请切换课程或执行路径。",
            ),
            (
                "intent_supported",
                "agent_intent_not_supported",
                "当前 Agent 不支持该任务意图，请重新描述任务。",
            ),
        )
        for key, code, message in capability_failures:
            if availability.get(key) is False:
                return code, message
        if (
            availability.get("external_retrieval_required") is True
            and availability.get("external_retrieval_available") is False
        ):
            return (
                "external_retrieval_unavailable",
                "当前外部检索能力未启用，请先配置检索服务后再重试。",
            )
        if (
            availability.get("generation_required") is True
            and availability.get("generation_available") is False
        ):
            return (
                "model_generation_required",
                "当前场景需要已配置的模型整理能力，请先完成配置后再重试。",
            )
        return None

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
        request = self.goal_preparation.attach(request)
        planner_snapshot: PlannerSnapshot | None = None
        planner_mode = self.planner.production_mode(self.settings, request)
        if planner_mode in {"controlled", "active"}:
            try:
                goal = GoalContract.model_validate(
                    request.options.get("_goal_contract", {})
                )
                planner_output = self.planner.build_authoritative(
                    request,
                    goal,
                    route,
                    settings=self.settings,
                    mode=cast(Literal["controlled", "active"], planner_mode),
                )
                planner_snapshot = planner_output.snapshot
                canonical_plan = planner_output.canonical_plan
                intent_plan = CanonicalPlanAdapter.to_intent_plan(
                    canonical_plan,
                    plan_id=f"compat:{canonical_plan.plan_id}",
                )
                request = self._with_canonical_plan(request, canonical_plan)
            except Exception as exc:
                planner_snapshot = self.planner.failed_snapshot(
                    request,
                    route,
                    error_type=type(exc).__name__,
                )
                if planner_mode == "active":
                    raise ValidationAppError(
                        "权威 Planner 未能生成有效执行计划",
                        details={
                            "error_code": "authoritative_planner_failed",
                            "error_type": type(exc).__name__,
                        },
                    ) from exc
                # Keep the compatibility request contract inspectable while
                # refusing to claim authoritative Planner success.
                intent_plan = self.plan_compiler.compile(request, route)
        else:
            intent_plan = self.plan_compiler.compile(request, route)
            if self.planner.shadow_enabled(
                self.settings
            ) or self.planner.takeover_allowed(request, self.settings):
                try:
                    planner_output = self.planner.build(
                        request,
                        route,
                        settings=self.settings,
                        intent_plan=intent_plan,
                        mode=(
                            "takeover"
                            if self.planner.takeover_allowed(request, self.settings)
                            else "shadow"
                        ),
                    )
                    planner_snapshot = planner_output.snapshot
                except Exception as exc:
                    planner_snapshot = self.planner.failed_snapshot(
                        request,
                        route,
                        error_type=type(exc).__name__,
                    )
        request = self._with_intent_plan(request, intent_plan)
        if planner_snapshot is not None:
            request = self._with_planner_snapshot(request, planner_snapshot)
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

        if self.manifest is not None:
            options = dict(request.options)
            options["_execution_surface"] = self.manifest.task_metadata()
            request = request.model_copy(update={"options": options})
        persisted_request = self._without_transient_context(request)
        task = TaskModel(
            id=request.task_id,
            session_id=request.session_id,
            user_id=request.user_id,
            course_id=request.course_id,
            intent=request.intent.value,
            status=TaskStatus.CREATED,
            provider=(self.provider_name if route.provider_required else "local_agent"),
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
        await append_task_event(
            self.db,
            task.id,
            AgentEventType.INTENT_RECOGNIZED,
            agent_id=route.agent_id,
            data=route.intent_recognition,
        )
        plan_event_data = intent_plan.model_dump(mode="json")
        if planner_snapshot is not None:
            plan_event_data["planner_snapshot"] = planner_snapshot.model_dump(
                mode="json"
            )
        await append_task_event(
            self.db,
            task.id,
            AgentEventType.PLAN_CREATED,
            agent_id=route.agent_id,
            data=plan_event_data,
        )
        if intent_plan.selected_skills:
            await append_task_event(
                self.db,
                task.id,
                AgentEventType.SKILL_SELECTED,
                agent_id=route.agent_id,
                data={"skills": intent_plan.selected_skills},
            )
        if intent_plan.selected_tools:
            await append_task_event(
                self.db,
                task.id,
                AgentEventType.TOOL_SELECTED,
                agent_id=route.agent_id,
                data={"tools": intent_plan.selected_tools},
            )
        route_failure = self._route_failure(route)
        if route_failure is not None:
            failure_code, failure_reason = route_failure
            task.status = TaskStatus.FAILED
            task.error_message = failure_reason
            task.failure_category = failure_code
            audit = audit_from_task_input(task.input_content)
            if audit:
                task.input_content = replace_task_audit(
                    task.input_content,
                    audit_for_terminal(audit, TaskStatus.FAILED.value, failure_code),
                )
            await append_task_event(
                self.db,
                task.id,
                AgentEventType.TASK_FAILED,
                agent_id=route.agent_id,
                data=terminal_event_data(
                    status=TaskStatus.FAILED.value,
                    failure_category=failure_code,
                    error_code=failure_code,
                    error_message=failure_reason,
                ),
            )
            failure_message = await ConversationMessageService(
                self.db
            ).append_terminal_failure(
                task,
                status=MessageStatus.FAILED,
                reason=failure_reason,
            )
            task.assistant_message_id = (
                failure_message.id if failure_message is not None else None
            )
            async with self.db.begin_nested():
                await cleanup_evaluation_attachments(
                    self.db,
                    self.settings,
                    task_id=task.id,
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
        scenario_contract = options.get("scenario_contract")
        if isinstance(scenario_contract, dict) and scenario_contract.get(
            "course_confirmation_required"
        ):
            detected_course = next(
                (
                    code.split(":", 1)[1].strip().upper()
                    for code in route.reason_codes
                    if code.startswith(("detected_course:", "explicit_course_marker:"))
                    and code.split(":", 1)[1].strip()
                ),
                "",
            )
            if detected_course:
                scenario_contract = dict(scenario_contract)
                resolution = dict(
                    scenario_contract.get("course_resolution") or {}
                )
                resolution.update(
                    {
                        "resolved": detected_course,
                        "source": "router_detected",
                        "confirmation_required": False,
                    }
                )
                scenario_contract.update(
                    {
                        "course": detected_course,
                        "course_resolution": resolution,
                        "course_confirmation_required": False,
                    }
                )
                options["scenario_contract"] = scenario_contract
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
        options["_audit"] = build_task_audit(
            request.model_copy(update={"options": options}),
            route,
            canonical_input=canonical_input,
        )
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
    def _with_intent_plan(
        request: AgentRequest, plan: IntentExecutionPlan
    ) -> AgentRequest:
        options = dict(request.options)
        options["_intent_plan"] = plan.model_dump(mode="json")
        options["intent_capabilities"] = list(plan.capabilities)
        options["selected_tools"] = list(plan.selected_tools)
        options["selected_skills"] = list(plan.selected_skills)
        return request.model_copy(update={"options": options})

    @staticmethod
    def _with_planner_snapshot(
        request: AgentRequest, snapshot: PlannerSnapshot
    ) -> AgentRequest:
        options = dict(request.options)
        options["_planner_snapshot"] = snapshot.model_dump(mode="json")
        return request.model_copy(update={"options": options})

    @staticmethod
    def _with_canonical_plan(
        request: AgentRequest, plan: object
    ) -> AgentRequest:
        options = dict(request.options)
        if hasattr(plan, "model_dump"):
            options["_canonical_plan"] = plan.model_dump(mode="json")
        return request.model_copy(update={"options": options})

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
