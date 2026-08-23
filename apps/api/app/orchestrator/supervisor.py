from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

from app.agents import AgentRegistry, TaskRouter
from app.contracts import (
    AgentRequest,
    AgentRequestV2,
    AttachmentRef,
    CourseCode,
    ExecutionStatus,
    Intent,
    NodeTrace,
    OrchestrationIntent,
    RouteDecision,
    RouteStatus,
    Scene,
    TaskFamily,
    UserRole,
)
from app.multimodal.file_parser import detect_input_type
from app.observability import TraceStore
from app.orchestrator.state import XZDGraphState, new_graph_state
from app.services.intent_recognition import IntentRecognitionService
from app.services.model_service import ModelService

COURSE_KEYWORDS: tuple[tuple[CourseCode, tuple[str, ...]], ...] = (
    (CourseCode.CT, ("电路", "节点电压", "网孔", "戴维南", "电容电压", "相量")),
    (CourseCode.AE, ("模电", "模拟电子", "运放", "三极管", "放大电路")),
    (
        CourseCode.DE,
        (
            "数电",
            "数字电子",
            "逻辑门",
            "逻辑式",
            "逻辑函数",
            "真值表",
            "布尔",
            "触发器",
            "卡诺图",
            "Verilog",
        ),
    ),
    (
        CourseCode.SS,
        ("信号与系统", "卷积", "拉普拉斯变换", "系统函数", "连续时间"),
    ),
    (
        CourseCode.DSP,
        ("数字信号处理", "离散傅里叶", "z变换", "滤波器", "采样定理", "频谱"),
    ),
    (
        CourseCode.COMM,
        ("通信原理", "通信系统", "调制", "解调", "信道编码", "误码率", "信噪比"),
    ),
    (CourseCode.RF, ("高频电子", "高频电子线路", "谐振放大", "混频")),
    (
        CourseCode.EM,
        ("电磁场", "电磁波", "麦克斯韦", "电场强度", "磁场强度"),
    ),
    (CourseCode.INFO, ("信息论", "信源编码", "信道容量", "熵")),
    (
        CourseCode.EMBEDDED,
        ("嵌入式", "单片机", "微控制器", "中断服务", "定时器"),
    ),
    (CourseCode.IC, ("集成电路", "芯片设计", "版图")),
)

# Natural-language aliases used by the public chat entry point. Keep these
# separate from the original baseline vocabulary so future course additions
# can extend the map without changing the routing algorithm.
COURSE_KEYWORD_EXTENSIONS: tuple[tuple[CourseCode, tuple[str, ...]], ...] = (
    (
        CourseCode.CT,
        (
            "电路理论", "戴维宁", "诺顿", "电感", "暂态", "稳态",
            "基尔霍夫", "KCL", "KVL",
        ),
    ),
    (
        CourseCode.AE,
        (
            "模拟电路", "运算放大器", "二极管", "反馈", "振荡", "稳压", "开关稳压",
            "线性稳压", "整流", "滤波", "晶体管", "MOS管",
        ),
    ),
    (
        CourseCode.DE,
        ("数字电路", "逻辑", "锁存器", "计数器", "寄存器", "时序逻辑", "组合逻辑"),
    ),
)

EXPLANATION_MARKERS = (
    "为什么", "是什么", "什么是", "解释", "讲解", "说明", "介绍", "原理", "概念",
    "特点", "区别", "作用", "如何理解", "怎么理解", "用途", "应用",
)
KNOWLEDGE_REQUEST_MARKERS = ("本地知识库", "本地资料", "课程资料", "知识库", "检索")

FOLLOW_UP_MARKERS = ("上一问", "上一步", "这里", "刚才", "为什么这里", "继续")
SOLVE_MARKERS = (
    "求",
    "计算",
    "列方程",
    "解方程",
    "化简",
    "判断工作状态",
    "分析电路",
    "求电压",
    "求电流",
    "求功率",
    "求响应",
)


@dataclass(frozen=True, slots=True)
class PreparedTask:
    request: AgentRequest
    route: RouteDecision
    state: XZDGraphState


class XZDSupervisor:
    """Lightweight graph runner that prepares the existing non-blocking task flow."""

    supervisor_id = "XZD_SUPERVISOR"

    def __init__(
        self,
        registry: AgentRegistry,
        router: TaskRouter,
        traces: TraceStore,
        model_service: ModelService | None = None,
    ) -> None:
        self.registry = registry
        self.router = router
        self.traces = traces
        self.model_service = model_service

    def prepare(
        self,
        payload: AgentRequestV2,
        *,
        session_id: str,
        user_id: str,
        attachments: list[AttachmentRef] | None = None,
        session_context: dict[str, Any] | None = None,
    ) -> PreparedTask:
        state = new_graph_state(
            request_id=payload.request_id,
            session_id=session_id,
            user_id=user_id,
            message=payload.message,
            file_refs=[item.model_dump(mode="json") for item in payload.files],
        )
        course_started = perf_counter()
        course = self._course(payload, session_context or {})
        state["course"] = course.value
        state["trace"].append(
            self._trace(
                "identify_course",
                course_started,
                {
                    "course_hint": (
                        payload.course_hint.value if payload.course_hint else ""
                    )
                },
                {"course": course.value},
            )
        )

        intent_started = perf_counter()
        intent = self._intent(payload, session_context or {})
        state["intent"] = intent.value
        state["task_family"] = self._task_family(intent).value
        state["trace"].append(
            self._trace(
                "identify_intent",
                intent_started,
                {
                    "intent_hint": (
                        payload.intent_hint.value if payload.intent_hint else ""
                    )
                },
                {"intent": intent.value},
            )
        )

        normalize_started = perf_counter()
        effective_input_type = detect_input_type(
            payload.files, has_text=bool(payload.message)
        )
        legacy_intent = self._legacy_intent(intent)
        context = session_context or {}
        continuity_options = {
            key: context.get(key, "")
            for key in (
                "previous_course",
                "previous_agent",
                "previous_intent",
                "previous_task_id",
                "previous_task_family",
                "previous_answer_summary",
                "previous_external_query",
                "previous_external_retrieval",
                "continuity_state",
            )
            if context.get(key) not in (None, "", {})
        }
        if "previous_course" not in continuity_options:
            active_course = context.get("active_course", "")
            if active_course not in (None, "", {}):
                continuity_options["previous_course"] = active_course
        legacy = AgentRequest(
            session_id=session_id,
            user_id=user_id,
            user_role=self._user_role(payload.metadata.get("user_role")),
            scene=self._scene(legacy_intent),
            course_id=course.value,
            intent=legacy_intent,
            canonical_input={
                "text": payload.message,
                "question": payload.message,
                "previous_answer_summary": payload.previous_answer_summary or "",
            },
            attachments=attachments or [],
            options={
                **payload.metadata,
                **continuity_options,
                "request_id": payload.request_id,
                "trace_id": state["trace_id"],
                "run_id": state["run_id"],
                "input_type": effective_input_type.value,
                "debug": payload.debug,
                "previous_answer_summary": (
                    str(
                        context.get(
                            "previous_answer_summary",
                            payload.previous_answer_summary or "",
                        )
                    )
                ),
            },
        )
        state["normalized_input"] = {
            "message_chars": len(payload.message),
            "input_type": effective_input_type.value,
            "file_count": len(payload.files),
        }
        state["trace"].append(
            self._trace(
                "normalize_input",
                normalize_started,
                {"input_type": effective_input_type.value},
                dict(state["normalized_input"]),
            )
        )

        route_started = perf_counter()
        settings = self.router.settings
        if settings.planner_mode != "shadow":
            legacy = legacy.model_copy(
                update={
                    "options": {**legacy.options, "_planner_preflight": True}
                }
            )
        route = self.router.route(legacy)
        structured_intent = str(route.intent_recognition.get("intent", ""))
        if (
            settings.enable_local_knowledge_qa
            and course
            in {
                CourseCode.CT,
                CourseCode.AE,
                CourseCode.DE,
                CourseCode.SS,
                CourseCode.DSP,
                CourseCode.COMM,
            }
            and intent
            in {
                OrchestrationIntent.EXPLAIN_CONCEPT,
                OrchestrationIntent.FOLLOW_UP_QUESTION,
                OrchestrationIntent.SUMMARIZE_KNOWLEDGE,
                OrchestrationIntent.LEARNING_ADVICE,
                OrchestrationIntent.GENERAL_QA,
                OrchestrationIntent.UNKNOWN,
            }
            and structured_intent not in {
                OrchestrationIntent.ACADEMIC_SEARCH.value,
                OrchestrationIntent.ACADEMIC_WRITING.value,
                OrchestrationIntent.DATA_ANALYSIS.value,
            }
        ):
            route = self._local_knowledge_primary(legacy, route)
        image_count = sum(
            item.content_type.startswith("image/") for item in legacy.attachments
        )
        has_pdf = any(
            item.content_type == "application/pdf" for item in legacy.attachments
        )
        if image_count > 1 or has_pdf:
            route = self._safe_local_fallback(legacy, route)
            route = route.model_copy(
                update={
                    "reason": ("多图/PDF 先在本地拆分，禁止直接发送给单图视觉接口"),
                    "reason_codes": [
                        *route.reason_codes,
                        "local_multimodal_preprocessing_required",
                    ],
                }
            )
        if route.route_status != RouteStatus.SELECTED:
            route = self._safe_local_fallback(legacy, route)
        state["selected_agent"] = route.agent_id
        state["route_status"] = (
            ExecutionStatus.SUCCESS.value
            if route.route_status == RouteStatus.SELECTED
            else ExecutionStatus.FAILED.value
        )
        state["confidence"] = route.route_confidence
        state["fallback_used"] = route.fallback_used
        if route.fallback_used:
            state["warnings"].append(f"fallback_used:{route.reason}")
        state["trace"].append(
            self._trace(
                "select_agent",
                route_started,
                {"course": course.value, "intent": intent.value},
                {
                    "agent_id": route.agent_id,
                    "route_status": route.route_status.value,
                    "fallback_used": route.fallback_used,
                },
                status=ExecutionStatus(state["route_status"]),
            )
        )
        self.traces.put(state)
        return PreparedTask(request=legacy, route=route, state=state)

    @staticmethod
    def _course(payload: AgentRequestV2, context: dict[str, Any]) -> CourseCode:
        if IntentRecognitionService.is_cross_domain_topic(payload.message):
            return CourseCode.UNKNOWN
        if payload.course_hint is not None:
            return payload.course_hint
        text = payload.message.casefold().replace(" ", "")
        for course, keywords in (*COURSE_KEYWORD_EXTENSIONS, *COURSE_KEYWORDS):
            if any(keyword.lower() in text for keyword in keywords):
                return course
        if any(
            marker in text
            for marker in ("ω", "欧姆", "电阻", "电压源", "电流源", "基尔霍夫")
        ):
            return CourseCode.CT
        previous = str(
            context.get("active_course", context.get("course_id", ""))
        ).upper()
        if any(
            marker in text
            for marker in (*FOLLOW_UP_MARKERS, *KNOWLEDGE_REQUEST_MARKERS)
        ):
            try:
                return CourseCode(previous)
            except ValueError:
                pass
        return CourseCode.UNKNOWN

    @staticmethod
    def _intent(
        payload: AgentRequestV2, context: dict[str, Any]
    ) -> OrchestrationIntent:
        if payload.intent_hint is not None:
            return payload.intent_hint
        text = payload.message.casefold().replace(" ", "")
        if any(marker in text for marker in FOLLOW_UP_MARKERS):
            return OrchestrationIntent.FOLLOW_UP_QUESTION
        if payload.files and any(
            item.content_type in {"text/csv", "application/vnd.ms-excel"}
            or item.filename.lower().endswith((".csv", ".xlsx", ".xls"))
            for item in payload.files
        ):
            return OrchestrationIntent.DATA_ANALYSIS
        if any(marker in text for marker in ("备课", "教案", "教学设计")):
            return OrchestrationIntent.LESSON_PREP
        if any(marker in text for marker in ("批改", "作业评价", "试卷分析")):
            return OrchestrationIntent.ASSIGNMENT_REVIEW
        if any(marker in text for marker in ("论文润色", "学术写作", "摘要改写")):
            return OrchestrationIntent.ACADEMIC_WRITING
        if any(marker in text for marker in SOLVE_MARKERS) and any(
            marker in text
            for marker in (
                "已知",
                "求",
                "计算",
                "化简",
                "Ω",
                "欧姆",
                "V",
                "A",
                "电路",
                "逻辑函数",
                "卷积",
                "变换",
            )
        ):
            return OrchestrationIntent.SOLVE_PROBLEM
        if any(marker in text for marker in EXPLANATION_MARKERS):
            return OrchestrationIntent.EXPLAIN_CONCEPT
        if any(marker in text for marker in KNOWLEDGE_REQUEST_MARKERS):
            return OrchestrationIntent.GENERAL_QA
        previous_intent = str(context.get("intent", ""))
        if previous_intent and any(marker in text for marker in FOLLOW_UP_MARKERS):
            return OrchestrationIntent.FOLLOW_UP_QUESTION
        return OrchestrationIntent.UNKNOWN

    @staticmethod
    def _legacy_intent(intent: OrchestrationIntent) -> Intent:
        try:
            return Intent(intent.value)
        except ValueError:
            return Intent.UNKNOWN

    @staticmethod
    def _task_family(intent: OrchestrationIntent) -> TaskFamily:
        return {
            OrchestrationIntent.SOLVE_PROBLEM: TaskFamily.ACADEMIC_SOLVING,
            OrchestrationIntent.LESSON_PREP: TaskFamily.LESSON_PREP,
            OrchestrationIntent.ASSIGNMENT_REVIEW: TaskFamily.ASSIGNMENT_REVIEW,
            OrchestrationIntent.ACADEMIC_WRITING: TaskFamily.ACADEMIC_WRITING,
            OrchestrationIntent.DATA_ANALYSIS: TaskFamily.DATA_ANALYSIS,
            OrchestrationIntent.ACADEMIC_SEARCH: TaskFamily.RESEARCH,
            OrchestrationIntent.EXPLAIN_CONCEPT: TaskFamily.KNOWLEDGE_QA,
            OrchestrationIntent.GENERAL_QA: TaskFamily.KNOWLEDGE_QA,
            OrchestrationIntent.SUMMARIZE_KNOWLEDGE: TaskFamily.KNOWLEDGE_QA,
            OrchestrationIntent.FOLLOW_UP_QUESTION: TaskFamily.LEARNING_SUPPORT,
            OrchestrationIntent.LEARNING_ADVICE: TaskFamily.LEARNING_SUPPORT,
        }.get(intent, TaskFamily.FALLBACK)

    @staticmethod
    def _scene(intent: Intent) -> Scene:
        if intent in {Intent.LESSON_PREP, Intent.ASSIGNMENT_REVIEW}:
            return Scene.TEACHING
        if intent in {
            Intent.ACADEMIC_WRITING,
            Intent.DATA_ANALYSIS,
            Intent.ACADEMIC_SEARCH,
        }:
            return Scene.RESEARCH
        return Scene.LEARNING

    @staticmethod
    def _user_role(value: Any) -> UserRole:
        try:
            return UserRole(str(value))
        except ValueError:
            return UserRole.STUDENT

    def _safe_local_fallback(
        self, request: AgentRequest, original: RouteDecision
    ) -> RouteDecision:
        fallback_id = "LEARN_01_LOCAL_RETRIEVAL_V1"
        try:
            definition = self.registry.get(fallback_id)
        except KeyError:
            return original
        if not definition.enabled:
            return original
        return RouteDecision(
            agent_id=fallback_id,
            scene=definition.scene,
            course_id=request.course_id,
            intent=original.intent or request.intent.value,
            route_status=RouteStatus.SELECTED,
            reason="规则无法确定专用 Agent，使用本地检索型安全回退",
            retrieval_required=True,
            provider_required=False,
            route_source="supervisor_local_fallback",
            route_confidence=0.25,
            fallback_used=True,
            original_agent_id=original.agent_id or None,
            reason_codes=["unresolved_route", "local_safe_fallback"],
            local_confidence=0.25,
            intent_recognition=dict(original.intent_recognition),
            capabilities=list(original.capabilities),
            selected_tools=list(original.selected_tools),
            selected_skills=list(original.selected_skills),
            route_mode=original.route_mode,
            complexity=original.complexity,
            needs_subagents=original.needs_subagents,
            parallelizable=original.parallelizable,
            route_revision=original.route_revision + 1,
            route_trace=[
                *original.route_trace,
                {
                    "stage": "supervisor_safe_fallback",
                    "source": "supervisor_local_fallback",
                    "from_agent_id": original.agent_id,
                    "to_agent_id": fallback_id,
                    "intent": original.intent or request.intent.value,
                },
            ],
        )

    def _local_knowledge_primary(
        self, request: AgentRequest, original: RouteDecision
    ) -> RouteDecision:
        # Teaching workflows have their own local internal agents.  Do not
        # replace them with the generic knowledge RAG route when the optional
        # cloud/model path is unavailable; doing so loses lesson-specific
        # structure and makes a valid teaching request look like a concept QA.
        if original.intent in {
            Intent.LESSON_PREP.value,
            Intent.ASSIGNMENT_REVIEW.value,
        } or original.intent_recognition.get("task_family") == "teaching":
            return original
        agent_id = "LEARN_01_LOCAL_RETRIEVAL_V1"
        definition = self.registry.get(agent_id)
        return RouteDecision(
            agent_id=agent_id,
            scene=definition.scene,
            course_id=request.course_id,
            intent=original.intent or request.intent.value,
            route_status=RouteStatus.SELECTED,
            reason="新版对话入口优先使用本地 RAG，并在已配置时由星火生成",
            retrieval_required=True,
            provider_required=False,
            route_source="supervisor_local_rag_primary",
            route_confidence=max(original.route_confidence, 0.9),
            fallback_used=False,
            original_agent_id=original.agent_id or None,
            reason_codes=["local_rag_primary", "spark_generation_when_available"],
            local_confidence=0.9,
            intent_recognition=dict(original.intent_recognition),
            capabilities=list(original.capabilities),
            selected_tools=list(original.selected_tools),
            selected_skills=list(original.selected_skills),
            route_mode=original.route_mode,
            complexity=original.complexity,
            needs_subagents=original.needs_subagents,
            parallelizable=original.parallelizable,
            route_revision=original.route_revision + 1,
            route_trace=[
                *original.route_trace,
                {
                    "stage": "supervisor_local_rag_primary",
                    "source": "supervisor_local_rag_primary",
                    "from_agent_id": original.agent_id,
                    "to_agent_id": agent_id,
                    "intent": original.intent or request.intent.value,
                },
            ],
        )

    @staticmethod
    def _trace(
        name: str,
        started: float,
        input_summary: dict[str, Any],
        output_summary: dict[str, Any],
        *,
        status: ExecutionStatus = ExecutionStatus.SUCCESS,
    ) -> NodeTrace:
        ended = datetime.now(UTC)
        elapsed = max(0, int((perf_counter() - started) * 1000))
        return NodeTrace(
            node_name=name,
            start_time=ended - timedelta(milliseconds=elapsed),
            end_time=ended,
            elapsed_ms=elapsed,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
        )
