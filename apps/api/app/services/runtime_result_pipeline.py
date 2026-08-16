from __future__ import annotations

import logging
from dataclasses import dataclass

from app.agents import AgentDefinition, AgentRegistry
from app.contracts import (
    AgentExecutionPlan,
    AgentRequest,
    AgentResult,
    AgentValidationResult,
    IntentExecutionPlan,
    TeachingMode,
)
from app.contracts.solver import SolverResult
from app.core.config import Settings
from app.courses import CourseRegistry
from app.services.agent_result_governance import AgentResultValidatorRegistry
from app.services.response_depth import policy_for
from app.services.scenario_output_contract import ScenarioOutputContractService
from app.services.solver_quality_gate import SolverQualityGateService
from app.services.teaching_foundation import TeachingFoundationService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GovernedRuntimeResult:
    result: AgentResult
    validation: AgentValidationResult
    routing: dict[str, object]


class RuntimeResultPipeline:
    """Apply cross-Agent result policy after Runtime has completed."""

    def __init__(
        self,
        registry: AgentRegistry,
        settings: Settings,
        validators: AgentResultValidatorRegistry,
        scenario_contract: ScenarioOutputContractService,
        solver_quality_gate: SolverQualityGateService,
        *,
        course_registry: CourseRegistry | None,
        teaching_foundation: TeachingFoundationService | None,
    ) -> None:
        self.registry = registry
        self.settings = settings
        self.validators = validators
        self.scenario_contract = scenario_contract
        self.solver_quality_gate = solver_quality_gate
        self.course_registry = course_registry
        self.teaching_foundation = teaching_foundation

    def process(
        self,
        *,
        definition: AgentDefinition,
        agent_id: str,
        request: AgentRequest,
        result: AgentResult,
        execution_plan: AgentExecutionPlan,
        intent_plan: IntentExecutionPlan | None,
        overall_route_metadata: dict[str, object],
    ) -> GovernedRuntimeResult:
        raw_routing = request.options.get("_routing", {})
        routing = dict(raw_routing) if isinstance(raw_routing, dict) else {}
        result.course_id = request.course_id
        result.intent = request.intent.value
        result.request_id = str(request.options.get("request_id", request.task_id))
        result.task_id = request.task_id
        result.trace_id = str(request.options.get("trace_id", ""))
        result.cloud_status = "not_required"
        result.fallback_used = bool(
            result.fallback_used or routing.get("fallback_used", False)
        )
        result.fallback_reason = result.fallback_reason or str(
            routing.get("fallback_reason", "")
        )
        result = self._apply_solver_quality_gate(result, request, agent_id)
        result = self._apply_teaching_foundation(result, request)
        if result.fallback_used and not result.fallback_reason:
            result.fallback_reason = "runtime_fallback"
        result = self.scenario_contract.enrich(result, request)
        self._ensure_response_depth_metadata(result, request, agent_id)
        validation = self.validators.validate(definition, result, request, None)
        result.structured_result["validation"] = validation.model_dump(mode="json")
        result.structured_result["result_status"] = validation.result_status
        result.structured_result["material_extraction"] = request.options.get(
            "_material_extraction",
            {},
        )
        knowledge = result.structured_result.get("knowledge", {})
        hits = knowledge.get("hits", []) if isinstance(knowledge, dict) else []
        result.structured_result.update(
            {
                "scene": definition.scene,
                "mode": definition.mode,
                "course": request.course_id,
                "intent": request.intent.value,
                "route_source": routing.get("route_source", "local_fast"),
                "route_confidence": routing.get("route_confidence", 1.0),
                "target_agent_id": agent_id,
                "local_ready": self.registry.is_configured(agent_id, self.settings),
                "knowledge_hit_count": len(hits) if isinstance(hits, list) else 0,
                "rag_status": result.rag_status,
                "intent_recognition": dict(
                    routing.get("intent_recognition", {})
                    if isinstance(routing.get("intent_recognition", {}), dict)
                    else {}
                ),
                "intent_plan": (
                    intent_plan.model_dump(mode="json")
                    if intent_plan is not None
                    else {}
                ),
                "evidence_status": result.evidence_status,
                "related_images": result.related_images,
                "retrieval_trace_id": result.retrieval_trace_id,
                "retrieval_latency_ms": result.retrieval_latency_ms,
                "index_version": result.index_version,
                "execution_plan": execution_plan.model_dump(mode="json"),
                "fallback_used": result.fallback_used,
                "fallback_reason": result.fallback_reason,
                "cloud_status": result.cloud_status,
                "execution_source": self._execution_source(result.provider),
                "original_agent_id": routing.get("original_agent_id"),
                "overall_routing": overall_route_metadata,
            }
        )
        return GovernedRuntimeResult(result, validation, routing)

    @staticmethod
    def _ensure_response_depth_metadata(
        result: AgentResult, request: AgentRequest, agent_id: str
    ) -> None:
        """Expose the effective depth for every Runtime-backed workflow.

        Business adapters may already provide a richer policy projection. The
        pipeline fills the gap for research/external adapters so the UI and
        task history can explain what changed when the user switches depth.
        """

        workflow = (
            "academic_search"
            if agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
            else "academic_solver"
            if agent_id == "ACADEMIC_PROBLEM_SOLVER"
            else "lesson_prep"
            if agent_id == "TEACH_01_LESSON_PREP_V1"
            else "internal_structured"
            if agent_id in {
                "TEACH_02_ASSIGNMENT_REVIEW_V1",
                "RESEARCH_02_ACADEMIC_WRITING_V1",
            }
            else "knowledge_qa"
            if agent_id in {
                "LEARN_01_KNOWLEDGE_QA_V1",
                "LEARN_01_LOCAL_RETRIEVAL_V1",
            }
            else "general_question"
        )
        current = result.structured_result.get("response_depth")
        if isinstance(current, dict) and current.get("level"):
            return
        result.structured_result["response_depth"] = policy_for(
            request.options, workflow
        ).metadata()

    def _apply_teaching_foundation(
        self,
        result: AgentResult,
        request: AgentRequest,
    ) -> AgentResult:
        if self.teaching_foundation is None:
            return result
        try:
            return self.teaching_foundation.enrich(
                result,
                request,
                None,
                query=request.input_text(),
            )
        except Exception:
            logger.exception(
                "teaching_foundation_unexpected_error task_id=%s",
                request.task_id,
            )
            return self._teaching_degraded_result(result, request)

    def _teaching_degraded_result(
        self,
        result: AgentResult,
        request: AgentRequest,
    ) -> AgentResult:
        assert self.teaching_foundation is not None
        try:
            mode = TeachingMode(
                str(request.options.get("teaching_mode", TeachingMode.DIRECT_ANSWER))
            )
        except ValueError:
            mode = TeachingMode.DIRECT_ANSWER
        policy = self.teaching_foundation.disclosure.policy(mode)
        structured = dict(result.structured_result)
        structured["teaching"] = {
            "teaching_mode": mode.value,
            "mode_status": "degraded",
            "student_attempt_present": isinstance(
                request.options.get("student_attempt"),
                dict,
            ),
            "requires_manual_review": True,
        }
        degraded = result.model_copy(
            update={
                "structured_result": structured,
                "warnings": list(
                    dict.fromkeys(
                        [*result.warnings, "teaching_enrichment_degraded"]
                    )
                ),
            }
        )
        if mode == TeachingMode.DIRECT_ANSWER:
            return degraded
        filtered, disclosure_ms = self.teaching_foundation.disclosure.apply(
            degraded,
            policy=policy,
            hint=None,
            next_check=None,
            verification=None,
        )
        return filtered.model_copy(
            update={
                "metrics": filtered.metrics.model_copy(
                    update={
                        "teaching_mode": mode.value,
                        "manual_review_required": True,
                        "answer_disclosure_mode": policy.mode.value,
                        "full_solution_disclosed": False,
                        "disclosure_filter_ms": disclosure_ms,
                    }
                )
            }
        )

    def _apply_solver_quality_gate(
        self,
        result: AgentResult,
        request: AgentRequest,
        agent_id: str,
    ) -> AgentResult:
        definition = self.registry.get(agent_id)
        if (
            self.course_registry is None
            or "ACADEMIC_SOLVING" not in definition.task_families
        ):
            return result
        structured = dict(result.structured_result)
        payload = {
            key: value
            for key, value in structured.items()
            if key in SolverResult.model_fields
        }
        payload.setdefault("status", structured.get("status", "partial"))
        payload.setdefault("course", request.course_id)
        payload.setdefault("problem_summary", request.input_text()[:500])
        payload.setdefault(
            "final_answer",
            structured.get("final_answer", result.answer),
        )
        payload.setdefault(
            "execution_path",
            structured.get("execution_path", "STANDARD"),
        )
        try:
            solver_result = SolverResult.model_validate(payload)
        except ValueError:
            return result
        checked = self.solver_quality_gate.evaluate(
            solver_result,
            self.course_registry.get(request.course_id),
        )
        structured.update(checked.model_dump(mode="json"))
        return result.model_copy(update={"structured_result": structured})

    @staticmethod
    def _execution_source(provider: str) -> str:
        if provider == "local_agent":
            return "internal_agent"
        if provider == "local":
            return "local_rag"
        return "provider"
