from __future__ import annotations

from collections.abc import Sequence
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.planner import (
    CanonicalPlan,
    CanonicalPlanNode,
    PlannerSkillSelection,
)
from app.runtime.handler_registry import RuntimeHandlerRegistry
from app.services.canonical_plan_adapter import CanonicalPlanAdapter
from app.services.skill_binding import SkillBindingResult, SkillBindingService
from app.services.skill_policy import SkillPolicy
from app.services.skill_registry import SkillRegistry
from app.services.skill_retriever import SkillRetrievalRequest, SkillRetriever

SkillEvidenceLevel = Literal[
    "synthetic_provider_free",
    "offline_real_case",
    "real_provider_test",
    "controlled_canary",
    "production",
]
SkillEvaluationDecision = Literal["GO", "NO_GO"]
SkillSelectionStatus = Literal["valid", "empty", "rejected", "fallback"]


class SkillEvaluationCase(BaseModel):
    """A bounded skill-control case; it never stores prompts or answers."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    evidence_level: SkillEvidenceLevel
    request: SkillRetrievalRequest
    expected_selection: SkillSelectionStatus
    expected_skill_ids: list[str] = Field(default_factory=list, max_length=16)
    plan_skill_ids: list[str] = Field(default_factory=list, max_length=16)
    expected_binding_handlers: dict[str, str] = Field(
        default_factory=dict, max_length=16
    )
    expected_rejection_codes: list[str] = Field(default_factory=list, max_length=16)
    resume_from_checkpoint: bool = False
    token_count: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0, ge=0)


class SkillEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    title: str
    evidence_level: SkillEvidenceLevel
    selection_status: SkillSelectionStatus
    selected_skill_ids: list[str] = Field(default_factory=list)
    approved_skill_ids: list[str] = Field(default_factory=list)
    rejected_skill_ids: list[str] = Field(default_factory=list)
    rejection_codes: list[str] = Field(default_factory=list)
    policy_rejection_count: int = Field(default=0, ge=0)
    binding_status: Literal["bound", "empty", "rejected"]
    bound_skill_ids: list[str] = Field(default_factory=list)
    handler_ids: list[str] = Field(default_factory=list)
    plan_compatible: bool = False
    resume_compatible: bool | None = None
    runtime_failure: bool = False
    task_outcome_quality: float | None = None
    token_count: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0, ge=0)
    latency_ms: float = Field(default=0, ge=0)
    passed: bool
    failure_reasons: list[str] = Field(default_factory=list)


class SkillEvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["skill_evaluation.v1"] = "skill_evaluation.v1"
    evidence_level: SkillEvidenceLevel
    decision: SkillEvaluationDecision
    results: list[SkillEvaluationResult] = Field(default_factory=list)
    metrics: dict[str, int | float | bool] = Field(default_factory=dict)
    rollback_integrity: bool
    provider_free: bool


class SkillCanaryConfig(BaseModel):
    """Default-off, allowlisted policy for a future controlled takeover."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    allowlist: list[str] = Field(default_factory=list, max_length=32)
    rollback_enabled: bool = True
    automatic_expansion: bool = False


class SkillCanaryDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["disabled", "approved", "rejected", "rolled_back"]
    skill_ids: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    rollback_integrity: bool = True


class SkillControlledCanary:
    """Policy-only canary gate; it does not mutate Runtime or launch Agents."""

    def decide(
        self,
        report: SkillEvaluationReport,
        skill_ids: Sequence[str],
        config: SkillCanaryConfig | None = None,
    ) -> SkillCanaryDecision:
        policy = config or SkillCanaryConfig()
        selected = list(dict.fromkeys(str(item).strip() for item in skill_ids if item))
        if not policy.enabled:
            return SkillCanaryDecision(
                status="disabled",
                skill_ids=selected,
                reason_codes=["canary_default_off"],
            )
        reasons: list[str] = []
        if report.evidence_level != "controlled_canary":
            reasons.append("evidence_level_not_controlled_canary")
        if report.decision != "GO":
            reasons.append("evaluation_no_go")
        if not policy.rollback_enabled:
            reasons.append("rollback_not_configured")
        if policy.automatic_expansion:
            reasons.append("automatic_expansion_forbidden")
        if not selected:
            reasons.append("canary_allowlist_empty")
        if not set(selected).issubset(set(policy.allowlist)):
            reasons.append("skill_not_allowlisted")
        if reasons:
            return SkillCanaryDecision(
                status="rejected",
                skill_ids=selected,
                reason_codes=list(dict.fromkeys(reasons)),
            )
        return SkillCanaryDecision(status="approved", skill_ids=selected)

    def rollback(
        self, decision: SkillCanaryDecision
    ) -> SkillCanaryDecision:
        """Return a non-active decision without changing any Runtime state."""

        return decision.model_copy(
            update={
                "status": "rolled_back",
                "reason_codes": [*decision.reason_codes, "manual_rollback"],
                "skill_ids": [],
                "rollback_integrity": True,
            }
        )


class SkillEvaluationService:
    """Provider-free evaluation of the existing Skill control chain."""

    def __init__(
        self,
        skill_registry: SkillRegistry,
        runtime_handlers: RuntimeHandlerRegistry,
        *,
        available_workers: Sequence[str] = (),
    ) -> None:
        self.registry = skill_registry
        self.retriever = SkillRetriever(skill_registry)
        self.policy = SkillPolicy(skill_registry)
        self.binding = SkillBindingService(
            skill_registry,
            runtime_handlers,
            available_workers=available_workers,
        )

    def evaluate(
        self,
        cases: Sequence[SkillEvaluationCase],
        *,
        evidence_level: SkillEvidenceLevel | None = None,
    ) -> SkillEvaluationReport:
        if not cases:
            raise ValueError("skill evaluation requires at least one case")
        levels = {case.evidence_level for case in cases}
        if evidence_level is not None:
            levels.add(evidence_level)
        if len(levels) != 1:
            raise ValueError("one report must contain one evidence level")
        level = next(iter(levels))
        results = [self.evaluate_case(case) for case in cases]
        metrics = self._metrics(results)
        decision: SkillEvaluationDecision = (
            "GO" if all(item.passed for item in results) else "NO_GO"
        )
        return SkillEvaluationReport(
            evidence_level=level,
            decision=decision,
            results=results,
            metrics=metrics,
            rollback_integrity=True,
            provider_free=level == "synthetic_provider_free",
        )

    def evaluate_case(self, case: SkillEvaluationCase) -> SkillEvaluationResult:
        started = perf_counter()
        matches = self.retriever.retrieve(case.request)
        policy_result = self.policy.evaluate(matches, case.request)
        approved_ids = [item.skill_id for item in policy_result.approved]
        rejected_ids = [item.skill_id for item in policy_result.rejected]
        rejection_codes = [
            code
            for item in policy_result.rejected
            for code in item.reason_codes
        ]
        unknown_requested = self._unknown_requested(case.request.requested_skill_ids)
        if unknown_requested:
            rejection_codes.append("unregistered_skill")
            rejected_ids.extend(unknown_requested)

        selected_ids = list(case.plan_skill_ids or approved_ids)
        selection_status = self._selection_status(
            case, approved_ids, rejection_codes
        )
        binding_result = self._binding_result(case, selected_ids)
        bound_ids = [item.skill_id for item in binding_result.bindings]
        handler_ids = [item.handler_id for item in binding_result.bindings]
        binding_reasons = [
            code
            for item in binding_result.rejected
            for code in item.reason_codes
        ]
        rejection_codes = list(dict.fromkeys([*rejection_codes, *binding_reasons]))
        plan_compatible, resume_compatible = self._plan_compatibility(
            case, selected_ids, binding_result
        )
        failures: list[str] = []
        if selection_status != case.expected_selection:
            failures.append("selection_status_mismatch")
        if case.expected_skill_ids and not set(case.expected_skill_ids).issubset(
            set(approved_ids)
        ):
            failures.append("expected_skill_not_approved")
        if case.expected_rejection_codes and not set(
            case.expected_rejection_codes
        ).issubset(set(rejection_codes)):
            failures.append("expected_rejection_missing")
        for skill_id, handler_id in case.expected_binding_handlers.items():
            actual = next(
                (
                    item.handler_id
                    for item in binding_result.bindings
                    if item.skill_id == skill_id
                ),
                None,
            )
            if actual != handler_id:
                failures.append("handler_mismatch")
                rejection_codes.append("handler_mismatch")
        if binding_result.status == "bound" and not plan_compatible:
            failures.append("plan_incompatible")
        if case.resume_from_checkpoint and not resume_compatible:
            failures.append("resume_incompatible")
        elapsed_ms = (perf_counter() - started) * 1000
        return SkillEvaluationResult(
            case_id=case.case_id,
            title=case.title,
            evidence_level=case.evidence_level,
            selection_status=selection_status,
            selected_skill_ids=selected_ids,
            approved_skill_ids=approved_ids,
            rejected_skill_ids=list(dict.fromkeys(rejected_ids)),
            rejection_codes=list(dict.fromkeys(rejection_codes)),
            policy_rejection_count=len(policy_result.rejected),
            binding_status=binding_result.status,
            bound_skill_ids=bound_ids,
            handler_ids=handler_ids,
            plan_compatible=plan_compatible,
            resume_compatible=resume_compatible,
            runtime_failure=False,
            task_outcome_quality=None,
            token_count=case.token_count,
            estimated_cost=case.estimated_cost,
            latency_ms=elapsed_ms,
            passed=not failures,
            failure_reasons=list(dict.fromkeys(failures)),
        )

    def _binding_result(
        self, case: SkillEvaluationCase, selected_ids: Sequence[str]
    ) -> SkillBindingResult:
        plan = self._plan(case.request, selected_ids)
        return self.binding.resolve_plan(plan)

    @staticmethod
    def _plan(
        request: SkillRetrievalRequest, selected_ids: Sequence[str]
    ) -> CanonicalPlan:
        goal = request.goal.model_copy(
            update={
                "course": request.normalized_course,
                "intent": request.intent or request.goal.intent,
            }
        )
        nodes = [
            CanonicalPlanNode(
                node_id=f"skill.evaluate.{index}",
                node_type="skill",
                target_id=skill_id,
            )
            for index, skill_id in enumerate(selected_ids, start=1)
        ]
        if not nodes:
            nodes = [
                CanonicalPlanNode(
                    node_id="skill.evaluate.fallback",
                    node_type="verifier",
                    target_id="skill-selection-fallback",
                )
            ]
        return CanonicalPlan(
            plan_id=f"skill-evaluation:{request.normalized_course or 'fallback'}",
            goal=goal,
            nodes=nodes,
            capabilities=list(request.capabilities),
            selected_skills=list(selected_ids),
            skill_selection=[
                PlannerSkillSelection(
                    skill_id=skill_id,
                    version="",
                    status="selected",
                )
                for skill_id in selected_ids
            ],
        )

    def _plan_compatibility(
        self,
        case: SkillEvaluationCase,
        selected_ids: Sequence[str],
        binding_result: SkillBindingResult,
    ) -> tuple[bool, bool | None]:
        if binding_result.status != "bound":
            return not selected_ids, None
        plan = self._plan(case.request, selected_ids).model_copy(
            update={"skill_bindings": binding_result.bindings}
        )
        try:
            runtime_plan = CanonicalPlanAdapter.to_runtime_plan(plan)
            restored = CanonicalPlanAdapter.from_agent_run_plan(runtime_plan)
        except (TypeError, ValueError):
            return False, False if case.resume_from_checkpoint else None
        runtime_bindings = {
            item.skill_id: item for item in restored.skill_bindings
        }
        compatible = all(
            skill_id in runtime_bindings for skill_id in selected_ids
        )
        resumed = (
            compatible
            and [item.version for item in restored.skill_bindings]
            == [item.version for item in binding_result.bindings]
        )
        return compatible, resumed if case.resume_from_checkpoint else None

    def _unknown_requested(self, skill_ids: Sequence[str]) -> list[str]:
        unknown: list[str] = []
        for skill_id in skill_ids:
            try:
                self.registry.resolve(skill_id)
            except KeyError:
                unknown.append(skill_id)
        return unknown

    @staticmethod
    def _selection_status(
        case: SkillEvaluationCase,
        approved_ids: Sequence[str],
        rejection_codes: Sequence[str],
    ) -> SkillSelectionStatus:
        if case.expected_selection == "fallback":
            return "fallback" if not approved_ids else "valid"
        if not approved_ids and rejection_codes:
            return "rejected"
        if not approved_ids:
            return "empty"
        return "valid"

    @staticmethod
    def _metrics(
        results: Sequence[SkillEvaluationResult],
    ) -> dict[str, int | float | bool]:
        def count(code: str) -> int:
            return sum(code in item.rejection_codes for item in results)

        latencies = [item.latency_ms for item in results]
        return {
            "case_count": len(results),
            "passed_case_count": sum(item.passed for item in results),
            "valid_selection_count": sum(
                item.selection_status == "valid" for item in results
            ),
            "empty_selection_count": sum(
                item.selection_status == "empty" for item in results
            ),
            "fallback_selection_count": sum(
                item.selection_status == "fallback" for item in results
            ),
            "invalid_unregistered_count": count("unregistered_skill"),
            "prerequisite_rejection_count": count("prerequisite_missing"),
            "policy_rejection_count": sum(
                item.policy_rejection_count for item in results
            ),
            "binding_success_count": sum(
                item.binding_status == "bound" for item in results
            ),
            "handler_mismatch_count": count("handler_mismatch"),
            "plan_compatibility_count": sum(
                item.plan_compatible for item in results
            ),
            "runtime_failure_count": sum(item.runtime_failure for item in results),
            "latency_ms_total": sum(latencies),
            "latency_ms_average": sum(latencies) / len(latencies),
            "token_count": sum(item.token_count for item in results),
            "estimated_cost": sum(item.estimated_cost for item in results),
            "task_outcome_quality_observed": sum(
                item.task_outcome_quality is not None for item in results
            ),
            "rollback_integrity": True,
        }


__all__ = [
    "SkillCanaryConfig",
    "SkillCanaryDecision",
    "SkillControlledCanary",
    "SkillEvaluationCase",
    "SkillEvaluationReport",
    "SkillEvaluationResult",
    "SkillEvaluationService",
]
