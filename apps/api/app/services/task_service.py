from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AgentRegistry, SessionRouteContext, TaskRouter
from app.contracts import (
    AgentEvent,
    AgentEventType,
    AgentRequest,
    AgentResult,
    Artifact,
    InputMode,
    RouteDecision,
    RouteStatus,
)
from app.core.config import Settings
from app.core.errors import (
    AppError,
    NotFoundError,
    ProviderError,
    RouteUnresolvedError,
    ValidationAppError,
)
from app.models import (
    AgentRunModel,
    ArtifactModel,
    TaskEventModel,
    TaskModel,
    TaskStatus,
)
from app.providers.base import AgentProvider
from app.providers.xingchen import json_object_from_answer
from app.repositories import SessionRepository, TaskRepository
from app.services.knowledge_base import KnowledgeBaseService, KnowledgeSnippet
from app.services.workflow_cache import WorkflowCache

logger = logging.getLogger(__name__)
TEXT_FIELDS = ("text", "question", "problem", "query", "prompt")
IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg"}
KB_WARNING = "本地知识库暂时不可用，本次未附加课程资料。"
CACHE_WARNING = "缓存暂时不可用。"


@dataclass(frozen=True, slots=True)
class ValidatedInput:
    mode: InputMode
    text: str
    text_field: str


class TaskService:
    def __init__(
        self,
        db: AsyncSession,
        provider: AgentProvider,
        *,
        settings: Settings | None = None,
        registry: AgentRegistry | None = None,
        router: TaskRouter | None = None,
        knowledge_base: KnowledgeBaseService | None = None,
        cache: WorkflowCache | None = None,
    ) -> None:
        self.db = db
        self.provider = provider
        self.settings = settings or Settings()
        self.registry = registry or AgentRegistry()
        self.router = router or TaskRouter(
            self.registry, self.settings.local_route_confidence_threshold
        )
        self.knowledge_base = knowledge_base or KnowledgeBaseService(self.settings)
        self.cache = cache or WorkflowCache(self.settings, self.registry)
        self.repository = TaskRepository(db)

    @property
    def provider_name(self) -> str:
        explicit = getattr(self.provider, "provider_name", "")
        if isinstance(explicit, str) and explicit:
            return explicit
        name = self.provider.__class__.__name__.lower()
        if "xingchen" in name:
            return "xingchen"
        if "mock" in name:
            return "mock"
        return name.replace("agentprovider", "").replace("cloudprovider", "")

    async def _event(
        self,
        task_id: str,
        event_type: AgentEventType,
        *,
        agent_id: str = "",
        data: dict[str, Any] | None = None,
    ) -> None:
        event = AgentEvent(
            task_id=task_id,
            type=event_type,
            agent_id=agent_id,
            data=data or {},
        )
        await self.repository.add_event(
            TaskEventModel(
                id=event.event_id,
                task_id=task_id,
                event_type=event.type.value,
                event_data=event.model_dump(mode="json"),
                created_at=event.timestamp,
            )
        )

    @staticmethod
    def validate_input(request: AgentRequest) -> ValidatedInput:
        text_parts: list[str] = []
        text_field = "text"
        for field in TEXT_FIELDS:
            value = request.canonical_input.get(field)
            if isinstance(value, str) and value.strip():
                if not text_parts:
                    text_field = field
                text_parts.append(value.strip())
        text = "\n".join(dict.fromkeys(text_parts))
        if len(request.attachments) > 1:
            raise ValidationAppError(
                "当前版本暂只支持单张图片，请将完整题目整理为一张截图。"
            )
        if request.attachments:
            attachment = request.attachments[0]
            if attachment.content_type == "application/pdf":
                raise ValidationAppError(
                    "当前版本暂不直接解析 PDF，请先转换为单张清晰图片。"
                )
            if attachment.content_type not in IMAGE_CONTENT_TYPES:
                raise ValidationAppError("当前版本仅支持 PNG、JPG 或 JPEG 图片附件。")
            if attachment.size_bytes <= 0:
                raise ValidationAppError("图片文件为空或已损坏。")
            mode = InputMode.TEXT_AND_SINGLE_IMAGE if text else InputMode.SINGLE_IMAGE
            return ValidatedInput(mode, text, text_field)
        if not text:
            raise ValidationAppError("请输入问题文字或上传一张清晰图片。")
        return ValidatedInput(InputMode.TEXT, text, text_field)

    async def create_and_run(
        self, request: AgentRequest, *, agent_id: str | None = None
    ) -> TaskModel:
        del agent_id
        session = await SessionRepository(self.db).get(request.session_id)
        if session is None:
            raise NotFoundError(
                "任务引用的会话不存在", details={"session_id": request.session_id}
            )
        validated = self.validate_input(request)
        routing_started = perf_counter()
        previous = await self.repository.latest_completed_for_session(
            request.session_id
        )
        route_context = SessionRouteContext(
            course_id=previous.course_id if previous else "",
            intent=previous.intent if previous else "",
            target_agent_id=previous.agent_id if previous else "",
        )
        provider_request, context_warnings = self._with_follow_up_context(
            request, validated, previous
        )
        route = self.router.route(provider_request, validated.mode, route_context)
        routing_latency_ms = int((perf_counter() - routing_started) * 1000)
        if route.route_status == RouteStatus.UNSUPPORTED:
            raise ValidationAppError(route.reason)

        task = TaskModel(
            id=request.task_id,
            session_id=request.session_id,
            user_id=request.user_id,
            course_id=route.course_id,
            intent=route.intent,
            status=TaskStatus.CREATED,
            provider=self.provider_name,
            agent_id=route.target_agent_id,
            input_content=request.model_dump(mode="json"),
        )
        await self.repository.add(task)
        await self._event(task.id, AgentEventType.TASK_CREATED)
        await self._event(
            task.id,
            AgentEventType.INPUT_VALIDATED,
            data={"input_mode": validated.mode.value},
        )
        await self._event(
            task.id,
            AgentEventType.SESSION_CONTEXT_LOADED,
            data={"history_available": previous is not None},
        )
        if route.needs_fallback:
            await self._event(
                task.id,
                AgentEventType.ROUTE_CLOUD_FALLBACK_STARTED,
                agent_id=route.target_agent_id,
            )
        else:
            await self._event(
                task.id,
                AgentEventType.ROUTE_LOCAL_SELECTED,
                agent_id=route.target_agent_id,
                data=route.model_dump(mode="json"),
            )
        task.status = TaskStatus.RUNNING
        task.started_at = AgentEvent(
            task_id=task.id, type=AgentEventType.AGENT_STARTED
        ).timestamp
        await self.db.commit()

        started = perf_counter()
        warnings = list(context_warnings)
        retrieval_latency_ms = 0
        provider_latency_ms = 0
        cache_hit = False
        try:
            if route.needs_fallback:
                fallback_started = perf_counter()
                route = await self._cloud_fallback(
                    provider_request, validated, route_context
                )
                routing_latency_ms += int((perf_counter() - fallback_started) * 1000)
                task.agent_id = route.target_agent_id
                task.course_id = route.course_id
                task.intent = route.intent
                await self._event(
                    task.id,
                    AgentEventType.ROUTE_CLOUD_FALLBACK_COMPLETED,
                    agent_id=route.target_agent_id,
                    data=route.model_dump(mode="json"),
                )

            if self.provider_name == "xingchen" and not self.registry.is_callable(
                route.target_agent_id, self.settings
            ):
                raise RouteUnresolvedError(
                    f"{route.target_agent_id} 对应云端工作流尚未启用。"
                )

            retrieval_started = perf_counter()
            snippets: list[KnowledgeSnippet] = []
            try:
                snippets = self._retrieve_knowledge(route, validated)
            except Exception as exc:  # retrieval must never block the provider
                logger.warning(
                    "knowledge_retrieval_failed task_id=%s error=%s",
                    task.id,
                    type(exc).__name__,
                )
                warnings.append(KB_WARNING)
            retrieval_latency_ms = int((perf_counter() - retrieval_started) * 1000)
            if snippets:
                await self._event(
                    task.id,
                    AgentEventType.KNOWLEDGE_RETRIEVED,
                    agent_id=route.target_agent_id,
                    data={"count": len(snippets)},
                )
                provider_request = self._with_knowledge(
                    provider_request, route, validated, snippets
                )
            source_refs = [snippet.source_ref for snippet in snippets]

            await self._event(
                task.id,
                AgentEventType.AGENT_STARTED,
                agent_id=route.target_agent_id,
                data={"provider": self.provider_name},
            )
            result: AgentResult | None = None
            cache_key = ""
            cache_allowed = self._cache_allowed(provider_request, route)
            if cache_allowed:
                cache_key = self.cache.key(
                    route.target_agent_id,
                    provider_request,
                    course_id=route.course_id,
                    intent=route.intent,
                    source_refs=source_refs,
                )
                try:
                    result = await self.cache.get(cache_key)
                except Exception as exc:  # Redis is an optional accelerator
                    logger.warning(
                        "workflow_cache_read_failed task_id=%s error=%s",
                        task.id,
                        type(exc).__name__,
                    )
                    warnings.append(CACHE_WARNING)
                if result is not None:
                    cache_hit = True
                    result = self._rekey_cached_result(result, request)
                    await self._event(
                        task.id,
                        AgentEventType.CACHE_HIT,
                        agent_id=route.target_agent_id,
                    )
                else:
                    await self._event(
                        task.id,
                        AgentEventType.CACHE_MISS,
                        agent_id=route.target_agent_id,
                    )

            if result is None:
                await self._event(
                    task.id,
                    AgentEventType.PROVIDER_REQUEST_STARTED,
                    agent_id=route.target_agent_id,
                )
                provider_started = perf_counter()
                result = await self.provider.run(
                    route.target_agent_id, provider_request, stream=False
                )
                provider_latency_ms = int((perf_counter() - provider_started) * 1000)
                await self._event(
                    task.id,
                    AgentEventType.PROVIDER_REQUEST_COMPLETED,
                    agent_id=route.target_agent_id,
                    data={"latency_ms": provider_latency_ms},
                )

            total_latency_ms = int((perf_counter() - started) * 1000)
            self._normalize_result(
                result,
                request,
                route,
                validated,
                source_refs,
                warnings,
                total_latency_ms=total_latency_ms,
                routing_latency_ms=routing_latency_ms,
                retrieval_latency_ms=retrieval_latency_ms,
                provider_latency_ms=provider_latency_ms,
                cache_hit=cache_hit,
            )
            await self._event(
                task.id,
                AgentEventType.RESULT_NORMALIZED,
                agent_id=route.target_agent_id,
            )

            if cache_allowed and not cache_hit and cache_key:
                try:
                    await self.cache.set(
                        cache_key,
                        result,
                        self.registry.cache_ttl_seconds(
                            route.target_agent_id, self.settings
                        ),
                    )
                except Exception as exc:  # Redis failure must not fail the task
                    logger.warning(
                        "workflow_cache_write_failed task_id=%s error=%s",
                        task.id,
                        type(exc).__name__,
                    )
                    if CACHE_WARNING not in result.warnings:
                        result.warnings.append(CACHE_WARNING)

            task.result_content = result.model_dump(mode="json")
            task.status = TaskStatus.COMPLETED
            task.completed_at = AgentEvent(
                task_id=task.id, type=AgentEventType.TASK_COMPLETED
            ).timestamp
            session.course_id = route.course_id
            for artifact in result.artifacts:
                self.db.add(
                    ArtifactModel(
                        id=artifact.artifact_id,
                        task_id=task.id,
                        artifact_type=artifact.artifact_type.value,
                        version=artifact.version,
                        content=artifact.content,
                        confidence=artifact.confidence,
                        created_at=artifact.created_at,
                    )
                )
            self.db.add(
                AgentRunModel(
                    task_id=task.id,
                    agent_id=route.target_agent_id,
                    provider=result.provider,
                    status=result.status.value,
                    latency_ms=total_latency_ms,
                    model_calls=int(result.metrics.get("model_calls", 0)),
                    tool_calls=int(result.metrics.get("tool_calls", 0)),
                    retrieval_calls=int(bool(snippets)),
                )
            )
            await self._event(
                task.id,
                AgentEventType.TASK_COMPLETED,
                agent_id=route.target_agent_id,
                data={
                    "artifact_count": len(result.artifacts),
                    "latency_ms": total_latency_ms,
                    "cache_hit": cache_hit,
                },
            )
        except Exception as exc:
            await self._mark_failed(task, exc, started)

        await self.db.commit()
        return await self.get(task.id)

    async def _cloud_fallback(
        self,
        request: AgentRequest,
        validated: ValidatedInput,
        context: SessionRouteContext,
    ) -> RouteDecision:
        fallback_id = "ROUTER_01_FALLBACK_V1"
        if self.provider_name == "xingchen" and not self.registry.is_callable(
            fallback_id, self.settings
        ):
            raise RouteUnresolvedError(
                "暂时无法确定该问题应进入哪类专业能力，请补充课程名称。"
            )
        payload = {
            "user_text": validated.text,
            "input_mode": validated.mode.value,
            "course_hint": request.course_id or "UNKNOWN",
            "intent_hint": request.intent.value,
            "session_course": context.course_id,
            "session_intent": context.intent,
            "available_agents": self.registry.available_routing_targets(),
            "filename": request.attachments[0].filename if request.attachments else "",
        }
        fallback_request = request.model_copy(
            update={
                "course_id": "UNKNOWN",
                "canonical_input": {
                    "text": json.dumps(payload, ensure_ascii=False, sort_keys=True)
                },
                "attachments": [],
            }
        )
        result = await self.provider.run(fallback_id, fallback_request, stream=False)
        raw = result.structured_result
        if "route_status" not in raw:
            raw = json_object_from_answer(result.answer) or {}
        target = str(raw.get("target_agent_id", ""))
        if target == fallback_id or target not in self.registry.ROUTING_TARGETS:
            raise RouteUnresolvedError(
                "暂时无法确定该问题应进入哪类专业能力，请补充课程名称。"
            )
        try:
            confidence = float(raw.get("route_confidence", 0))
        except (TypeError, ValueError) as exc:
            raise RouteUnresolvedError("云端调度结果缺少有效置信度。") from exc
        course_id = str(raw.get("course_id", "UNKNOWN")).upper()
        intent = str(raw.get("intent", "unknown"))
        if raw.get("route_status") != "selected" or not 0 <= confidence <= 1:
            raise RouteUnresolvedError("云端调度未能确定唯一目标能力。")
        return RouteDecision(
            route_status=RouteStatus.SELECTED,
            course_id=course_id,
            intent=intent,
            target_agent_id=target,
            route_confidence=confidence,
            route_source="cloud_fallback",
            reason=str(raw.get("reason", "云端调度已选择目标 Agent。")),
            input_mode=validated.mode,
            needs_knowledge=target == "LEARN_01_KNOWLEDGE_QA_V1",
        )

    def _retrieve_knowledge(
        self, route: RouteDecision, validated: ValidatedInput
    ) -> list[KnowledgeSnippet]:
        if not validated.text or validated.mode == InputMode.SINGLE_IMAGE:
            return []
        if (
            route.target_agent_id == "LEARN_01_KNOWLEDGE_QA_V1"
            and self.settings.knowledge_use_local_kb_context
        ):
            return self.knowledge_base.search(
                validated.text, route.course_id, self.settings.knowledge_kb_top_k
            )
        if (
            route.target_agent_id == "SOLVER_CT_V1"
            and self.settings.solver_use_local_kb_context
        ):
            return self.knowledge_base.search(
                validated.text, route.course_id, self.settings.solver_kb_top_k
            )
        return []

    def _with_knowledge(
        self,
        request: AgentRequest,
        route: RouteDecision,
        validated: ValidatedInput,
        snippets: list[KnowledgeSnippet],
    ) -> AgentRequest:
        if route.target_agent_id == "LEARN_01_KNOWLEDGE_QA_V1":
            limit = self.settings.knowledge_kb_max_chars
            blocks = self._knowledge_blocks(snippets, limit)
            text = (
                f"【用户问题】\n{validated.text}\n\n"
                f"【本地课程资料】\n{blocks}\n\n"
                "【讲解要求】\n请结合资料回答，但不得照抄资料。\n"
                "资料不足时明确说明，不得编造教材内容。"
            )
        else:
            limit = self.settings.solver_kb_max_chars
            blocks = self._knowledge_blocks(snippets, limit)
            text = (
                f"【用户题目】\n{validated.text}\n\n"
                f"【本地方法参考】\n{blocks}\n\n"
                "【重要约束】\n本地知识库只用于方法参考。\n"
                "题目参数、电路连接、参考方向和图中事实以用户输入为准。\n"
                "不得使用知识库内容覆盖或修改题目事实。"
            )
        canonical = dict(request.canonical_input)
        canonical[validated.text_field] = text
        options = dict(request.options)
        options["xingchen_knowledge_sources"] = [
            snippet.source_ref for snippet in snippets
        ]
        return request.model_copy(
            update={"canonical_input": canonical, "options": options}
        )

    @staticmethod
    def _knowledge_blocks(snippets: list[KnowledgeSnippet], limit: int) -> str:
        blocks: list[str] = []
        remaining = limit
        for index, snippet in enumerate(snippets, start=1):
            prefix = f"资料 {index}：\n"
            suffix = f"\n来源：{snippet.source_ref}"
            content = snippet.content[: max(0, remaining - len(prefix) - len(suffix))]
            block = prefix + content + suffix
            if len(block) > remaining:
                break
            blocks.append(block)
            remaining -= len(block)
        return "\n\n".join(blocks)

    @staticmethod
    def _with_follow_up_context(
        request: AgentRequest,
        validated: ValidatedInput,
        previous: TaskModel | None,
    ) -> tuple[AgentRequest, list[str]]:
        if request.intent.value != "follow_up_question":
            return request, []
        if previous is None:
            return request, ["当前会话没有可用的上一条已完成任务上下文。"]
        previous_input = previous.input_content.get("canonical_input", {})
        previous_question = ""
        if isinstance(previous_input, dict):
            previous_question = next(
                (
                    value.strip()
                    for key in TEXT_FIELDS
                    if isinstance((value := previous_input.get(key)), str)
                    and value.strip()
                ),
                "",
            )
        result = previous.result_content or {}
        previous_answer = str(result.get("answer", ""))
        text = (
            f"【上一次问题】\n{previous_question[:800]}\n\n"
            f"【上一次回答摘要】\n{previous_answer[:1600]}\n\n"
            f"【本次追问】\n{validated.text}"
        )
        canonical = dict(request.canonical_input)
        canonical[validated.text_field] = text
        return request.model_copy(update={"canonical_input": canonical}), []

    def _cache_allowed(self, request: AgentRequest, route: RouteDecision) -> bool:
        return bool(
            self.settings.xingchen_cache_enabled
            and self.provider_name != "mock"
            and not request.force_refresh
            and route.intent != "follow_up_question"
        )

    @staticmethod
    def _rekey_cached_result(result: AgentResult, request: AgentRequest) -> AgentResult:
        artifacts = [
            artifact.model_copy(
                update={
                    "artifact_id": Artifact().artifact_id,
                    "task_id": request.task_id,
                    "owner_id": request.user_id,
                }
            )
            for artifact in result.artifacts
        ]
        return result.model_copy(deep=True, update={"artifacts": artifacts})

    def _normalize_result(
        self,
        result: AgentResult,
        request: AgentRequest,
        route: RouteDecision,
        validated: ValidatedInput,
        source_refs: list[str],
        warnings: list[str],
        **metrics: Any,
    ) -> None:
        definition = self.registry.get(route.target_agent_id)
        result.agent_id = route.target_agent_id
        result.structured_result.update(
            {
                "mode": definition.mode,
                "course_id": route.course_id,
                "intent": route.intent,
                "route_source": route.route_source,
                "route_confidence": route.route_confidence,
                "input_mode": validated.mode.value,
            }
        )
        result.citations = list(dict.fromkeys([*result.citations, *source_refs]))
        result.warnings = list(dict.fromkeys([*result.warnings, *warnings]))
        result.metrics.update(metrics)
        result.metrics["provider_call"] = (
            "skipped" if metrics.get("cache_hit") else "completed"
        )
        if not result.artifacts:
            result.artifacts = [
                Artifact(
                    owner_id=request.user_id,
                    task_id=request.task_id,
                    course_id=route.course_id,
                    content={},
                    confidence=result.confidence,
                )
            ]
        for artifact in result.artifacts:
            artifact.owner_id = request.user_id
            artifact.task_id = request.task_id
            artifact.course_id = route.course_id
            artifact.source_refs = list(
                dict.fromkeys([*artifact.source_refs, *source_refs])
            )
            artifact.content.update(
                {
                    "mode": definition.mode,
                    "answer": result.answer,
                    "course_id": route.course_id,
                    "intent": route.intent,
                    "route_source": route.route_source,
                    "target_agent_id": route.target_agent_id,
                    "knowledge_sources": source_refs,
                    "cache_hit": bool(metrics.get("cache_hit")),
                }
            )

    async def _mark_failed(
        self, task: TaskModel, exc: Exception, started: float
    ) -> None:
        latency_ms = int((perf_counter() - started) * 1000)
        task.status = TaskStatus.FAILED
        message = exc.message if isinstance(exc, AppError) else "Provider 执行失败"
        code = exc.code if isinstance(exc, AppError) else ProviderError.code
        task.error_message = message
        task.result_content = {
            "status": "failed",
            "error_code": code,
            "answer": message,
        }
        task.completed_at = AgentEvent(
            task_id=task.id, type=AgentEventType.TASK_FAILED
        ).timestamp
        self.db.add(
            AgentRunModel(
                task_id=task.id,
                agent_id=task.agent_id,
                provider=self.provider_name,
                status=TaskStatus.FAILED.value,
                latency_ms=latency_ms,
            )
        )
        await self._event(
            task.id,
            AgentEventType.TASK_FAILED,
            agent_id=task.agent_id,
            data={"error_code": code},
        )
        logger.warning(
            "task_failed task_id=%s session_id=%s agent_id=%s error=%s",
            task.id,
            task.session_id,
            task.agent_id,
            type(exc).__name__,
        )

    async def get(self, task_id: str) -> TaskModel:
        task = await self.repository.get(task_id, with_artifacts=True)
        if task is None:
            raise NotFoundError("任务不存在", details={"task_id": task_id})
        return task

    async def list_events(self, task_id: str) -> list[TaskEventModel]:
        if await self.repository.get(task_id) is None:
            raise NotFoundError("任务不存在", details={"task_id": task_id})
        return await self.repository.list_events(task_id)
