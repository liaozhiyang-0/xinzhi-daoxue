from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.planner import (
    CanonicalPlan,
    PlannerSkillSelection,
    SkillExecutionDescriptor,
)
from app.runtime.handler_registry import (
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeHandlerRegistryError,
)
from app.services.skill_policy import SkillPolicy
from app.services.skill_registry import SkillDefinition, SkillMatch, SkillRegistry
from app.services.skill_retriever import SkillRetrievalRequest


class SkillBindingRejection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str = Field(min_length=1, max_length=128)
    version: str = Field(default="", max_length=32)
    reason_codes: list[str] = Field(min_length=1, max_length=16)


class SkillBindingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["bound", "empty", "rejected"]
    bindings: list[SkillExecutionDescriptor] = Field(
        default_factory=list, max_length=32
    )
    rejected: list[SkillBindingRejection] = Field(
        default_factory=list, max_length=32
    )


class SkillBindingError(RuntimeError):
    def __init__(
        self,
        error_code: str,
        *,
        rejections: Sequence[SkillBindingRejection] = (),
    ) -> None:
        self.error_code = error_code
        self.rejections = tuple(rejections)
        super().__init__(error_code)


class SkillBindingService:
    """Resolve approved Skills to the existing Runtime handler registry.

    This service only produces metadata. It never invokes a Tool, Worker,
    Provider, or Agent and it does not own checkpoints or execution state.
    """

    _CAPABILITY_TO_TOOLS: dict[str, tuple[str, ...]] = {
        "algebra": ("calculator",),
        "complex_numbers": ("complex_number_tool",),
        "differential_equations": ("sympy_solver",),
        "equation_system": ("linear_equation_solver",),
        "unit_validation": ("unit_checker",),
    }
    _WORKER_TARGETS: dict[str, str] = {
        "AcademicPaperReviewService": "ACADEMIC_PAPER_REVIEW_LOCAL_V1",
        "AcademicSearchPlannerService": "RESEARCH_01_ACADEMIC_SEARCH_V1",
        "KnowledgeQAService": "LEARN_01_KNOWLEDGE_QA_V1",
        "ResearchAnalysisReviewService": "RESEARCH_FRONTIER_BRIEF_LOCAL_V1",
        "ResearchAnalysisRuntimeService": "RESEARCH_03_DATA_ANALYSIS_V1",
        "ResearchKnowledgeService": "RESEARCH_FRONTIER_KNOWLEDGE_LOCAL_V1",
        "LessonPrepRuntimeService": "TEACH_01_LESSON_PREP_V1",
        "AssignmentReviewRuntimeService": "TEACH_02_ASSIGNMENT_REVIEW_V1",
        "LearningPathRuntimeService": "LEARN_01_LOCAL_RETRIEVAL_V1",
        "AcademicProblemSolver": "ACADEMIC_PROBLEM_SOLVER",
    }

    def __init__(
        self,
        skill_registry: SkillRegistry,
        runtime_handlers: RuntimeHandlerRegistry,
        *,
        available_workers: Sequence[str] = (),
    ) -> None:
        self.skill_registry = skill_registry
        self.runtime_handlers = runtime_handlers
        self.available_workers = tuple(
            sorted(
                {
                    str(item).strip()
                    for item in available_workers
                    if str(item).strip()
                }
            )
        )
        if not self.available_workers:
            self.available_workers = tuple(
                sorted(
                    worker
                    for worker, target in self._WORKER_TARGETS.items()
                    if self._handler_enabled(f"subagent.{target}")
                )
            )
        self.policy = SkillPolicy(skill_registry)

    def _handler_enabled(self, handler_id: str) -> bool:
        try:
            return self.runtime_handlers.descriptor(handler_id).enabled
        except RuntimeHandlerRegistryError:
            return False

    def resolve_plan(self, plan: CanonicalPlan) -> SkillBindingResult:
        """Resolve every selected Skill or return explicit fail-closed reasons."""

        selections = self._selections(plan)
        if not selections:
            return SkillBindingResult(status="empty")

        request = self._policy_request(plan)
        bindings: list[SkillExecutionDescriptor] = []
        rejected: list[SkillBindingRejection] = []
        for selection in selections:
            try:
                skill = self.skill_registry.resolve(
                    selection.skill_id,
                    version=selection.version or None,
                )
            except KeyError:
                rejected.append(
                    SkillBindingRejection(
                        skill_id=selection.skill_id,
                        version=selection.version,
                        reason_codes=["unregistered_skill"],
                    )
                )
                continue
            except ValueError:
                rejected.append(
                    SkillBindingRejection(
                        skill_id=selection.skill_id,
                        version=selection.version,
                        reason_codes=["version_mismatch"],
                    )
                )
                continue

            policy_reasons = self._policy_reasons(skill, selection, plan, request)
            if policy_reasons:
                rejected.append(
                    SkillBindingRejection(
                        skill_id=skill.skill_id,
                        version=skill.version,
                        reason_codes=policy_reasons,
                    )
                )
                continue

            descriptor = self._resolve_handler(skill)
            if descriptor is None:
                rejected.append(
                    SkillBindingRejection(
                        skill_id=skill.skill_id,
                        version=skill.version,
                        reason_codes=["no_existing_runtime_handler"],
                    )
                )
                continue
            bindings.append(self._execution_descriptor(skill, descriptor))

        if rejected:
            return SkillBindingResult(
                status="rejected",
                bindings=bindings,
                rejected=rejected,
            )
        return SkillBindingResult(status="bound", bindings=bindings)

    def bind_plan(self, plan: CanonicalPlan) -> CanonicalPlan:
        """Attach only policy-approved, existing-handler bindings to a plan."""

        result = self.resolve_plan(plan)
        if result.rejected:
            raise SkillBindingError(
                "skill_binding_rejected",
                rejections=result.rejected,
            )
        return plan.model_copy(update={"skill_bindings": result.bindings})

    bind_canonical_plan = bind_plan

    def _selections(self, plan: CanonicalPlan) -> list[PlannerSkillSelection]:
        if plan.skill_selection:
            selected = [
                item for item in plan.skill_selection if item.status == "selected"
            ]
            rejected = [
                item
                for item in plan.skill_selection
                if item.status == "rejected"
            ]
            if rejected:
                return [
                    *selected,
                    *rejected,
                ]
            return selected
        return [
            PlannerSkillSelection(
                skill_id=skill_id,
                version="",
                status="selected",
            )
            for skill_id in plan.selected_skills
        ]

    def _policy_request(self, plan: CanonicalPlan) -> SkillRetrievalRequest:
        constraints = plan.goal.constraints
        evidence_state = constraints.get("evidence_state", {})
        if not isinstance(evidence_state, Mapping):
            evidence_state = {}
        max_risk = constraints.get("max_risk", "low")
        available_tools = sorted(
            descriptor.handler_id.removeprefix("tool.")
            for descriptor in self.runtime_handlers.descriptors()
            if descriptor.enabled and descriptor.kind == "tool"
        )
        return SkillRetrievalRequest(
            goal=plan.goal,
            course=plan.goal.course,
            intent=plan.goal.intent,
            capabilities=list(plan.capabilities),
            available_workers=list(self.available_workers),
            available_tools=available_tools,
            available_skill_ids=list(plan.selected_skills),
            evidence_state=dict(evidence_state),
            max_risk=str(max_risk),
        )

    def _policy_reasons(
        self,
        skill: SkillDefinition,
        selection: PlannerSkillSelection,
        plan: CanonicalPlan,
        request: SkillRetrievalRequest,
    ) -> list[str]:
        if selection.status != "selected":
            return ["planner_skill_not_approved"]
        prerequisite_ok, _ = self.skill_registry.validate_prerequisites(
            skill.skill_id,
            available_skill_ids=plan.selected_skills,
        )
        match = SkillMatch(
            skill_id=skill.skill_id,
            score=selection.score,
            match_reasons=list(selection.match_reasons),
            eligibility="eligible" if prerequisite_ok else "ineligible",
            prerequisite_status="satisfied" if prerequisite_ok else "missing",
            policy_status="pending",
            version=skill.version,
        )
        policy_result = self.policy.evaluate([match], request)
        if policy_result.rejected:
            return policy_result.rejected[0].reason_codes
        return []

    def _resolve_handler(
        self, skill: SkillDefinition
    ) -> RuntimeHandlerDescriptor | None:
        candidates: list[str] = []
        candidates.extend(f"tool.{item}" for item in skill.eligible_tools)
        for worker in skill.eligible_workers:
            target = self._WORKER_TARGETS.get(worker)
            if worker in self.available_workers:
                candidates.append("agent.internal")
            if target:
                candidates.append(f"subagent.{target}")
        for capability in skill.capability_ids:
            candidates.extend(
                f"tool.{tool_id}"
                for tool_id in self._CAPABILITY_TO_TOOLS.get(capability, ())
            )
        for handler_id in dict.fromkeys(candidates):
            try:
                descriptor = self.runtime_handlers.descriptor(handler_id)
            except RuntimeHandlerRegistryError:
                continue
            if descriptor.enabled:
                return descriptor
        return None

    def _execution_descriptor(
        self,
        skill: SkillDefinition,
        handler: RuntimeHandlerDescriptor,
    ) -> SkillExecutionDescriptor:
        target_id, operation = self._target_and_operation(skill, handler)
        binding_id = "skill-binding:" + hashlib.sha256(
            f"{skill.skill_id}@{skill.version}:{handler.handler_id}:{operation}".encode()
        ).hexdigest()[:24]
        return SkillExecutionDescriptor(
            binding_id=binding_id,
            skill_id=skill.skill_id,
            version=skill.version,
            handler_id=handler.handler_id,
            operation=operation,
            target_id=target_id,
            handler_kind=handler.kind,
            risk_level=handler.risk_level,
            requires_approval=handler.requires_approval,
            side_effecting=handler.side_effecting,
            replay_safe=handler.replay_safe,
            max_timeout_ms=handler.max_timeout_ms,
        )

    def _target_and_operation(
        self,
        skill: SkillDefinition,
        handler: RuntimeHandlerDescriptor,
    ) -> tuple[str, str]:
        if handler.handler_id.startswith("tool."):
            tool_id = handler.handler_id.removeprefix("tool.")
            return tool_id, f"{tool_id}.execute"
        worker = next(
            (
                item
                for item in skill.eligible_workers
                if item in self._WORKER_TARGETS
            ),
            "",
        )
        target = self._WORKER_TARGETS.get(worker, "")
        return target, f"{worker or handler.handler_id}.execute"


__all__ = [
    "SkillBindingError",
    "SkillBindingRejection",
    "SkillBindingResult",
    "SkillBindingService",
]
