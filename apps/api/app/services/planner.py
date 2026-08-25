from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from time import perf_counter
from typing import Literal

from app.contracts import (
    AgentRequest,
    GoalContract,
    RouteDecision,
)
from app.contracts.experience import ExperienceInfluence, ExperienceRetrievalQuery
from app.contracts.intent import IntentExecutionPlan
from app.contracts.planner import (
    CanonicalGoal,
    CanonicalPlan,
    CanonicalPlanNode,
    CapabilityBinding,
    PlannerLineage,
    PlannerPlanShape,
    PlannerRouteProjection,
    PlannerSkillSelection,
    PlannerSnapshot,
)
from app.core.config import Settings
from app.observability.architecture_telemetry import architecture_telemetry
from app.runtime.handler_registry import RuntimeHandlerRegistryError
from app.services.canonical_plan_adapter import CanonicalPlanAdapter
from app.services.capability_binding_registry import (
    CapabilityBindingRegistry,
    default_capability_binding_registry,
)
from app.services.circuit_visualization import (
    CircuitVisualizationDecision,
    decide_circuit_visualization,
)
from app.services.experience_memory import ExperiencePlannerPrior
from app.services.intent_plan import IntentPlanCompiler
from app.services.production_execution_manifest import ProductionExecutionManifest
from app.services.skill_binding import SkillBindingService
from app.services.skill_policy import SkillPolicy
from app.services.skill_registry import SkillMatch, SkillRegistry
from app.services.skill_retriever import SkillRetrievalRequest, SkillRetriever


@dataclass(frozen=True, slots=True)
class PlannerOutput:
    snapshot: PlannerSnapshot
    route: RouteDecision
    canonical_plan: CanonicalPlan


@dataclass(frozen=True, slots=True)
class PlannerExperienceShadow:
    """Baseline Planner output plus a non-executing Experience shadow."""

    baseline: PlannerOutput
    influence: ExperienceInfluence


class GoalInterpreter:
    """Normalize the existing request/route facts into a Planner goal."""

    @staticmethod
    def interpret(
        request: AgentRequest,
        route: RouteDecision,
        plan: IntentExecutionPlan,
    ) -> str:
        return plan.goal or request.input_text()


class CandidateBuilder:
    """Expose candidate capabilities without invoking a provider or tool."""

    @staticmethod
    def build(
        route: RouteDecision,
        plan: IntentExecutionPlan,
        canonical_plan: CanonicalPlan,
    ) -> list[str]:
        return list(
            dict.fromkeys(
                [
                    *route.capabilities,
                    *plan.capabilities,
                    *[node.target_id for node in canonical_plan.nodes],
                ]
            )
        )


class PlannerPlanCompiler:
    """Compile one canonical plan; Runtime adapters remain downstream."""

    @staticmethod
    def compile(
        plan: IntentExecutionPlan,
        route: RouteDecision,
    ) -> CanonicalPlan:
        return CanonicalPlanAdapter.from_intent_plan(
            plan,
            route,
            task_family=str(route.intent_recognition.get("task_family", "")),
        )


class PlannerService:
    """Provider-free Planner boundary used for shadow and guarded takeover.

    The first implementation deliberately compiles the existing deterministic
    route into the new contract. This establishes ownership and lineage without
    silently introducing a second model route or changing business behavior.
    """

    VERSION = "planner-v1"

    def __init__(
        self,
        plan_compiler: IntentPlanCompiler | None = None,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self.plan_compiler = plan_compiler or IntentPlanCompiler()
        self.goal_interpreter = GoalInterpreter()
        self.candidate_builder = CandidateBuilder()
        self.plan_compiler_boundary = PlannerPlanCompiler()
        self.skill_registry = skill_registry
        self.capability_bindings: CapabilityBindingRegistry = (
            default_capability_binding_registry()
        )
        self.skill_binding_service: SkillBindingService | None = None
        self.manifest: ProductionExecutionManifest | None = None

    def bind_manifest(self, manifest: ProductionExecutionManifest) -> None:
        manifest.validate_bootstrap()
        self.manifest = manifest

    def configure_skill_registry(self, registry: SkillRegistry) -> None:
        """Bind the composition-root registry; never create a second one."""

        self.skill_registry = registry

    def configure_skill_binding_service(
        self, service: SkillBindingService
    ) -> None:
        self.skill_binding_service = service

    def build_authoritative(
        self,
        request: AgentRequest,
        goal: GoalContract,
        route: RouteDecision,
        *,
        settings: Settings,
        mode: Literal["controlled", "active"],
    ) -> PlannerOutput:
        """Build a CanonicalPlan from GoalContract facts, not an old plan.

        The deterministic route is still accepted as a preflight capability
        candidate during migration, but it is not compiled into the plan.
        Registry validation and skill policy remain provider-free and bounded.
        """

        if mode not in {"controlled", "active"}:
            raise ValueError(f"authoritative planner mode invalid: {mode}")
        started = perf_counter()
        capabilities = self._registered_capabilities(
            [
                *self._string_list(goal.constraints.get("capabilities")),
                *route.capabilities,
                *self._string_list(
                    route.intent_recognition.get("capabilities")
                ),
            ]
        )
        if not capabilities:
            capabilities = [
                binding.capability_id
                for binding in self.capability_bindings.list()
                if binding.handler_id == route.agent_id
            ]
        if not capabilities:
            raise ValueError("planner produced no registered capability")
        capabilities = list(
            dict.fromkeys(
                self._canonical_capability(item, route)
                for item in capabilities
            )
        )
        skills, skill_status, skill_rejections = self._select_goal_skills(
            request, goal, route, capabilities
        )
        selected_tools = list(
            dict.fromkeys(
                [
                    *route.selected_tools,
                    *self._string_list(route.intent_recognition.get("selected_tools")),
                ]
            )
        )
        bindings = [
            self.capability_bindings.get(item)
            for item in capabilities
            if item
            in {
                binding.capability_id
                for binding in self.capability_bindings.list()
            }
        ]
        primary_capability_binding = next(
            (
                binding
                for binding in bindings
                if binding.capability_id == capabilities[0]
            ),
            None,
        )
        primary_timeout_ms = self._handler_timeout_ms(
            primary_capability_binding.handler_id
            if primary_capability_binding is not None
            else ""
        )
        node = CanonicalPlanNode(
            node_id="planner.capability.primary",
            node_type="agent",
            target_id=capabilities[0],
            timeout_ms=primary_timeout_ms,
        )
        canonical = CanonicalPlan(
            plan_id=(
                f"planner:{self._digest({'goal_id': goal.goal_id, 'mode': mode})[:32]}"
            ),
            version="canonical-v1",
            goal=CanonicalGoal(
                objective=goal.normalized_goal,
                task_family=goal.task_family_hint,
                course=goal.course_context,
                intent=route.intent,
                constraints=dict(goal.constraints),
                context_requirements=list(goal.evidence_requirements),
            ),
            nodes=[node],
            capabilities=capabilities,
            capability_bindings=[
                CapabilityBinding(
                    capability_id=item.capability_id,
                    handler_id=item.handler_id,
                    skill_ids=list(item.skill_ids),
                )
                for item in bindings
            ],
            selected_agents=[route.agent_id],
            selected_skills=[item.skill_id for item in skills],
            skill_selection=skills,
            skill_selection_status=skill_status,
            selected_tools=selected_tools,
            success_criteria=list(
                dict.fromkeys(
                    [
                        *goal.desired_output,
                        *goal.evidence_requirements,
                        "verification_boundary",
                    ]
                )
            ),
            budget=goal.budget,
            confidence=route.route_confidence,
            source="planner_authoritative",
        )
        if self.skill_binding_service is not None and canonical.selected_skills:
            canonical = self.skill_binding_service.bind_plan(canonical)
            if canonical.skill_bindings:
                primary_binding = canonical.skill_bindings[0]
                canonical = canonical.model_copy(
                    update={
                        "nodes": [
                            CanonicalPlanNode(
                                node_id="planner.skill.primary",
                                node_type="skill",
                                target_id=primary_binding.skill_id,
                                timeout_ms=min(
                                    300_000, primary_binding.max_timeout_ms
                                ),
                            )
                        ]
                    }
                    )
        canonical, circuit_decision = self._append_circuit_visualization(
            request, route, settings, canonical
        )
        if self.manifest is not None:
            self.manifest.validate_canonical_plan(
                canonical,
                caller="PlannerService.build_authoritative",
            )
        shape = self._canonical_plan_shape(canonical)
        projection = self._route_projection(route)
        lineage = PlannerLineage(
            task_id=request.task_id,
            request_id=str(request.options.get("request_id", "")),
            trace_id=str(request.options.get("trace_id", "")),
            route_revision=route.route_revision,
            current_plan_id="",
            current_plan_version="",
            context_snapshot_id=self._context_snapshot_id(request),
            registry_snapshot_id=self._registry_snapshot_id(request, route),
            source="goal_contract",
        )
        snapshot = PlannerSnapshot(
            planner_version=self.VERSION,
            mode=mode,
            status="completed",
            goal=goal.normalized_goal,
            objective=goal.normalized_goal,
            task_family=goal.task_family_hint,
            course=goal.course_context,
            intent=route.intent,
            candidate_capabilities=capabilities,
            selected_capability=capabilities[0],
            selected_agents=[route.agent_id],
            selected_skills=list(canonical.selected_skills),
            selected_tools=selected_tools,
            success_criteria=list(canonical.success_criteria),
            constraints=dict(goal.constraints),
            budget=goal.budget,
            context_requirements=list(goal.evidence_requirements),
            canonical_plan=canonical,
            confidence=route.route_confidence,
            reason_codes=["goal_contract", "registered_capability", "canonical_plan"],
            lineage=lineage,
            current_route=projection,
            planner_route=projection,
            current_intent=route.intent,
            planner_intent=route.intent,
            current_capability=route.agent_id,
            planner_capability=capabilities[0],
            current_tools=list(route.selected_tools),
            planner_tools=selected_tools,
            current_skills=list(route.selected_skills),
            planner_skills=list(canonical.selected_skills),
            planner_skill_selection=skills,
            skill_selection_status=skill_status,
            skill_rejection_reasons=skill_rejections,
            current_plan_shape=PlannerPlanShape(fingerprint=self._digest({})),
            planner_plan_shape=shape,
            route_match=True,
            plan_match=False,
            planner_confidence=route.route_confidence,
            planner_reason_codes=["goal_contract_authority"],
            latency_ms=max(0, int((perf_counter() - started) * 1000)),
            circuit_visualization=circuit_decision.model_dump(mode="json"),
        )
        architecture_telemetry.increment(f"planner_{mode}_count")
        return PlannerOutput(snapshot=snapshot, route=route, canonical_plan=canonical)

    def _handler_timeout_ms(self, handler_id: str) -> int:
        """Keep canonical node timeout within the registered handler policy."""

        if not handler_id or self.skill_binding_service is None:
            return 300_000
        try:
            descriptor = self.skill_binding_service.runtime_handlers.descriptor(
                f"subagent.{handler_id}"
            )
        except RuntimeHandlerRegistryError:
            return 300_000
        return min(300_000, descriptor.max_timeout_ms)

    def _registered_capabilities(self, values: list[str]) -> list[str]:
        candidates = list(
            dict.fromkeys(item.strip() for item in values if item.strip())
        )
        registry = getattr(self.skill_registry, "capability_registry", None)
        if registry is None:
            return candidates
        registered = {item.capability_id for item in registry.list_capabilities()}
        return [item for item in candidates if item in registered]

    def _canonical_capability(
        self, capability_id: str, route: RouteDecision
    ) -> str:
        # ``general_answer`` is a historical recognition label shared by
        # several routes. Resolve only the two known semantic aliases; an
        # ordinary general question must remain a general-answer capability.
        if capability_id == "general_answer":
            if route.intent in {"learning_advice"}:
                return "learning.path_plan"
            if route.intent in {"summarize_knowledge"}:
                return "knowledge.govern"
            return "general_answer"
        return self.capability_bindings.canonicalize(capability_id)

    def _select_goal_skills(
        self,
        request: AgentRequest,
        goal: GoalContract,
        route: RouteDecision,
        capabilities: list[str],
    ) -> tuple[
        list[PlannerSkillSelection],
        Literal["selected", "empty", "rejected", "unavailable"],
        list[str],
    ]:
        if self.skill_registry is None:
            return [], "unavailable", ["skill_registry_unavailable"]
        retrieval = SkillRetrievalRequest(
            goal=CanonicalGoal(
                objective=goal.normalized_goal,
                task_family=goal.task_family_hint,
                course=goal.course_context,
                intent=route.intent,
                constraints=dict(goal.constraints),
                context_requirements=list(goal.evidence_requirements),
            ),
            course=goal.course_context,
            intent=route.intent,
            problem_type=str(route.intent_recognition.get("problem_type", "")),
            capabilities=capabilities,
            context_summary=goal.normalized_goal,
            evidence_state=self._mapping_value(
                goal.constraints.get("evidence_state")
            ),
            learner_state={},
            available_workers=self._available_skill_workers(),
            available_tools=self._available_skill_tools(route),
            available_skill_ids=list(route.selected_skills),
            requested_skill_ids=[],
            role=goal.user_role.value,
            budget=goal.budget,
            max_risk=goal.risk_level,
        )
        retriever = SkillRetriever(self.skill_registry)
        policy = SkillPolicy(self.skill_registry)
        matches = retriever.retrieve(retrieval, top_k=3)
        policy_result = policy.evaluate(matches, retrieval)
        approved = list(policy_result.approved)
        rejected = list(policy_result.rejected)
        selected = [
            PlannerSkillSelection(
                skill_id=item.skill_id,
                version=item.version,
                score=item.score,
                status="selected",
                match_reasons=list(item.match_reasons),
            )
            for item in approved
        ]
        selected_ids = {item.skill_id for item in selected}
        for capability in capabilities:
            try:
                binding = self.capability_bindings.get(capability)
            except KeyError:
                continue
            for skill_id in binding.skill_ids:
                if skill_id in selected_ids:
                    continue
                try:
                    definition = self.skill_registry.resolve(skill_id)
                except (KeyError, ValueError):
                    continue
                match = SkillMatch(
                    skill_id=definition.skill_id,
                    version=definition.version,
                    score=100.0,
                    match_reasons=["capability_binding"],
                    eligibility=(
                        "eligible"
                        if self._prerequisites_satisfied(definition.skill_id, route)
                        else "ineligible"
                    ),
                    prerequisite_status=(
                        "satisfied"
                        if self._prerequisites_satisfied(definition.skill_id, route)
                        else "missing"
                    ),
                    policy_status="pending",
                )
                decision = policy.evaluate([match], retrieval)
                if decision.approved:
                    approved_match = decision.approved[0]
                    selected.append(
                        PlannerSkillSelection(
                            skill_id=approved_match.skill_id,
                            version=approved_match.version,
                            score=approved_match.score,
                            status="selected",
                            match_reasons=list(approved_match.match_reasons),
                        )
                    )
                    selected_ids.add(skill_id)
                else:
                    rejected.extend(decision.rejected)
        rejection_reasons = [
            reason
            for item in rejected
            for reason in item.reason_codes
        ]
        return (
            selected,
            ("selected" if selected else "rejected" if rejection_reasons else "empty"),
            list(dict.fromkeys(rejection_reasons)),
        )

    def _available_skill_workers(self) -> list[str]:
        if self.skill_binding_service is None:
            return []
        return list(self.skill_binding_service.available_workers)

    def _available_skill_tools(self, route: RouteDecision) -> list[str]:
        values = list(route.selected_tools)
        if self.skill_binding_service is not None:
            descriptors = self.skill_binding_service.runtime_handlers.descriptors()
            values.extend(
                descriptor.handler_id.removeprefix("tool.")
                for descriptor in descriptors
                if descriptor.enabled and descriptor.kind == "tool"
            )
        return list(dict.fromkeys(values))

    @staticmethod
    def _mapping_value(value: object) -> dict[str, object]:
        return dict(value) if isinstance(value, dict) else {}

    def _prerequisites_satisfied(
        self, skill_id: str, route: RouteDecision
    ) -> bool:
        if self.skill_registry is None:
            return False
        available = list(route.selected_skills)
        satisfied, _ = self.skill_registry.validate_prerequisites(
            skill_id,
            available_skill_ids=available,
        )
        return satisfied

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def build(
        self,
        request: AgentRequest,
        route: RouteDecision,
        *,
        settings: Settings,
        intent_plan: IntentExecutionPlan | None = None,
        mode: Literal["shadow", "takeover"] = "shadow",
    ) -> PlannerOutput:
        started = perf_counter()
        plan = intent_plan or self.plan_compiler.compile(request, route)
        task_family = str(route.intent_recognition.get("task_family", ""))
        canonical_plan = self.plan_compiler_boundary.compile(plan, route)
        objective = self.goal_interpreter.interpret(request, route, plan)
        canonical_plan, skill_selection, skill_status, skill_rejections = (
            self._select_skills(request, route, plan, canonical_plan, objective)
        )
        canonical_plan, circuit_decision = self._append_circuit_visualization(
            request, route, settings, canonical_plan
        )
        current_route = self._route_projection(route)
        planner_route = current_route.model_copy()
        current_shape = self._intent_plan_shape(plan)
        planner_shape = self._canonical_plan_shape(canonical_plan)
        context_snapshot_id = self._context_snapshot_id(request)
        registry_snapshot_id = self._registry_snapshot_id(request, route)
        lineage = PlannerLineage(
            task_id=request.task_id,
            request_id=str(request.options.get("request_id", "")),
            trace_id=str(request.options.get("trace_id", "")),
            route_revision=route.route_revision,
            current_plan_id=plan.plan_id,
            current_plan_version=plan.version,
            context_snapshot_id=context_snapshot_id,
            registry_snapshot_id=registry_snapshot_id,
        )
        planner_enabled = self.takeover_allowed(request, settings)
        effective_mode: Literal["shadow", "takeover"] = (
            "takeover" if mode == "takeover" and planner_enabled else "shadow"
        )
        architecture_telemetry.increment(
            {
                "shadow": "planner_shadow_count",
                "takeover": "planner_controlled_count",
            }[effective_mode]
        )
        snapshot = PlannerSnapshot(
            planner_version=self.VERSION,
            mode=effective_mode,
            status="completed",
            goal=objective,
            objective=objective,
            task_family=task_family,
            course=route.course_id,
            intent=route.intent,
            candidate_capabilities=self.candidate_builder.build(
                route, plan, canonical_plan
            ),
            selected_capability=route.agent_id,
            selected_agents=list(canonical_plan.selected_agents),
            selected_skills=list(canonical_plan.selected_skills),
            selected_tools=list(plan.selected_tools),
            success_criteria=list(canonical_plan.success_criteria),
            constraints=dict(canonical_plan.goal.constraints),
            budget=canonical_plan.budget,
            context_requirements=list(canonical_plan.goal.context_requirements),
            canonical_plan=canonical_plan,
            confidence=route.route_confidence,
            reason_codes=["legacy_route_adapter", "deterministic_shadow"],
            lineage=lineage,
            current_route=current_route,
            planner_route=planner_route,
            current_intent=route.intent,
            planner_intent=route.intent,
            current_capability=route.agent_id,
            planner_capability=route.agent_id,
            current_tools=list(plan.selected_tools),
            planner_tools=list(canonical_plan.selected_tools),
            current_skills=list(plan.selected_skills),
            planner_skills=list(canonical_plan.selected_skills),
            planner_skill_selection=skill_selection,
            skill_selection_status=skill_status,
            skill_rejection_reasons=skill_rejections,
            current_plan_shape=current_shape,
            planner_plan_shape=planner_shape,
            route_match=current_route == planner_route,
            plan_match=self._shape_matches(current_shape, planner_shape),
            planner_confidence=route.route_confidence,
            planner_reason_codes=["deterministic_route_reused"],
            latency_ms=max(0, int((perf_counter() - started) * 1000)),
            circuit_visualization=circuit_decision.model_dump(mode="json"),
        )
        return PlannerOutput(
            snapshot=snapshot,
            route=route,
            canonical_plan=canonical_plan,
        )

    @staticmethod
    def _append_circuit_visualization(
        request: AgentRequest,
        route: RouteDecision,
        settings: Settings,
        canonical: CanonicalPlan,
    ) -> tuple[CanonicalPlan, CircuitVisualizationDecision]:
        decision = decide_circuit_visualization(
            request,
            feature_mode=settings.circuit_visualization_mode,
            course_id=route.course_id,
        )
        updated = canonical.model_copy(
            update={"circuit_visualization": decision.model_dump(mode="json")}
        )
        if not decision.should_schedule:
            return updated, decision
        if any(node.node_id == "circuit.visualize" for node in updated.nodes):
            return updated, decision
        bindings = list(updated.capability_bindings)
        if not any(
            item.capability_id == "circuit.visualize" for item in bindings
        ):
            bindings.append(
                CapabilityBinding(
                    capability_id="circuit.visualize",
                    handler_id="tool.circuit.render",
                )
            )
        nodes = [*updated.nodes]
        nodes.append(
            CanonicalPlanNode(
                node_id="circuit.visualize",
                node_type="tool",
                target_id="circuit.visualize",
                input_ref="CircuitIR",
                depends_on=[node.node_id for node in updated.nodes],
                timeout_ms=10_000,
                optional=True,
                failure_policy="nonfatal",
            )
        )
        return (
            updated.model_copy(
                update={
                    "nodes": nodes,
                    "capabilities": list(
                        dict.fromkeys([*updated.capabilities, "circuit.visualize"])
                    ),
                    "capability_bindings": bindings,
                    "selected_tools": list(
                        dict.fromkeys([*updated.selected_tools, "circuit.render"])
                    ),
                }
            ),
            decision,
        )

    async def build_shadow_with_experience(
        self,
        request: AgentRequest,
        route: RouteDecision,
        *,
        settings: Settings,
        prior: ExperiencePlannerPrior,
        intent_plan: IntentExecutionPlan | None = None,
    ) -> PlannerExperienceShadow:
        """Compare a bounded experience prior without changing execution.

        The synchronous ``build`` remains the sole baseline planner path.
        This async companion is an explicit shadow seam for evaluation and
        keeps Task creation and Runtime execution provider-free.
        """

        baseline = self.build(
            request,
            route,
            settings=settings,
            intent_plan=intent_plan,
            mode="shadow",
        )
        snapshot = baseline.snapshot
        query = ExperienceRetrievalQuery(
            course_id=snapshot.course,
            capability_id=snapshot.selected_capability,
            problem_type=str(route.intent_recognition.get("problem_type", "")),
            selected_skill_ids=list(snapshot.selected_skills),
            selected_tool_ids=list(snapshot.selected_tools),
            risk_level=str(request.options.get("risk_level", "low")),
            planner_version=snapshot.planner_version,
            user_id=(
                str(request.options.get("user_id"))
                if request.options.get("user_id")
                else None
            ),
        )
        influence = await prior.shadow(
            snapshot.canonical_plan.model_dump(mode="json")
            if snapshot.canonical_plan is not None
            else {},
            query,
            preflight_result={
                "route_status": route.route_status.value,
                "route_source": route.route_source,
                "baseline_plan_id": baseline.canonical_plan.plan_id,
            },
        )
        return PlannerExperienceShadow(baseline=baseline, influence=influence)

    def _select_skills(
        self,
        request: AgentRequest,
        route: RouteDecision,
        plan: IntentExecutionPlan,
        canonical_plan: CanonicalPlan,
        objective: str,
    ) -> tuple[
        CanonicalPlan,
        list[PlannerSkillSelection],
        Literal["selected", "empty", "rejected", "unavailable"],
        list[str],
    ]:
        """Run bounded retrieval/policy in shadow metadata only."""

        if self.skill_registry is None:
            return canonical_plan, [], "unavailable", ["skill_registry_unavailable"]
        raw_evidence = request.options.get("evidence_state", {})
        evidence_state = raw_evidence if isinstance(raw_evidence, dict) else {}
        raw_workers = request.options.get("available_workers", [])
        raw_tools = request.options.get("available_tools", [])
        retrieval = SkillRetrievalRequest(
            goal=canonical_plan.goal,
            course=route.course_id,
            intent=route.intent,
            problem_type=str(route.intent_recognition.get("problem_type", "")),
            capabilities=list(
                dict.fromkeys([*route.capabilities, *plan.capabilities])
            ),
            context_summary=objective,
            evidence_state=evidence_state,
            learner_state=(
                request.options.get("learner_state", {})
                if isinstance(request.options.get("learner_state", {}), dict)
                else {}
            ),
            available_workers=[str(item) for item in raw_workers]
            if isinstance(raw_workers, list)
            else [],
            available_tools=[str(item) for item in raw_tools]
            if isinstance(raw_tools, list)
            else [],
            available_skill_ids=list(route.selected_skills),
            requested_skill_ids=[],
            role=str(request.options.get("role", "student")),
        )
        retriever = SkillRetriever(self.skill_registry)
        policy = SkillPolicy(self.skill_registry)
        matches = retriever.retrieve(retrieval, top_k=1)
        policy_result = policy.evaluate(matches, retrieval)
        selections = [
            PlannerSkillSelection(
                skill_id=item.skill_id,
                version=item.version,
                score=item.score,
                status="selected",
                match_reasons=list(item.match_reasons),
            )
            for item in policy_result.approved
        ]
        selections.extend(
            PlannerSkillSelection(
                skill_id=item.skill_id,
                version=item.version,
                score=0,
                status="rejected",
                reason_codes=list(item.reason_codes),
            )
            for item in policy_result.rejected
        )
        selected_ids = [item.skill_id for item in policy_result.approved]
        rejection_reasons = [
            reason
            for item in policy_result.rejected
            for reason in item.reason_codes
        ]
        status: Literal["selected", "empty", "rejected", "unavailable"]
        if selected_ids:
            status = "selected"
        elif policy_result.rejected:
            status = "rejected"
        else:
            status = "empty"
        canonical_plan = canonical_plan.model_copy(
            update={
                "selected_skills": selected_ids,
                "skill_selection": selections,
                "skill_selection_status": status,
            }
        )
        return (
            canonical_plan,
            selections,
            status,
            list(dict.fromkeys(rejection_reasons)),
        )

    def failed_snapshot(
        self,
        request: AgentRequest,
        route: RouteDecision,
        *,
        error_type: str,
    ) -> PlannerSnapshot:
        empty_shape = PlannerPlanShape(fingerprint=self._digest({}))
        projection = self._route_projection(route)
        raw_intent_plan = request.options.get("_intent_plan")
        intent_plan = raw_intent_plan if isinstance(raw_intent_plan, dict) else {}
        return PlannerSnapshot(
            planner_version=self.VERSION,
            mode="failed",
            status="failed",
            goal=request.input_text(),
            objective=request.input_text(),
            course=route.course_id,
            intent=route.intent,
            lineage=PlannerLineage(
                task_id=request.task_id,
                request_id=str(request.options.get("request_id", "")),
                trace_id=str(request.options.get("trace_id", "")),
                route_revision=route.route_revision,
                current_plan_id=str(intent_plan.get("plan_id", "")),
                current_plan_version=str(intent_plan.get("version", "")),
                context_snapshot_id=self._context_snapshot_id(request),
                registry_snapshot_id=self._registry_snapshot_id(request, route),
            ),
            current_route=projection,
            planner_route=projection,
            current_plan_shape=empty_shape,
            planner_plan_shape=empty_shape,
            route_match=False,
            plan_match=False,
            error_type=error_type,
            fallback_reason="planner_failure_legacy_path",
        )

    @staticmethod
    def shadow_enabled(settings: Settings) -> bool:
        return settings.planner_mode == "shadow" or settings.planner_shadow_enabled

    @staticmethod
    def production_mode(
        settings: Settings, request: AgentRequest | None = None
    ) -> Literal["shadow", "controlled", "active"]:
        configured = settings.planner_mode
        if configured in {"controlled", "active"}:
            return configured
        if request is not None and PlannerService.takeover_allowed(request, settings):
            return "controlled"
        return "shadow"

    @staticmethod
    def takeover_allowed(request: AgentRequest, settings: Settings) -> bool:
        if not settings.planner_takeover_enabled:
            return False
        allowed_agents = _csv(settings.planner_canary_agent_ids)
        allowed_scenarios = _csv(settings.planner_canary_scenario_ids)
        if not allowed_agents and not allowed_scenarios:
            return False
        routed_agent = str(
            request.options.get("_routing", {}).get("agent_id", "")
        )
        agent_allowed = (
            not allowed_agents
            or str(request.options.get("scenario_agent_id", "")) in allowed_agents
            or routed_agent in allowed_agents
        )
        scenario_allowed = (
            not allowed_scenarios or request.scenario_id in allowed_scenarios
        )
        return agent_allowed and scenario_allowed

    @staticmethod
    def takeover_route(route: RouteDecision) -> RouteDecision:
        """Mark the same preflighted route as Planner-owned for canary traces."""

        return route.model_copy(
            update={
                "route_source": "planner_takeover",
                "route_revision": route.route_revision + 1,
                "reason": "planner canary accepted the preflighted route",
                "reason_codes": [*route.reason_codes, "planner_takeover"],
                "route_trace": [
                    *route.route_trace,
                    {
                        "stage": "planner_takeover",
                        "source": "planner",
                        "agent_id": route.agent_id,
                    },
                ],
            }
        )

    @classmethod
    def _route_projection(cls, route: RouteDecision) -> PlannerRouteProjection:
        agent_id = route.agent_id
        course = route.course_id
        intent = route.intent
        route_status = route.route_status.value
        route_source = route.route_source
        route_revision = route.route_revision
        confidence = route.route_confidence
        capability = route.agent_id
        projection = {
            "agent_id": agent_id,
            "course": course,
            "intent": intent,
            "route_status": route_status,
            "route_source": route_source,
            "route_revision": route_revision,
            "confidence": confidence,
            "capability": capability,
        }
        return PlannerRouteProjection(
            agent_id=agent_id,
            course=course,
            intent=intent,
            route_status=route_status,
            route_source=route_source,
            route_revision=route_revision,
            confidence=confidence,
            capability=capability,
            fingerprint=cls._digest(projection),
        )

    @classmethod
    def _intent_plan_shape(cls, plan: IntentExecutionPlan) -> PlannerPlanShape:
        plan_id = plan.plan_id
        version = plan.version
        node_ids = [node.node_id for node in plan.nodes]
        target_ids = [node.target_id for node in plan.nodes]
        dependencies = {
            node.node_id: list(node.depends_on) for node in plan.nodes
        }
        payload = {
            "plan_id": plan_id,
            "version": version,
            "node_ids": node_ids,
            "target_ids": target_ids,
            "dependencies": dependencies,
        }
        return PlannerPlanShape(
            plan_id=plan_id,
            version=version,
            node_ids=node_ids,
            target_ids=target_ids,
            dependencies=dependencies,
            fingerprint=cls._digest(payload),
        )

    @classmethod
    def _canonical_plan_shape(cls, plan: CanonicalPlan) -> PlannerPlanShape:
        plan_id = plan.plan_id
        version = plan.version
        node_ids = [node.node_id for node in plan.nodes]
        target_ids = [node.target_id for node in plan.nodes]
        dependencies = {
            node.node_id: list(node.depends_on) for node in plan.nodes
        }
        payload = {
            "plan_id": plan_id,
            "version": version,
            "node_ids": node_ids,
            "target_ids": target_ids,
            "dependencies": dependencies,
        }
        return PlannerPlanShape(
            plan_id=plan_id,
            version=version,
            node_ids=node_ids,
            target_ids=target_ids,
            dependencies=dependencies,
            fingerprint=cls._digest(payload),
        )

    @staticmethod
    def _shape_matches(left: PlannerPlanShape, right: PlannerPlanShape) -> bool:
        return (
            left.node_ids == right.node_ids
            and left.target_ids == right.target_ids
            and left.dependencies == right.dependencies
        )

    @classmethod
    def _context_snapshot_id(cls, request: AgentRequest) -> str:
        options = request.options
        facts = {
            "course": request.course_id,
            "intent": request.intent.value,
            "context_keys": sorted(
                key
                for key in options
                if key
                in {
                    "active_course",
                    "previous_course",
                    "previous_agent",
                    "previous_intent",
                    "previous_task_id",
                    "conversation_summary",
                    "continuity_state",
                    "conversation_context",
                    "working_state",
                }
            ),
            "summary_length": len(str(options.get("conversation_summary", ""))),
        }
        return cls._digest(facts)

    @classmethod
    def _registry_snapshot_id(
        cls,
        request: AgentRequest,
        route: RouteDecision,
    ) -> str:
        facts = {
            "agent": route.agent_id,
            "candidates": [item.agent_id for item in route.candidate_agents],
            "skills": list(route.selected_skills),
            "tools": list(route.selected_tools),
            "available_agents": list(request.options.get("available_agents", [])),
        }
        return cls._digest(facts)

    @staticmethod
    def _digest(value: object) -> str:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]


def _csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}
