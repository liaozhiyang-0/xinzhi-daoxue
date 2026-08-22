from __future__ import annotations

from typing import Any, Literal, cast

from app.contracts import AgentExecutionPlan, RouteDecision
from app.contracts.intent import IntentExecutionPlan
from app.contracts.planner import (
    CanonicalGoal,
    CanonicalPlan,
    CanonicalPlanNode,
    PlannerBudget,
)
from app.runtime import AgentRunPlan, RuntimeGoal, RuntimeNode


class CanonicalPlanAdapter:
    """Translate existing plan dialects without changing Runtime behavior."""

    VERSION = "canonical-v1"

    @classmethod
    def from_intent_plan(
        cls,
        plan: IntentExecutionPlan,
        route: RouteDecision,
        *,
        task_family: str = "",
    ) -> CanonicalPlan:
        goal = CanonicalGoal(
            objective=plan.goal,
            task_family=task_family,
            course=route.course_id,
            intent=route.intent,
            constraints={
                "route_mode": plan.mode,
                "fallback_targets": list(plan.fallback_targets),
            },
            context_requirements=["routing_context", "session_continuity"],
        )
        return CanonicalPlan(
            plan_id=f"canonical:{plan.plan_id}",
            version=cls.VERSION,
            goal=goal,
            nodes=[
                CanonicalPlanNode(
                    node_id=node.node_id,
                    node_type=node.node_type,
                    target_id=node.target_id,
                    depends_on=list(node.depends_on),
                    parallel_group=node.parallel_group,
                    timeout_ms=node.timeout_ms,
                    max_retries=node.max_retries,
                    optional=node.optional,
                )
                for node in plan.nodes
            ],
            capabilities=list(plan.capabilities),
            selected_agents=[
                node.target_id for node in plan.nodes if node.node_type == "agent"
            ],
            selected_skills=list(plan.selected_skills),
            selected_tools=list(plan.selected_tools),
            success_criteria=list(plan.success_criteria),
            budget=PlannerBudget(max_parallelism=plan.max_parallelism),
            confidence=plan.confidence,
            source="intent_plan_adapter",
        )

    @classmethod
    def from_runtime_goal(
        cls,
        goal: RuntimeGoal,
        *,
        plan_id: str,
        version: str = VERSION,
    ) -> CanonicalPlan:
        nodes: list[CanonicalPlanNode] = []
        previous_ids: list[str] = []
        phases = _goal_phases(goal)
        step = 0
        for phase_index, phase in enumerate(phases, start=1):
            phase_node_ids: list[str] = []
            for capability in phase:
                step += 1
                node_id = f"goal.step.{step}.{_safe_id(capability)}"
                nodes.append(
                    CanonicalPlanNode(
                        node_id=node_id,
                        node_type="tool",
                        target_id=capability,
                        depends_on=list(previous_ids),
                        parallel_group=(
                            f"goal.phase.{phase_index}" if len(phase) > 1 else ""
                        ),
                    )
                )
                phase_node_ids.append(node_id)
            previous_ids.extend(phase_node_ids)
        return CanonicalPlan(
            plan_id=plan_id,
            version=version,
            goal=CanonicalGoal(
                objective=goal.objective,
                constraints=dict(goal.constraints),
                context_requirements=list(goal.required_capabilities),
            ),
            nodes=nodes,
            capabilities=list(goal.required_capabilities),
            success_criteria=list(goal.success_criteria),
            budget=PlannerBudget(
                max_parallelism=max((len(phase) for phase in phases), default=1)
            ),
            source="runtime_goal_adapter",
        )

    @classmethod
    def from_agent_run_plan(cls, plan: AgentRunPlan) -> CanonicalPlan:
        goal = plan.goal_contract or RuntimeGoal(
            objective=plan.goal,
            success_criteria=list(plan.success_criteria),
        )
        return CanonicalPlan(
            plan_id=f"canonical:{plan.plan_id}",
            version=cls.VERSION,
            goal=CanonicalGoal(
                objective=goal.objective,
                constraints=dict(goal.constraints),
                context_requirements=list(goal.required_capabilities),
            ),
            nodes=[
                CanonicalPlanNode(
                    node_id=node.node_id,
                    node_type=cast(
                        Literal[
                            "agent",
                            "tool",
                            "skill",
                            "retrieval",
                            "verifier",
                            "compose",
                        ],
                        _canonical_node_type(node.node_type),
                    ),
                    target_id=node.target_id or node.handler_id,
                    depends_on=list(node.depends_on),
                    parallel_group=node.parallel_group,
                    timeout_ms=node.timeout_ms,
                    max_retries=node.max_retries,
                    optional=node.optional,
                )
                for node in plan.nodes
            ],
            capabilities=list(goal.required_capabilities),
            success_criteria=list(plan.success_criteria),
            budget=PlannerBudget(max_parallelism=plan.max_parallelism),
            source="runtime_plan_adapter",
        )

    @staticmethod
    def execution_policy(plan: AgentExecutionPlan) -> dict[str, Any]:
        """Keep AgentExecutionPlan as policy, not canonical goal semantics."""

        return {
            "agent_id": plan.agent_id,
            "provider_type": plan.provider_type,
            "input_mode": plan.input_mode,
            "use_rag": plan.use_rag,
            "retrieval_policy_name": plan.retrieval_policy_name,
            "retrieval_mode": plan.retrieval_mode,
            "use_images": plan.use_images,
            "reranker_mode": plan.reranker_mode,
            "context_budget": plan.context_budget,
            "cloud_timeout_seconds": plan.cloud_timeout_seconds,
            "max_retries": plan.max_retries,
        }

    @staticmethod
    def to_intent_plan(
        plan: CanonicalPlan, *, plan_id: str | None = None
    ) -> IntentExecutionPlan:
        from app.contracts.intent import PlanNode

        mode = str(plan.goal.constraints.get("route_mode", "single_agent"))
        safe_mode = (
            mode
            if mode in {"fast", "single_agent", "workflow", "clarify"}
            else "single_agent"
        )
        return IntentExecutionPlan(
            plan_id=plan_id or plan.plan_id.removeprefix("canonical:"),
            version=plan.version,
            mode=cast(
                Literal["fast", "single_agent", "workflow", "clarify"],
                safe_mode,
            ),
            goal=plan.goal.objective,
            nodes=[
                PlanNode(
                    node_id=node.node_id,
                    node_type=node.node_type,
                    target_id=node.target_id,
                    depends_on=list(node.depends_on),
                    parallel_group=node.parallel_group,
                    timeout_ms=node.timeout_ms,
                    max_retries=node.max_retries,
                    optional=node.optional,
                )
                for node in plan.nodes
            ],
            capabilities=list(plan.capabilities),
            selected_tools=list(plan.selected_tools),
            selected_skills=list(plan.selected_skills),
            success_criteria=list(plan.success_criteria),
            max_parallelism=plan.budget.max_parallelism,
            confidence=plan.confidence,
        )

    @staticmethod
    def to_runtime_plan(
        plan: CanonicalPlan,
        *,
        handler_prefix: str = "workflow",
    ) -> AgentRunPlan:
        goal = RuntimeGoal(
            objective=plan.goal.objective or "runtime task",
            success_criteria=list(plan.success_criteria),
            constraints=dict(plan.goal.constraints),
            required_capabilities=list(plan.capabilities)
            or [node.target_id for node in plan.nodes],
            context={
                "canonical_plan_version": plan.version,
                "canonical_plan_source": plan.source,
            },
            source="canonical_plan",
        )
        return AgentRunPlan(
            plan_id=plan.plan_id,
            version=plan.version,
            goal=goal.objective,
            goal_contract=goal,
            nodes=[
                RuntimeNode(
                    node_id=node.node_id,
                    node_type=node.node_type,
                    handler_id=f"{handler_prefix}.{node.target_id}",
                    target_id=node.target_id,
                    depends_on=list(node.depends_on),
                    parallel_group=node.parallel_group,
                    timeout_ms=node.timeout_ms,
                    max_retries=node.max_retries,
                    optional=node.optional,
                )
                for node in plan.nodes
            ],
            success_criteria=list(plan.success_criteria),
            max_parallelism=plan.budget.max_parallelism,
        )


def _safe_id(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in "_-" else "-" for char in value
    )[:80]


def _goal_phases(goal: RuntimeGoal) -> list[list[str]]:
    required = [item.strip() for item in goal.required_capabilities]
    if not goal.parallel_groups:
        return [[item] for item in required]
    required_by_key = {item.casefold(): item for item in required}
    seen: set[str] = set()
    phases: list[list[str]] = []
    for group in goal.parallel_groups:
        phase: list[str] = []
        for item in group:
            key = item.strip().casefold()
            capability = required_by_key.get(key)
            if capability is not None and key not in seen:
                phase.append(capability)
                seen.add(key)
        if phase:
            phases.append(phase)
    phases.extend(
        [[capability] for capability in required if capability.casefold() not in seen]
    )
    return phases


def _canonical_node_type(value: str) -> str:
    return (
        value
        if value in {"agent", "tool", "skill", "retrieval", "verifier", "compose"}
        else "tool"
    )
