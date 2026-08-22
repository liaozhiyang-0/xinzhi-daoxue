from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from time import perf_counter
from typing import Literal

from app.contracts import AgentRequest, RouteDecision
from app.contracts.intent import IntentExecutionPlan
from app.contracts.planner import (
    CanonicalPlan,
    PlannerLineage,
    PlannerPlanShape,
    PlannerRouteProjection,
    PlannerSnapshot,
)
from app.core.config import Settings
from app.services.canonical_plan_adapter import CanonicalPlanAdapter
from app.services.intent_plan import IntentPlanCompiler


@dataclass(frozen=True, slots=True)
class PlannerOutput:
    snapshot: PlannerSnapshot
    route: RouteDecision
    canonical_plan: CanonicalPlan


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

    def __init__(self, plan_compiler: IntentPlanCompiler | None = None) -> None:
        self.plan_compiler = plan_compiler or IntentPlanCompiler()
        self.goal_interpreter = GoalInterpreter()
        self.candidate_builder = CandidateBuilder()
        self.plan_compiler_boundary = PlannerPlanCompiler()

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
            selected_skills=list(plan.selected_skills),
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
            current_plan_shape=current_shape,
            planner_plan_shape=planner_shape,
            route_match=current_route == planner_route,
            plan_match=self._shape_matches(current_shape, planner_shape),
            planner_confidence=route.route_confidence,
            planner_reason_codes=["deterministic_route_reused"],
            latency_ms=max(0, int((perf_counter() - started) * 1000)),
        )
        return PlannerOutput(
            snapshot=snapshot,
            route=route,
            canonical_plan=canonical_plan,
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
        return settings.planner_shadow_enabled

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
