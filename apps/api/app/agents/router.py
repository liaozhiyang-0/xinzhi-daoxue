from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.agents.registry import AgentDefinition, AgentRegistry, RoutingRule
from app.contracts.agent import AgentRequest, Intent
from app.contracts.routing import RouteCandidate, RouteDecision, RouteStatus
from app.core.config import Settings
from app.core.errors import AgentInputNotSupportedError, RouteInvalidTargetError
from app.core.internal_workflows import internal_workflow_models_configured
from app.services.request_materials import RequestMaterialExtractor

GENERAL_QUESTION_AGENT_ID = "GENERAL_QUESTION_V1"

BUSINESS_AGENTS = (
    "LEARN_01_KNOWLEDGE_QA_V1",
    "ACADEMIC_PROBLEM_SOLVER",
    "TEACH_01_LESSON_PREP_V1",
    "TEACH_02_ASSIGNMENT_REVIEW_V1",
    "RESEARCH_02_ACADEMIC_WRITING_V1",
    "RESEARCH_03_DATA_ANALYSIS_V1",
)
INTENT_AGENT = {
    "general_qa": "LEARN_01_KNOWLEDGE_QA_V1",
    "explain_concept": "LEARN_01_KNOWLEDGE_QA_V1",
    "follow_up_question": "LEARN_01_KNOWLEDGE_QA_V1",
    "summarize_knowledge": "LEARN_01_KNOWLEDGE_QA_V1",
    "learning_advice": "LEARN_01_KNOWLEDGE_QA_V1",
    "check_simple_step": "LEARN_01_KNOWLEDGE_QA_V1",
    "solve_problem": "ACADEMIC_PROBLEM_SOLVER",
    "lesson_prep": "TEACH_01_LESSON_PREP_V1",
    "assignment_review": "TEACH_02_ASSIGNMENT_REVIEW_V1",
    "academic_writing": "RESEARCH_02_ACADEMIC_WRITING_V1",
    "data_analysis": "RESEARCH_03_DATA_ANALYSIS_V1",
}
AGENT_INTENT = {
    "LEARN_01_KNOWLEDGE_QA_V1": "explain_concept",
    "ACADEMIC_PROBLEM_SOLVER": "solve_problem",
    "TEACH_01_LESSON_PREP_V1": "lesson_prep",
    "TEACH_02_ASSIGNMENT_REVIEW_V1": "assignment_review",
    "RESEARCH_02_ACADEMIC_WRITING_V1": "academic_writing",
    "RESEARCH_03_DATA_ANALYSIS_V1": "data_analysis",
}
AGENT_ROLE = {
    "TEACH_01_LESSON_PREP_V1": "teacher",
    "TEACH_02_ASSIGNMENT_REVIEW_V1": "teacher",
    "RESEARCH_02_ACADEMIC_WRITING_V1": "researcher",
    "RESEARCH_03_DATA_ANALYSIS_V1": "researcher",
}


@dataclass(frozen=True, slots=True)
class _ScoredRoute:
    scores: dict[str, float]
    reasons: dict[str, list[str]]
    task_subtype: str
    secondary_intents: list[str]
    requires_pipeline: bool


class TaskRouter:
    """Fast deterministic routes with bounded, validated cloud fallback hooks."""

    def __init__(
        self, registry: AgentRegistry, settings: Settings | None = None
    ) -> None:
        self.registry = registry
        self.settings = settings or Settings()
        self.material_extractor = RequestMaterialExtractor()

    def route(self, request: AgentRequest) -> RouteDecision:
        material = self.material_extractor.extract(request)
        course_id, course_reasons = self._detect_course(request, material.raw_text)
        input_type = self._input_type(request)
        debug_target = str(request.options.get("debug_agent_id", "")).strip()
        if (
            debug_target
            and request.user_role.value == "admin"
            and self.settings.app_env in {"development", "test"}
        ):
            decision = self._decision_for_target(
                debug_target,
                request,
                course_id=course_id,
                intent=AGENT_INTENT.get(debug_target, request.intent.value),
                input_type=input_type,
                confidence=1.0,
            )
            return decision.model_copy(
                update={
                    "route_source": "admin_debug_override",
                    "reason": f"admin debug selected {debug_target}",
                    "reason_codes": ["admin_debug_override"],
                    "visited_agents": [debug_target],
                }
            )
        if request.intent != Intent.UNKNOWN:
            for rule in self.registry.routing_rules:
                if (
                    course_id in rule.course_ids
                    and request.intent.value in rule.intents
                ):
                    normalized = request.model_copy(update={"course_id": course_id})
                    decision = self._decision_for_rule(rule, normalized)
                    self._ensure_supported(decision.agent_id, input_type)
                    return decision.model_copy(
                        update={
                            "reason_codes": course_reasons
                            + [f"explicit_intent:{request.intent.value}"],
                            "local_confidence": 1.0,
                            "route_confidence": 1.0,
                            "material_extraction": material.model_dump(mode="json"),
                            "inferred_user_role": request.user_role.value,
                            "visited_agents": [decision.agent_id],
                        }
                    )
        scored = self._score(request, material.materials, material.raw_text)
        candidates = self._candidate_models(
            scored, course_id=course_id, input_type=input_type
        )
        best = candidates[0]
        runner_up = candidates[1]
        confidence = best.score
        score_gap = best.score - runner_up.score
        intent = AGENT_INTENT.get(best.agent_id, request.intent.value)
        explicit_intent = request.intent != Intent.UNKNOWN
        general_without_course = (
            input_type == "text"
            and not request.attachments
            and not explicit_intent
            and "course_unspecified_default_context" in course_reasons
            and best.agent_id == "LEARN_01_KNOWLEDGE_QA_V1"
            and confidence <= 0.72
            and any(code.startswith("keywords:") for code in best.reason_codes)
            and all(
                code.startswith("keywords:")
                for code in best.reason_codes
            )
        )
        if general_without_course:
            general_decision = self._general_question_decision(
                request=request,
                course_id=course_id,
                input_type=input_type,
                confidence=confidence,
                candidates=candidates,
                course_reasons=course_reasons,
                material_extraction=material.model_dump(mode="json"),
                reason="未识别到课程领域，使用通用问题回答能力直接作答",
                route_source="local_general_direct",
                extra_reason_codes=["general_question_without_course_context"],
            )
            if general_decision is not None:
                return general_decision
        strong_conflict = runner_up.score >= 0.70 and not scored.requires_pipeline
        direct = explicit_intent or (
            not strong_conflict
            and (confidence >= 0.85 or (confidence >= 0.60 and score_gap >= 0.10))
        )
        if direct:
            decision = self._decision_for_target(
                best.agent_id,
                request,
                course_id=course_id,
                intent=intent,
                input_type=input_type,
                confidence=confidence,
            )
            return decision.model_copy(
                update={
                    "task_subtype": scored.task_subtype,
                    "secondary_intents": scored.secondary_intents,
                    "requires_pipeline": scored.requires_pipeline,
                    "candidate_agents": candidates,
                    "reason_codes": course_reasons + best.reason_codes,
                    "local_confidence": confidence,
                    "availability": self._availability(
                        best.agent_id, course_id, input_type, intent
                    ),
                    "material_extraction": material.model_dump(mode="json"),
                    "inferred_user_role": AGENT_ROLE.get(
                        best.agent_id, request.user_role.value
                    ),
                    "visited_agents": [decision.agent_id],
                }
            )

        cloud_router = self.registry.get("ROUTER_01_FALLBACK_V1")
        if self._cloud_allowed(request) and self.registry.is_runtime_available(
            cloud_router.agent_id, self.settings
        ):
            return RouteDecision(
                agent_id=cloud_router.agent_id,
                scene=cloud_router.scene,
                course_id=course_id,
                intent=intent,
                route_status=RouteStatus.SELECTED,
                reason="local confidence or score gap requires one-pass cloud router",
                retrieval_required=False,
                provider_required=True,
                route_source="cloud_fallback",
                route_confidence=confidence,
                task_subtype=scored.task_subtype,
                secondary_intents=scored.secondary_intents,
                requires_pipeline=scored.requires_pipeline,
                candidate_agents=candidates,
                reason_codes=course_reasons + ["cloud_router_required"],
                local_confidence=confidence,
                cloud_router_invoked=True,
                availability=self._availability(
                    cloud_router.agent_id, course_id, input_type, intent
                ),
                material_extraction=material.model_dump(mode="json"),
                inferred_user_role=request.user_role.value,
                visited_agents=[cloud_router.agent_id],
            )
        cloud_reason = (
            "cloud_router_unavailable"
            if self._cloud_allowed(request)
            else "cloud_router_not_authorized"
        )
        general_decision = self._general_question_decision(
            request=request,
            course_id=course_id,
            input_type=input_type,
            confidence=confidence,
            candidates=candidates,
            course_reasons=course_reasons,
            material_extraction=material.model_dump(mode="json"),
            reason="专用能力路由置信度不足，使用通用问题回答能力",
            route_source="local_general_fallback",
            extra_reason_codes=[cloud_reason, "general_question_fallback"],
        )
        if general_decision is not None:
            return general_decision
        return RouteDecision(
            agent_id="UNRESOLVED",
            scene=request.scene.value,
            course_id=course_id,
            intent=intent,
            route_status=RouteStatus.UNRESOLVED,
            reason=(
                "本地路由置信度不足；星辰调度未获本次请求授权，请补充课程或任务类型"
                if not self._cloud_allowed(request)
                else "本地路由置信度不足，且云端调度工作流未配置；请求保持未决状态"
            ),
            retrieval_required=False,
            provider_required=False,
            route_source="local_degraded",
            route_confidence=confidence,
            task_subtype=scored.task_subtype,
            secondary_intents=scored.secondary_intents,
            requires_pipeline=scored.requires_pipeline,
            candidate_agents=candidates,
            reason_codes=course_reasons + [cloud_reason],
            local_confidence=confidence,
            availability=self._availability(
                cloud_router.agent_id, course_id, input_type, intent
            ),
            material_extraction=material.model_dump(mode="json"),
            inferred_user_role=request.user_role.value,
        )

    def _general_question_decision(
        self,
        *,
        request: AgentRequest,
        course_id: str,
        input_type: str,
        confidence: float,
        candidates: list[RouteCandidate],
        course_reasons: list[str],
        material_extraction: dict[str, Any],
        reason: str,
        route_source: str,
        extra_reason_codes: list[str],
    ) -> RouteDecision | None:
        general = self.registry.get(GENERAL_QUESTION_AGENT_ID)
        if (
            input_type != "text"
            or not general.enabled
            or not self.registry.is_runtime_available(general.agent_id, self.settings)
        ):
            return None
        route_confidence = max(confidence, 0.35)
        decision = self._decision_for_target(
            general.agent_id,
            request,
            course_id=course_id,
            intent=Intent.GENERAL_QA.value,
            input_type=input_type,
            confidence=route_confidence,
        )
        return decision.model_copy(
            update={
                "reason": reason,
                "route_source": route_source,
                "route_confidence": route_confidence,
                "candidate_agents": candidates,
                "reason_codes": course_reasons + extra_reason_codes,
                "local_confidence": confidence,
                "availability": self._availability(
                    general.agent_id,
                    course_id,
                    input_type,
                    Intent.GENERAL_QA.value,
                ),
                "material_extraction": material_extraction,
                "inferred_user_role": request.user_role.value,
                "visited_agents": [general.agent_id],
            }
        )

    def _candidate_models(
        self, scored: _ScoredRoute, *, course_id: str, input_type: str
    ) -> list[RouteCandidate]:
        result = []
        for agent_id in BUSINESS_AGENTS:
            intent = AGENT_INTENT[agent_id]
            availability = self._availability(agent_id, course_id, input_type, intent)
            result.append(
                RouteCandidate(
                    agent_id=agent_id,
                    score=max(0.0, min(1.0, scored.scores.get(agent_id, 0.0))),
                    available=all(availability.values()),
                    reason_codes=scored.reasons.get(agent_id, []),
                )
            )
        return sorted(result, key=lambda item: (-item.score, item.agent_id))

    def _availability(
        self, agent_id: str, course_id: str, input_type: str, intent: str
    ) -> dict[str, bool]:
        definition = self.registry.get(agent_id)
        internal_available = internal_workflow_models_configured(
            self.settings, agent_id
        )
        return {
            "enabled": definition.enabled,
            "published": definition.publication_status in {"published", "local"},
            "flow_configured": self.registry.is_configured(agent_id, self.settings),
            "provider_available": (
                internal_available
                or definition.provider == "local"
                or (
                    self.settings.xingchen_enabled
                    and bool(self.settings.xingchen_api_key.get_secret_value())
                    and bool(self.settings.xingchen_api_secret.get_secret_value())
                )
            ),
            "input_mode_supported": input_type in definition.supports,
            "course_supported": course_id in definition.course_ids,
            "intent_supported": (
                not definition.capabilities.intents
                or intent in definition.capabilities.intents
            ),
        }

    @staticmethod
    def _detect_course(request: AgentRequest, text: str) -> tuple[str, list[str]]:
        explicit = request.course_id.upper().strip()
        if explicit in {
            "CT",
            "AE",
            "DE",
            "SS",
            "DSP",
            "COMM",
            "RF",
            "EM",
            "INFO",
            "EMBEDDED",
            "IC",
        }:
            return explicit, ["explicit_course_hint"]
        scores = {
            "CT": sum(
                token in text
                for token in (
                    "电路理论",
                    "电阻",
                    "电容",
                    "电感",
                    "节点电压",
                    "网孔",
                    "戴维宁",
                    "一阶电路",
                    "受控源",
                    "相量",
                    "KCL",
                    "KVL",
                )
            ),
            "AE": sum(
                token in text
                for token in (
                    "模拟电子",
                    "模电",
                    "负反馈",
                    "放大电路",
                    "运放",
                    "晶体管",
                    "MOS管",
                    "静态工作点",
                    "共射",
                )
            ),
            "DE": sum(
                token in text
                for token in (
                    "数字电子",
                    "数电",
                    "触发器",
                    "锁存器",
                    "卡诺图",
                    "逻辑门",
                    "计数器",
                    "寄存器",
                    "时序逻辑",
                    "组合逻辑",
                )
            ),
            "SS": sum(
                token in text
                for token in ("信号与系统", "卷积", "拉普拉斯", "傅里叶变换", "LTI")
            ),
            "DSP": sum(
                token in text for token in ("数字信号处理", "DFT", "FFT", "数字滤波器")
            ),
            "COMM": sum(
                token in text for token in ("通信原理", "调制", "解调", "信道")
            ),
            "RF": sum(token in text for token in ("高频电子", "混频", "谐振放大")),
            "EM": sum(token in text for token in ("电磁场", "电磁波", "麦克斯韦")),
            "INFO": sum(token in text for token in ("信息论", "信道容量", "信源编码")),
            "EMBEDDED": sum(
                token in text for token in ("嵌入式", "单片机", "微控制器")
            ),
            "IC": sum(token in text for token in ("集成电路", "芯片设计", "版图")),
        }
        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        if scores[best] > 0 and list(scores.values()).count(scores[best]) == 1:
            return best, [f"detected_course:{best}"]
        previous = str(request.options.get("previous_course", "")).upper()
        if previous in scores:
            return previous, ["inherited_previous_course"]
        return "CT", ["course_unspecified_default_context"]

    def _score(
        self, request: AgentRequest, materials: dict[str, Any], text: str
    ) -> _ScoredRoute:
        scores: dict[str, float] = defaultdict(float)
        reasons: dict[str, list[str]] = defaultdict(list)
        explicit = INTENT_AGENT.get(request.intent.value)
        if explicit:
            scores[explicit] = 1.0
            reasons[explicit].append(f"explicit_intent:{request.intent.value}")
            return _ScoredRoute(dict(scores), dict(reasons), "", [], False)

        def add(agent: str, amount: float, code: str) -> None:
            scores[agent] += amount
            reasons[agent].append(code)

        keyword_groups: tuple[tuple[str, tuple[str, ...], float], ...] = (
            (
                "TEACH_01_LESSON_PREP_V1",
                (
                    "教案",
                    "备课",
                    "教学设计",
                    "教学目标",
                    "教学流程",
                    "教学方案",
                    "课堂活动",
                    "课时",
                    "形成性评价",
                ),
                0.72,
            ),
            (
                "TEACH_02_ASSIGNMENT_REVIEW_V1",
                ("批改", "评分标准", "rubric", "学生答案", "给分", "教师反馈", "满分"),
                0.72,
            ),
            (
                "RESEARCH_02_ACADEMIC_WRITING_V1",
                (
                    "论文",
                    "摘要",
                    "提纲",
                    "引言",
                    "方法部分",
                    "结果部分",
                    "结论",
                    "润色",
                    "改写",
                    "审稿",
                    "引用",
                    "无依据声明",
                    "学术表达",
                    "Results",
                ),
                0.72,
            ),
            (
                "RESEARCH_03_DATA_ANALYSIS_V1",
                (
                    "数据",
                    "样本量",
                    "缺失值",
                    "AUC",
                    "统计检验",
                    "回归",
                    "显著性",
                    "置信区间",
                    "分析方法",
                    "分类任务",
                    "连续结局",
                    "指标",
                    "可复现",
                ),
                0.72,
            ),
            (
                "ACADEMIC_PROBLEM_SOLVER",
                (
                    "完整解答",
                    "列方程",
                    "求数值",
                    "计算",
                    "求响应",
                    "相量响应",
                    "正弦稳态",
                    "节点电压法",
                    "网孔电流法",
                    "相量法",
                    "求回路电流",
                ),
                0.72,
            ),
            (
                "LEARN_01_KNOWLEDGE_QA_V1",
                (
                    "为什么",
                    "是什么",
                    "有什么区别",
                    "适用条件",
                    "作用",
                    "总结",
                    "怎么理解",
                    "如何复习",
                    "学习建议",
                ),
                0.66,
            ),
        )
        for agent, keywords, ceiling in keyword_groups:
            hits = [token for token in keywords if token.casefold() in text.casefold()]
            if hits:
                add(
                    agent,
                    min(ceiling, 0.60 + 0.12 * len(hits)),
                    f"keywords:{','.join(hits[:4])}",
                )

        statistical_context = any(
            token in text
            for token in (
                "数据",
                "样本",
                "统计",
                "回归",
                "AUC",
                "置信区间",
                "缺失值",
                "连续结局",
                "分析计划",
                "分析方法",
                "数据质量",
            )
        )
        if "变量" in text and statistical_context:
            add(
                "RESEARCH_03_DATA_ANALYSIS_V1",
                0.72,
                "contextual_keyword:statistical_variable",
            )

        dynamic_circuit_problem = (
            any(
                token in text
                for token in (
                    "电路",
                    "电容",
                    "电感",
                    "受控源",
                    "节点电压",
                    "KCL",
                    "KVL",
                )
            )
            and any(
                token in text
                for token in (
                    "换路初始条件",
                    "状态方程",
                    "微分方程",
                    "完整响应",
                    "自由响应",
                    "强迫响应",
                    "自然频率",
                    "阻尼类型",
                    "零点",
                    "能量平衡",
                )
            )
        )
        if dynamic_circuit_problem:
            add(
                "ACADEMIC_PROBLEM_SOLVER",
                0.92,
                "domain_contract:dynamic_circuit_problem",
            )
            if not statistical_context:
                scores["RESEARCH_03_DATA_ANALYSIS_V1"] = 0.0
                reasons["RESEARCH_03_DATA_ANALYSIS_V1"].append(
                    "negative_rule:state_variable_is_not_statistical_data"
                )

        if request.attachments and any(
            item.content_type.startswith("image/") for item in request.attachments
        ):
            add("ACADEMIC_PROBLEM_SOLVER", 0.88, "multimodal_solver_contract")
        if materials.get("student_answer") and materials.get("rubric"):
            add("TEACH_02_ASSIGNMENT_REVIEW_V1", 0.92, "student_answer_and_rubric")
        elif materials.get("student_answer"):
            add("TEACH_02_ASSIGNMENT_REVIEW_V1", 0.68, "student_answer_present")
        if any(
            materials.get(field)
            for field in ("topic", "class_duration", "student_level", "lesson_count")
        ) and any(token in text for token in ("教案", "备课", "课堂", "教学", "课程")):
            add("TEACH_01_LESSON_PREP_V1", 0.28, "lesson_fields_present")
        if materials.get("source_text") or request.canonical_input.get("uploaded_text"):
            add("RESEARCH_02_ACADEMIC_WRITING_V1", 0.30, "source_text_present")
        if any(
            materials.get(field) for field in ("data_description", "provided_results")
        ):
            add("RESEARCH_03_DATA_ANALYSIS_V1", 0.30, "data_context_present")

        if any(
            token in text for token in ("教案", "备课", "教学流程", "教学方案", "课程")
        ) and any(token in text for token in ("设计", "备课", "教案", "流程")):
            add("TEACH_01_LESSON_PREP_V1", 0.60, "teaching_task_semantics")
            scores["ACADEMIC_PROBLEM_SOLVER"] = max(
                0.0, scores.get("ACADEMIC_PROBLEM_SOLVER", 0.0) - 0.45
            )
            reasons["ACADEMIC_PROBLEM_SOLVER"].append("negative_rule:lesson_design")
        if any(
            token in text for token in ("如何复习", "怎么理解", "总结", "学习建议")
        ) and not any(
            token in text for token in ("完整解答", "列方程", "求数值", "计算")
        ):
            scores["ACADEMIC_PROBLEM_SOLVER"] = max(
                0.0, scores.get("ACADEMIC_PROBLEM_SOLVER", 0.0) - 0.45
            )
            reasons["ACADEMIC_PROBLEM_SOLVER"].append("negative_rule:learning_request")

        previous_agent = str(request.options.get("previous_agent", ""))
        follow_up = any(
            token in text
            for token in ("刚才", "上面", "之前", "这个", "压缩成", "改成")
        )
        writing_switch = any(
            token in text
            for token in ("写成结果段", "写成论文摘要", "写一段Results", "改写成摘要")
        )
        if writing_switch:
            add(
                "RESEARCH_02_ACADEMIC_WRITING_V1",
                0.92,
                "follow_up_task_switch_to_writing",
            )
        elif follow_up and previous_agent in BUSINESS_AGENTS:
            add(previous_agent, 0.90, "session_continuity")

        if not scores and request.intent == Intent.UNKNOWN:
            add("LEARN_01_KNOWLEDGE_QA_V1", 0.30, "generic_question_candidate")
        scores = {key: min(1.0, value) for key, value in scores.items()}
        analysis_score = scores.get("RESEARCH_03_DATA_ANALYSIS_V1", 0.0)
        writing_score = scores.get("RESEARCH_02_ACADEMIC_WRITING_V1", 0.0)
        multi = (
            analysis_score >= 0.55
            and writing_score >= 0.55
            and any(token in text for token in ("再", "然后", "后写", "并写", "之后"))
        )
        if multi:
            scores["RESEARCH_03_DATA_ANALYSIS_V1"] = max(0.90, analysis_score)
            scores["RESEARCH_02_ACADEMIC_WRITING_V1"] = max(0.75, writing_score)
            reasons["RESEARCH_03_DATA_ANALYSIS_V1"].append(
                "pipeline_primary:data_analysis_then_writing"
            )
        subtype = self._task_subtype(text)
        return _ScoredRoute(
            scores,
            dict(reasons),
            subtype,
            ["academic_writing"] if multi else [],
            multi,
        )

    @staticmethod
    def _task_subtype(text: str) -> str:
        pairs = (
            ("write_outline", ("提纲",)),
            ("rewrite_paragraph", ("润色", "改写")),
            ("write_abstract", ("摘要",)),
            ("review_response", ("审稿回复",)),
            ("claim_strength_check", ("结论过度", "论证强度")),
            ("data_quality_check", ("数据质量", "缺失值")),
            ("result_interpretation", ("解释结果", "AUC结果", "结果说明")),
            ("analysis_plan", ("分析计划", "分析流程", "统计方法")),
        )
        for subtype, keywords in pairs:
            if any(keyword in text for keyword in keywords):
                return subtype
        return ""

    @staticmethod
    def _input_type(request: AgentRequest) -> str:
        has_text = any(
            isinstance(request.canonical_input.get(key), str)
            and bool(request.canonical_input[key].strip())
            for key in ("text", "question", "problem", "query", "prompt")
        )
        images = [
            item
            for item in request.attachments
            if item.content_type.startswith("image/")
        ]
        if len(images) > 1:
            return "text_and_multi_image" if has_text else "multi_image"
        if has_text and images:
            return "text_and_single_image"
        if images:
            return "single_image"
        if has_text:
            return "text"
        if request.attachments:
            raise AgentInputNotSupportedError("非图片附件需要同时提供文字说明")
        raise AgentInputNotSupportedError("任务输入不能为空")

    def _decision_for_target(
        self,
        target_agent_id: str,
        request: AgentRequest,
        *,
        course_id: str,
        intent: str,
        input_type: str,
        confidence: float,
    ) -> RouteDecision:
        primary = self.registry.get(target_agent_id)
        selected = primary
        fallback_used = False
        source = "local_fast"
        cloud_allowed = self._cloud_allowed(request)
        internal_available = internal_workflow_models_configured(
            self.settings, primary.agent_id
        )
        local_only = (
            primary.provider == "xingchen"
            and not cloud_allowed
            and not internal_available
        )
        if local_only or not self.registry.is_runtime_available(
            primary.agent_id, self.settings
        ):
            fallback = self.registry.resolve_fallback(primary.agent_id)
            if fallback is not None and self.registry.is_runtime_available(
                fallback.agent_id, self.settings
            ):
                selected = fallback
                fallback_used = True
                source = "local_degraded"
            elif local_only:
                source = "local_only"
        self._ensure_supported(selected.agent_id, input_type)
        return RouteDecision(
            agent_id=selected.agent_id,
            scene=primary.scene,
            course_id=course_id,
            intent=intent,
            route_status=RouteStatus.SELECTED,
            reason=(
                f"fallback from {primary.agent_id} to {selected.agent_id}"
                if fallback_used
                else f"local deterministic routing selected {primary.agent_id}"
            ),
            retrieval_required=selected.retrieval_policy.enabled,
            provider_required=(
                selected.provider == "xingchen"
                and cloud_allowed
                and not internal_workflow_models_configured(
                    self.settings, selected.agent_id
                )
            ),
            route_source=source,
            route_confidence=confidence,
            fallback_used=fallback_used,
            original_agent_id=primary.agent_id if fallback_used else None,
            fallback_instruction=(
                primary.fallback.instruction_prefix if fallback_used else ""
            ),
        )

    def _ensure_supported(self, agent_id: str, input_type: str) -> None:
        if input_type not in self.registry.get(agent_id).supports:
            raise AgentInputNotSupportedError(
                "目标 Agent 不支持当前输入类型",
                details={"agent_id": agent_id, "input_type": input_type},
            )

    def _decision_for_rule(
        self, rule: RoutingRule, request: AgentRequest
    ) -> RouteDecision:
        primary = self.registry.get(rule.agent_id)
        selected = primary
        fallback_used = False
        source = "local_fast"
        cloud_allowed = self._cloud_allowed(request)
        internal_available = internal_workflow_models_configured(
            self.settings, primary.agent_id
        )
        local_only = (
            primary.provider == "xingchen"
            and not cloud_allowed
            and not internal_available
        )

        if (
            local_only
            or (
                not primary.route_when_unconfigured
                and not self.registry.is_runtime_available(
                    primary.agent_id, self.settings
                )
            )
        ):
            fallback = self.registry.resolve_fallback(primary.agent_id)
            if fallback and (
                fallback.route_when_unconfigured
                or self.registry.is_runtime_available(fallback.agent_id, self.settings)
            ):
                selected = fallback
                fallback_used = True
                source = "local_degraded"
            elif not local_only:
                return RouteDecision(
                    agent_id="UNRESOLVED",
                    scene=rule.scene,
                    course_id=request.course_id.upper(),
                    intent=request.intent.value,
                    route_status=RouteStatus.UNRESOLVED,
                    reason=f"configured agent unavailable: {primary.agent_id}",
                    retrieval_required=False,
                    provider_required=False,
                    route_source="local_degraded",
                    route_confidence=0.0,
                    original_agent_id=primary.agent_id,
                )
            else:
                source = "local_only"

        return RouteDecision(
            agent_id=selected.agent_id,
            scene=rule.scene,
            course_id=request.course_id.upper(),
            intent=request.intent.value,
            route_status=RouteStatus.SELECTED,
            reason=(
                f"fallback from {primary.agent_id} to {selected.agent_id}"
                if fallback_used
                else (
                    "matched configured route "
                    f"course_id={request.course_id.upper()}, "
                    f"intent={request.intent.value}"
                )
            ),
            retrieval_required=rule.retrieval_required,
            provider_required=(
                selected.provider == "xingchen"
                and cloud_allowed
                and not internal_workflow_models_configured(
                    self.settings, selected.agent_id
                )
            ),
            route_source=source,
            route_confidence=0.9 if fallback_used else 0.98,
            fallback_used=fallback_used,
            original_agent_id=primary.agent_id if fallback_used else None,
            fallback_instruction=(
                primary.fallback.instruction_prefix if fallback_used else ""
            ),
        )

    def _cloud_allowed(self, request: AgentRequest) -> bool:
        value = request.options.get(
            "allow_cloud", self.settings.xingchen_workflows_default_enabled
        )
        return value is True

    def validate_cloud_target(
        self,
        target_agent_id: str,
        request: AgentRequest,
        *,
        source_agent_id: str = "ROUTER_01_FALLBACK_V1",
    ) -> AgentDefinition:
        if target_agent_id == source_agent_id:
            raise RouteInvalidTargetError("云端调度不得路由回自身")
        try:
            target = self.registry.get(target_agent_id)
        except KeyError as exc:
            raise RouteInvalidTargetError("云端调度返回未注册 Agent") from exc
        if not target.enabled:
            raise RouteInvalidTargetError("云端调度返回未启用 Agent")
        if target.mode == "routing_only":
            raise RouteInvalidTargetError("云端调度目标不得再次进入调度 Agent")
        if request.course_id.upper() not in target.course_ids:
            raise RouteInvalidTargetError("云端调度目标不支持当前课程")
        has_text = any(
            isinstance(value, str) and bool(value.strip())
            for value in request.canonical_input.values()
        )
        if len(request.attachments) > 1:
            raise RouteInvalidTargetError("云端调度目标不支持多附件输入")
        input_type = (
            "text_and_single_image"
            if has_text and request.attachments
            else "single_image"
            if request.attachments
            else "text"
            if has_text
            else "empty"
        )
        if input_type not in target.supports:
            raise RouteInvalidTargetError("云端调度目标不支持当前输入类型")
        if target.provider == "xingchen" and not self.registry.is_runtime_available(
            target.agent_id, self.settings
        ):
            raise RouteInvalidTargetError("云端调度目标当前不可运行")
        return target

    def route_cloud_response(self, answer: str, request: AgentRequest) -> RouteDecision:
        try:
            payload = json.loads(answer)
            target_id = payload["target_agent_id"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RouteInvalidTargetError(
                "云端调度响应必须包含 target_agent_id JSON"
            ) from exc
        if not isinstance(target_id, str):
            raise RouteInvalidTargetError("云端调度 target_agent_id 必须是字符串")
        target = self.validate_cloud_target(target_id, request)
        confidence = payload.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            confidence = 0.5
        return RouteDecision(
            agent_id=target.agent_id,
            scene=target.scene,
            course_id=request.course_id.upper(),
            intent=request.intent.value,
            route_status=RouteStatus.SELECTED,
            reason="validated one-pass cloud dispatch target",
            retrieval_required=target.mode != "routing_only",
            provider_required=target.provider == "xingchen",
            route_source="cloud_fallback",
            route_confidence=max(0.0, min(1.0, float(confidence))),
            fallback_used=True,
            original_agent_id="ROUTER_01_FALLBACK_V1",
        )
