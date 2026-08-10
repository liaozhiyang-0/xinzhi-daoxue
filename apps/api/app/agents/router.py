from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.agents.registry import AgentDefinition, AgentRegistry, RoutingRule
from app.contracts.agent import AgentRequest, Intent
from app.contracts.intent import IntentRecognition
from app.contracts.routing import RouteCandidate, RouteDecision, RouteStatus
from app.core.config import Settings
from app.core.errors import AgentInputNotSupportedError, RouteInvalidTargetError
from app.core.internal_workflows import internal_workflow_models_configured
from app.services.external_research_answer import (
    is_academic_search_follow_up,
    is_academic_search_request,
)
from app.services.intent_recognition import IntentRecognitionService
from app.services.request_materials import RequestMaterialExtractor

GENERAL_QUESTION_AGENT_ID = "GENERAL_QUESTION_V1"

BUSINESS_AGENTS = (
    "LEARN_01_KNOWLEDGE_QA_V1",
    "ACADEMIC_PROBLEM_SOLVER",
    "TEACH_01_LESSON_PREP_V1",
    "TEACH_02_ASSIGNMENT_REVIEW_V1",
    "RESEARCH_01_ACADEMIC_SEARCH_V1",
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
    "RESEARCH_01_ACADEMIC_SEARCH_V1": "academic_search",
    "RESEARCH_02_ACADEMIC_WRITING_V1": "academic_writing",
    "RESEARCH_03_DATA_ANALYSIS_V1": "data_analysis",
}
AGENT_ROLE = {
    "TEACH_01_LESSON_PREP_V1": "teacher",
    "TEACH_02_ASSIGNMENT_REVIEW_V1": "teacher",
    "RESEARCH_01_ACADEMIC_SEARCH_V1": "researcher",
    "RESEARCH_02_ACADEMIC_WRITING_V1": "researcher",
    "RESEARCH_03_DATA_ANALYSIS_V1": "researcher",
}

OVERALL_ROUTE_CATALOG = (
    {
        "agent_id": GENERAL_QUESTION_AGENT_ID,
        "label": "通用问答",
        "description": "无法可靠归类、跨领域或需要先澄清的问题。",
        "selection_hint": "不确定时选择此路径。",
    },
    {
        "agent_id": "LEARN_01_KNOWLEDGE_QA_V1",
        "label": "课程知识问答",
        "description": "解释电子信息课程概念、定理、方法和知识点。",
        "selection_hint": "课程概念解释、知识总结和学习建议。",
    },
    {
        "agent_id": "ACADEMIC_PROBLEM_SOLVER",
        "label": "学术问题求解",
        "description": "计算、推导和分析电路或其他课程题目。",
        "selection_hint": "含数值、公式、图像或明确求解目标的问题。",
    },
    {
        "agent_id": "TEACH_01_LESSON_PREP_V1",
        "label": "教案设计",
        "description": "设计课程教案、课堂流程和形成性评价。",
        "selection_hint": "用户要求备课、授课方案或教学活动。",
    },
    {
        "agent_id": "TEACH_02_ASSIGNMENT_REVIEW_V1",
        "label": "作业初审",
        "description": "检查学生作业的正确部分、错误、风险和反馈。",
        "selection_hint": "用户要求批改、初审或检查学生答案。",
    },
    {
        "agent_id": "RESEARCH_01_ACADEMIC_SEARCH_V1",
        "label": "科研前沿检索与证据简报",
        "description": "从论文、报道和会议来源整理带证据边界的科研前沿简报。",
        "selection_hint": "研究进展、趋势、最新论文、行业报道、会议或技术对比。",
    },
    {
        "agent_id": "RESEARCH_02_ACADEMIC_WRITING_V1",
        "label": "学术写作",
        "description": "改写、润色、摘要化或规范化用户已有学术文本。",
        "selection_hint": "修改表达，不负责替用户查找论文。",
    },
    {
        "agent_id": "RESEARCH_03_DATA_ANALYSIS_V1",
        "label": "数据分析",
        "description": "根据用户提供的数据或目标制定、解释分析方案。",
        "selection_hint": "统计、实验数据、指标分析和可复现计划。",
    },
)


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
        self.intent_recognizer = IntentRecognitionService()

    def route(self, request: AgentRequest) -> RouteDecision:
        recognition = self.intent_recognizer.recognize(request)
        # The first rollout is additive: legacy rules remain authoritative for
        # route compatibility, while structured recognition is available to
        # planning and later model refinement.
        decision = self._route_legacy(request, recognition)
        return self._attach_intent_context(decision, recognition)

    def _route_legacy(
        self, request: AgentRequest, recognition: IntentRecognition
    ) -> RouteDecision:
        material = self.material_extractor.extract(request)
        course_id, course_reasons = self._detect_course(request, material.raw_text)
        input_type = self._input_type(request)
        scenario_agent_id = (
            str(request.options.get("scenario_agent_id", "")).strip()
            if request.options.get("_scenario_catalog_bound") is True
            else ""
        )
        if scenario_agent_id:
            decision = self._decision_for_target(
                scenario_agent_id,
                request,
                course_id=course_id,
                intent=request.intent.value,
                input_type=input_type,
                confidence=1.0,
            )
            return decision.model_copy(
                update={
                    "route_source": "scenario_catalog",
                    "reason": (
                        f"scenario catalog selected {scenario_agent_id}"
                        if not decision.fallback_used
                        else decision.reason
                    ),
                    "reason_codes": course_reasons + ["scenario_catalog_bound"],
                    "local_confidence": 1.0,
                    "route_confidence": 1.0,
                    "material_extraction": material.model_dump(mode="json"),
                    "inferred_user_role": request.user_role.value,
                    "visited_agents": [decision.agent_id],
                }
            )
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
        scored = self._score(request, material.materials, material.raw_text)
        previous_agent = str(request.options.get("previous_agent", ""))
        previous_answer_summary = str(
            request.options.get("previous_answer_summary", "")
        )
        is_search_follow_up = is_academic_search_follow_up(
            material.raw_text,
            previous_agent=previous_agent,
            previous_answer_summary=previous_answer_summary,
            previous_query=str(request.options.get("previous_external_query", "")),
        )
        research_alias_allowed = recognition.intent not in {
            Intent.ACADEMIC_WRITING.value,
            Intent.DATA_ANALYSIS.value,
        }
        if (
            recognition.intent == Intent.ACADEMIC_SEARCH.value
            or (
                research_alias_allowed
                and (
                    is_academic_search_request(material.raw_text)
                    or is_search_follow_up
                )
            )
        ):
            decision = self._decision_for_target(
                "RESEARCH_01_ACADEMIC_SEARCH_V1",
                request,
                course_id=course_id,
                intent=AGENT_INTENT["RESEARCH_01_ACADEMIC_SEARCH_V1"],
                input_type=input_type,
                confidence=1.0,
            )
            return decision.model_copy(
                update={
                    "task_subtype": "academic_search",
                    "reason": "识别为论文检索请求，进入外部学术检索能力",
                    "reason_codes": course_reasons + ["academic_search_request"],
                    "local_confidence": 1.0,
                    "route_confidence": 1.0,
                    "material_extraction": material.model_dump(mode="json"),
                    "inferred_user_role": request.user_role.value,
                    "visited_agents": ["RESEARCH_01_ACADEMIC_SEARCH_V1"],
                }
            )
        recognized_workflow_intent = recognition.intent in {
            Intent.ACADEMIC_WRITING.value,
            Intent.DATA_ANALYSIS.value,
        }
        if (
            recognized_workflow_intent
            and recognition.confidence >= 0.80
            and request.intent in {Intent.UNKNOWN, Intent.GENERAL_QA}
        ):
            target_agent_id = INTENT_AGENT[recognition.intent]
            decision = self._decision_for_target(
                target_agent_id,
                request,
                course_id=course_id,
                intent=recognition.intent,
                input_type=input_type,
                confidence=recognition.confidence,
            )
            return decision.model_copy(
                update={
                    "reason": "本地意图识别已确认研究工作流，直接进入对应 Agent",
                    "route_source": "local_intent_recognition",
                    "reason_codes": course_reasons
                    + [f"recognized_intent:{recognition.intent}"],
                    "local_confidence": recognition.confidence,
                    "route_confidence": recognition.confidence,
                    "secondary_intents": scored.secondary_intents,
                    "requires_pipeline": scored.requires_pipeline,
                    "material_extraction": material.model_dump(mode="json"),
                    "inferred_user_role": AGENT_ROLE.get(
                        target_agent_id, request.user_role.value
                    ),
                    "visited_agents": [target_agent_id],
                }
            )
        if (
            "topic_outside_course" in course_reasons
            and request.intent in {Intent.UNKNOWN, Intent.GENERAL_QA}
        ):
            general_decision = self._general_question_decision(
                request=request,
                course_id="UNKNOWN",
                input_type=input_type,
                confidence=0.86,
                candidates=[],
                course_reasons=course_reasons,
                material_extraction=material.model_dump(mode="json"),
                reason="识别到非课程领域问题，切换通用回答能力并停止课程资料检索",
                route_source="local_topic_boundary",
                extra_reason_codes=["topic_outside_course"],
            )
            if general_decision is not None:
                return general_decision
        general_qa_problem_override = (
            request.intent == Intent.GENERAL_QA
            and "domain_contract:academic_problem_language"
            in scored.reasons.get("ACADEMIC_PROBLEM_SOLVER", [])
        )
        if request.intent != Intent.UNKNOWN and not general_qa_problem_override:
            for rule in self.registry.routing_rules:
                if (
                    course_id in rule.course_ids
                    and request.intent.value in rule.intents
                ):
                    normalized = request.model_copy(update={"course_id": course_id})
                    decision = self._decision_for_rule(rule, normalized)
                    if decision.route_status != RouteStatus.UNRESOLVED:
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
            and all(code.startswith("keywords:") for code in best.reason_codes)
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
        research_frontier_direct = (
            best.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1" and confidence >= 0.80
        )
        direct = explicit_intent or (
            research_frontier_direct
            or (
                not strong_conflict
                and (confidence >= 0.85 or (confidence >= 0.60 and score_gap >= 0.10))
            )
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

    @staticmethod
    def _attach_intent_context(
        decision: RouteDecision, recognition: Any
    ) -> RouteDecision:
        reason_codes = list(
            dict.fromkeys(
                [
                    *recognition.reason_codes,
                    "structured_intent",
                    *decision.reason_codes,
                ]
            )
        )
        # The selected business route remains authoritative for legacy
        # solver/teaching semantics.  The one former alias that caused a real
        # cross-layer conflict was research being persisted as ``general_qa``.
        # Normalize that case while keeping a solver route from being changed
        # to ``general_qa`` by a conservative recognizer.
        normalized_intent = decision.intent
        if (
            recognition.intent == Intent.ACADEMIC_SEARCH.value
            and decision.agent_id
            in {"RESEARCH_01_ACADEMIC_SEARCH_V1", GENERAL_QUESTION_AGENT_ID}
        ):
            normalized_intent = Intent.ACADEMIC_SEARCH.value
        recognition = IntentRecognitionService.align_to_intent(
            recognition, normalized_intent
        )
        payload = recognition.model_dump(mode="json")
        reason_codes = list(
            dict.fromkeys(
                [
                    *recognition.reason_codes,
                    "structured_intent",
                    *decision.reason_codes,
                ]
            )
        )
        return decision.model_copy(
            update={
                "intent": normalized_intent,
                "intent_recognition": payload,
                "capabilities": list(recognition.capabilities),
                "selected_tools": list(recognition.selected_tools),
                "selected_skills": list(recognition.selected_skills),
                "route_mode": recognition.route_mode,
                "complexity": recognition.complexity,
                "needs_subagents": recognition.needs_subagents,
                "parallelizable": recognition.parallelizable,
                "reason_codes": reason_codes,
                "route_trace": decision.route_trace
                or [
                    {
                        "stage": "deterministic",
                        "source": decision.route_source,
                        "agent_id": decision.agent_id,
                        "intent": normalized_intent,
                        "confidence": decision.route_confidence,
                    }
                ],
            }
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

    def overall_route_candidates(
        self, request: AgentRequest, current: RouteDecision | None = None
    ) -> list[dict[str, Any]]:
        """Return a compact, model-readable summary of all executable paths."""

        material = self.material_extractor.extract(request)
        course_id, _ = self._detect_course(request, material.raw_text)
        input_type = self._input_type(request)
        current_scores = {
            item.agent_id: item.score
            for item in (current.candidate_agents if current else [])
        }
        result: list[dict[str, Any]] = []
        for item in OVERALL_ROUTE_CATALOG:
            agent_id = str(item["agent_id"])
            intent = (
                Intent.GENERAL_QA.value
                if agent_id == GENERAL_QUESTION_AGENT_ID
                else AGENT_INTENT[agent_id]
            )
            availability = self._availability(agent_id, course_id, input_type, intent)
            result.append(
                {
                    **item,
                    "available": all(availability.values()),
                    "availability": availability,
                    "local_score": current_scores.get(agent_id, 0.0),
                }
            )
        return result

    def apply_overall_route(
        self,
        request: AgentRequest,
        current: RouteDecision,
        *,
        target_agent_id: str,
        intent: str,
        course_id: str,
        confidence: float,
        reason: str,
        reason_codes: list[str] | None = None,
        task_subtype: str = "",
    ) -> RouteDecision | None:
        """Validate and materialize a model-selected route."""

        if not self.overall_refinement_allowed(current):
            return None

        allowed = {str(item["agent_id"]) for item in OVERALL_ROUTE_CATALOG}
        if target_agent_id not in allowed:
            return None
        input_type = self._input_type(request)
        detected_course, course_reasons = self._detect_course(
            request, self.material_extractor.extract(request).raw_text
        )
        explicit_course = request.course_id.upper().strip()
        selected_course = (
            explicit_course
            if explicit_course not in {"", "AUTO", "UNKNOWN"}
            else course_id.upper().strip()
        )
        if selected_course not in {
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
            selected_course = current.course_id or detected_course
        selected_intent = intent.strip() or (
            Intent.GENERAL_QA.value
            if target_agent_id == GENERAL_QUESTION_AGENT_ID
            else AGENT_INTENT.get(target_agent_id, current.intent)
        )
        recognized_intent = str(current.intent_recognition.get("intent", ""))
        if target_agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1":
            selected_intent = Intent.ACADEMIC_SEARCH.value
        elif (
            recognized_intent == Intent.ACADEMIC_SEARCH.value
            and current.route_confidence >= 0.85
        ):
            # A bounded refiner must not turn a high-confidence research
            # request into writing/general QA because the word "paper" occurs.
            return None
        if selected_intent not in {item.value for item in Intent}:
            selected_intent = (
                Intent.GENERAL_QA.value
                if target_agent_id == GENERAL_QUESTION_AGENT_ID
                else AGENT_INTENT.get(target_agent_id, current.intent)
            )
        try:
            decision = self._decision_for_target(
                target_agent_id,
                request,
                course_id=selected_course,
                intent=selected_intent,
                input_type=input_type,
                confidence=max(0.0, min(1.0, confidence)),
            )
        except (KeyError, AgentInputNotSupportedError):
            return None
        aligned_recognition = IntentRecognitionService.align_to_intent(
            IntentRecognition.model_validate(current.intent_recognition or {}),
            selected_intent,
        )
        visited = list(dict.fromkeys([*current.visited_agents, target_agent_id]))
        return decision.model_copy(
            update={
                "reason": reason.strip() or "overall router selected a validated path",
                "route_source": "overall_router",
                "route_confidence": max(0.0, min(1.0, confidence)),
                "task_subtype": task_subtype.strip()
                or current.task_subtype
                or (
                    "academic_search"
                    if target_agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
                    else ""
                ),
                "secondary_intents": current.secondary_intents,
                "requires_pipeline": current.requires_pipeline,
                "candidate_agents": current.candidate_agents,
                "reason_codes": [
                    *course_reasons,
                    *current.reason_codes,
                    *(reason_codes or []),
                    "overall_router_selected",
                ][-12:],
                "local_confidence": current.local_confidence,
                "material_extraction": current.material_extraction,
                "inferred_user_role": AGENT_ROLE.get(
                    target_agent_id, request.user_role.value
                ),
                "visited_agents": visited,
                "reroute_count": current.reroute_count + 1,
                "intent_recognition": aligned_recognition.model_dump(mode="json"),
                "capabilities": list(aligned_recognition.capabilities),
                "selected_tools": list(aligned_recognition.selected_tools),
                "selected_skills": list(aligned_recognition.selected_skills),
                "route_mode": aligned_recognition.route_mode,
                "complexity": aligned_recognition.complexity,
                "needs_subagents": aligned_recognition.needs_subagents,
                "parallelizable": aligned_recognition.parallelizable,
                "route_revision": current.route_revision + 1,
                "route_trace": [
                    *current.route_trace,
                    {
                        "stage": "overall_refinement",
                        "source": "overall_router",
                        "from_agent_id": current.agent_id,
                        "to_agent_id": target_agent_id,
                        "from_intent": current.intent,
                        "to_intent": selected_intent,
                        "confidence": max(0.0, min(1.0, confidence)),
                        "reason": reason.strip()
                        or "overall router selected a validated path",
                    },
                ],
            }
        )

    def overall_refinement_allowed(self, current: RouteDecision) -> bool:
        """Apply the single policy boundary for a second routing pass."""

        if current.route_status != RouteStatus.SELECTED:
            return True
        if any(
            code in {
                "scenario_catalog_bound",
                "admin_debug_override",
                "session_continuity",
            }
            or code.startswith("explicit_intent:")
            for code in current.reason_codes
        ):
            return False
        structured_intent = str(current.intent_recognition.get("intent", ""))
        if (
            structured_intent == Intent.ACADEMIC_SEARCH.value
            and current.route_confidence >= 0.80
        ):
            return False
        if (
            structured_intent
            in {Intent.ACADEMIC_WRITING.value, Intent.DATA_ANALYSIS.value}
            and float(current.intent_recognition.get("confidence", 0.0)) >= 0.80
        ):
            return False
        threshold = self.settings.overall_routing_skip_confidence_threshold
        return not (
            current.local_confidence >= threshold
            and current.route_confidence >= threshold
            and not current.needs_subagents
            and not current.requires_pipeline
        )

    def _availability(
        self, agent_id: str, course_id: str, input_type: str, intent: str
    ) -> dict[str, bool]:
        definition = self.registry.get(agent_id)
        internal_available = internal_workflow_models_configured(
            self.settings, agent_id
        )
        return {
            "enabled": definition.enabled,
            "published": self.registry.is_execution_eligible(agent_id),
            "flow_configured": (
                self.registry.is_execution_eligible(agent_id)
                and self.registry.is_configured(agent_id, self.settings)
            ),
            "provider_available": (
                self.registry.is_execution_eligible(agent_id)
                and (
                    internal_available
                    or definition.provider == "local"
                    or (
                        self.settings.xingchen_enabled
                        and bool(self.settings.xingchen_api_key.get_secret_value())
                        and bool(self.settings.xingchen_api_secret.get_secret_value())
                    )
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
        # A strong cross-domain signal wins over a stale UI course hint. This
        # prevents a new AI/TCP question from inheriting the previous course.
        if IntentRecognitionService.is_cross_domain_topic(text):
            return "UNKNOWN", ["topic_outside_course", "course_hint_overridden"]
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
        non_course_topic_markers = (
            "人工智能",
            "机器学习",
            "深度学习",
            "生成式人工智能",
            "大模型",
            "transformer",
            "self-attention",
            "attention mechanism",
            "natural language processing",
            "computer vision",
            "large language model",
            "tcp",
            "tcp/ip",
            "syn+ack",
            "三次握手",
            "网络协议",
            "计算机网络",
            "http",
            "https",
            "dns",
            "websocket",
            "操作系统",
            "数据库",
            "sql",
            "linux",
            "python",
            "javascript",
        )
        if any(
            marker.casefold() in text.casefold()
            for marker in non_course_topic_markers
        ):
            return "UNKNOWN", ["topic_outside_course"]
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
        # The router is also used directly by integrations that do not pass
        # through XZDSupervisor. Keep a complete natural-language vocabulary
        # here as a second line of defense for those callers.
        for course, keywords in {
            "CT": (
                "电路理论",
                "戴维宁",
                "诺顿",
                "电感",
                "暂态",
                "稳态",
                "基尔霍夫",
                "KCL",
                "KVL",
            ),
            "AE": (
                "模拟电路",
                "运算放大器",
                "二极管",
                "反馈",
                "振荡",
                "稳压",
                "开关稳压",
                "线性稳压",
                "整流",
                "滤波",
                "晶体管",
                "MOS管",
            ),
            "DE": (
                "数字电路",
                "逻辑",
                "锁存器",
                "计数器",
                "寄存器",
                "时序逻辑",
                "组合逻辑",
            ),
            "SS": ("信号与系统", "卷积", "拉普拉斯变换"),
            "DSP": ("数字信号处理", "离散傅里叶", "z变换", "滤波器"),
            "COMM": ("通信原理", "调制", "解调", "信道编码"),
            "RF": ("高频电子", "谐振放大", "混频"),
            "EM": ("电磁场", "电磁波", "麦克斯韦"),
            "INFO": ("信息论", "信源编码", "信道容量"),
            "EMBEDDED": ("嵌入式", "单片机", "微控制器"),
            "IC": ("集成电路", "芯片设计", "版图"),
        }.items():
            scores[course] += 2 * sum(
                token.casefold() in text.casefold() for token in keywords
            )
        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        if scores[best] > 0 and list(scores.values()).count(scores[best]) == 1:
            return best, [f"detected_course:{best}"]
        previous = str(request.options.get("previous_course", "")).upper()
        if previous == "UNKNOWN":
            return "UNKNOWN", ["inherited_previous_course"]
        if previous in scores:
            return previous, ["inherited_previous_course"]
        return "CT", ["course_unspecified_default_context"]

    def _score(
        self, request: AgentRequest, materials: dict[str, Any], text: str
    ) -> _ScoredRoute:
        scores: dict[str, float] = defaultdict(float)
        reasons: dict[str, list[str]] = defaultdict(list)
        explicit = INTENT_AGENT.get(request.intent.value)
        if explicit and request.intent != Intent.GENERAL_QA:
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
                "RESEARCH_01_ACADEMIC_SEARCH_V1",
                (
                    "\u5173\u952e\u8fdb\u5c55",
                    "\u8fd1\u4e09\u5e74",
                    "\u4ea7\u4e1a\u62a5\u9053",
                    "研究进展",
                    "研究现状",
                    "前沿",
                    "趋势",
                    "最新研究",
                    "近期研究",
                    "技术进展",
                    "行业报道",
                    "会议",
                    "conference",
                    "workshop",
                    "news",
                    "state of the art",
                    "检索",
                    "查找资料",
                    "推荐文献",
                ),
                0.86,
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

        knowledge_markers = (
            "为什么",
            "是什么",
            "什么是",
            "解释",
            "讲解",
            "说明",
            "介绍",
            "原理",
            "概念",
            "特点",
            "区别",
            "作用",
            "如何理解",
            "怎么理解",
            "用途",
            "应用",
            "本地知识库",
            "本地资料",
            "课程资料",
            "知识库",
            "检索",
        )
        knowledge_hits = [
            token for token in knowledge_markers if token.casefold() in text.casefold()
        ]
        non_knowledge_score = max(
            (
                score
                for agent, score in scores.items()
                if agent != "LEARN_01_KNOWLEDGE_QA_V1"
            ),
            default=0.0,
        )
        if (
            knowledge_hits
            and non_knowledge_score < 0.60
            and scores.get("LEARN_01_KNOWLEDGE_QA_V1", 0.0) == 0.0
            and not str(request.options.get("previous_agent", "")).strip()
        ):
            add(
                "LEARN_01_KNOWLEDGE_QA_V1",
                min(0.72, 0.60 + 0.06 * len(knowledge_hits)),
                f"keywords:knowledge_language:{','.join(knowledge_hits[:4])}",
            )

        problem_actions = (
            "求",
            "计算",
            "求解",
            "解出",
            "列式",
            "列方程",
            "判断",
            "确定",
            "分析",
            "化简",
            "设计",
            "验证",
        )
        academic_targets = (
            "功率",
            "电压",
            "电流",
            "电阻",
            "阻抗",
            "导纳",
            "电荷",
            "能量",
            "相量",
            "频率",
            "增益",
            "响应",
            "传递函数",
            "状态方程",
            "微分方程",
            "工作点",
            "放大倍数",
            "输出",
            "输入",
            "逻辑式",
            "真值表",
            "卡诺图",
            "触发器",
            "波形",
            "卷积",
            "频谱",
            "系统函数",
            "误码率",
            "信噪比",
            "调制",
            "解调",
            "电路",
            "二极管",
            "晶体管",
            "MOS管",
        )
        has_problem_action = any(token in text for token in problem_actions)
        has_academic_target = any(token in text for token in academic_targets)
        has_quantified_condition = (
            any(char.isdigit() for char in text)
            or "=" in text
            or any(
                token in text
                for token in ("已知", "给定", "条件", "参数", "参考方向", "初始值")
            )
        )
        is_assignment_review = bool(
            materials.get("student_answer")
            or materials.get("rubric")
            or any(
                token in text
                for token in ("批改", "评分标准", "教师反馈", "给分", "满分")
            )
        )
        is_lesson_design = any(
            token in text
            for token in ("教案", "备课", "教学设计", "教学流程", "课堂活动", "课时")
        ) or (
            "课程" in text
            and any(token in text for token in ("设计", "教学", "备课", "课堂"))
        )
        if (
            has_problem_action
            and has_academic_target
            and not is_assignment_review
            and not is_lesson_design
        ):
            add(
                "ACADEMIC_PROBLEM_SOLVER",
                0.86 if has_quantified_condition else 0.72,
                "domain_contract:academic_problem_language",
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

        dynamic_circuit_problem = any(
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
        ) and any(
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
            for token in (
                "刚才",
                "上面",
                "之前",
                "上一轮",
                "这个",
                "这些",
                "接着",
                "继续",
                "然后",
                "另外",
                "还有",
                "额外",
                "补充",
                "再提供",
                "更多",
                "进一步",
                "压缩成",
                "改成",
            )
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
        data_files = [
            item
            for item in request.attachments
            if not item.content_type.startswith("image/")
        ]
        if images and data_files:
            return "mixed"
        if len(images) > 1:
            return "text_and_multi_image" if has_text else "multi_image"
        if has_text and images:
            return "text_and_single_image"
        if images:
            return "single_image"
        if data_files:
            return "text_and_data_file" if has_text else "data_file"
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
        local_analysis_v2 = (
            primary.agent_id == "RESEARCH_03_DATA_ANALYSIS_V1"
            and isinstance(request.options.get("research_analysis_v2"), dict)
        )
        internal_available = internal_workflow_models_configured(
            self.settings, primary.agent_id
        ) or local_analysis_v2
        runtime_available = local_analysis_v2 or self.registry.is_runtime_available(
            primary.agent_id, self.settings
        )
        primary_eligible = self.registry.is_execution_eligible(primary.agent_id)
        local_only = (
            primary.provider == "xingchen"
            and not cloud_allowed
            and not internal_available
        )
        if not primary_eligible or local_only or not runtime_available:
            fallback = self.registry.resolve_fallback(primary.agent_id)
            if fallback is not None and self.registry.is_execution_eligible(
                fallback.agent_id
            ) and (
                self.registry.is_runtime_available(fallback.agent_id, self.settings)
                or self.registry.allows_unconfigured_route(fallback.agent_id)
            ):
                selected = fallback
                fallback_used = True
                source = "local_degraded"
            elif primary_eligible and (
                self.registry.allows_unconfigured_route(primary.agent_id)
                or (
                    local_only
                    and self.registry.has_local_execution_contract(primary.agent_id)
                )
            ):
                source = "local_only" if local_only else "local_degraded"
            else:
                return RouteDecision(
                    agent_id="UNRESOLVED",
                    scene=primary.scene,
                    course_id=course_id,
                    intent=intent,
                    route_status=RouteStatus.UNRESOLVED,
                    reason=f"configured agent unavailable: {primary.agent_id}",
                    retrieval_required=False,
                    provider_required=False,
                    route_source="local_degraded",
                    route_confidence=0.0,
                    original_agent_id=primary.agent_id,
                )
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
                and self.registry.is_runtime_available(selected.agent_id, self.settings)
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
        primary_eligible = self.registry.is_execution_eligible(primary.agent_id)

        if not primary_eligible or local_only or (
            not self.registry.allows_unconfigured_route(primary.agent_id)
            and not self.registry.is_runtime_available(primary.agent_id, self.settings)
        ):
            fallback = self.registry.resolve_fallback(primary.agent_id)
            if fallback and self.registry.is_execution_eligible(fallback.agent_id) and (
                self.registry.allows_unconfigured_route(fallback.agent_id)
                or self.registry.is_runtime_available(fallback.agent_id, self.settings)
            ):
                selected = fallback
                fallback_used = True
                source = "local_degraded"
            elif not primary_eligible or not (
                local_only
                and self.registry.has_local_execution_contract(primary.agent_id)
            ):
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
                and self.registry.is_runtime_available(selected.agent_id, self.settings)
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
        if not self.registry.is_execution_eligible(target.agent_id):
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
        target_intent = AGENT_INTENT.get(target.agent_id, request.intent.value)
        routing = request.options.get("_routing", {})
        prior_recognition = (
            routing.get("intent_recognition", {})
            if isinstance(routing, dict)
            else {}
        )
        aligned_recognition = IntentRecognitionService.align_to_intent(
            IntentRecognition.model_validate(prior_recognition), target_intent
        )
        return RouteDecision(
            agent_id=target.agent_id,
            scene=target.scene,
            course_id=request.course_id.upper(),
            intent=target_intent,
            route_status=RouteStatus.SELECTED,
            reason="validated one-pass cloud dispatch target",
            retrieval_required=target.mode != "routing_only",
            provider_required=target.provider == "xingchen",
            route_source="cloud_fallback",
            route_confidence=max(0.0, min(1.0, float(confidence))),
            fallback_used=True,
            original_agent_id="ROUTER_01_FALLBACK_V1",
            intent_recognition=aligned_recognition.model_dump(mode="json"),
            capabilities=list(aligned_recognition.capabilities),
            selected_tools=list(aligned_recognition.selected_tools),
            selected_skills=list(aligned_recognition.selected_skills),
            route_mode=aligned_recognition.route_mode,
            complexity=aligned_recognition.complexity,
            needs_subagents=aligned_recognition.needs_subagents,
            parallelizable=aligned_recognition.parallelizable,
            route_trace=[
                {
                    "stage": "cloud_refinement",
                    "source": "cloud_fallback",
                    "from_agent_id": "ROUTER_01_FALLBACK_V1",
                    "to_agent_id": target.agent_id,
                    "intent": target_intent,
                    "confidence": max(0.0, min(1.0, float(confidence))),
                }
            ],
        )
