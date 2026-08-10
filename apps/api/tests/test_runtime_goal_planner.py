from __future__ import annotations

import pytest
from app.runtime import (
    RuntimeGoal,
    RuntimeGoalPlanner,
    RuntimeGoalPlannerError,
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeObservation,
)


def _registry() -> RuntimeHandlerRegistry:
    registry = RuntimeHandlerRegistry()
    registry.register(
        RuntimeHandlerDescriptor(
            handler_id="tool.calculator",
            kind="tool",
            max_timeout_ms=5_000,
        ),
        lambda _run, node: RuntimeObservation(node_id=node.node_id),
    )
    registry.register(
        RuntimeHandlerDescriptor(
            handler_id="tool.send_message",
            kind="tool",
            requires_approval=True,
            side_effecting=True,
            replay_safe=False,
            max_timeout_ms=10_000,
        ),
        lambda _run, node: RuntimeObservation(node_id=node.node_id),
    )
    return registry


def test_goal_planner_selects_registered_capabilities_and_dependencies() -> None:
    result = RuntimeGoalPlanner(_registry()).build(
        RuntimeGoal(
            objective="solve and report",
            success_criteria=["return a verified answer"],
            required_capabilities=["calculator", "tool.send_message"],
        ),
        plan_id="goal-plan-test",
    )

    assert [node.handler_id for node in result.plan.nodes] == [
        "tool.calculator",
        "tool.send_message",
    ]
    assert result.plan.nodes[1].depends_on == [
        "goal.step.1.calculator"
    ]
    assert result.requires_approval is True
    assert result.plan.goal_contract is not None
    assert result.plan.goal_contract.objective == "solve and report"


def test_goal_planner_fails_closed_for_unknown_capability() -> None:
    planner = RuntimeGoalPlanner(_registry())

    with pytest.raises(
        RuntimeGoalPlannerError,
        match="capability_not_registered:missing",
    ):
        planner.build(
            RuntimeGoal(
                objective="unknown",
                required_capabilities=["missing"],
            ),
            plan_id="unknown-plan",
        )


def test_goal_planner_reads_handlers_registered_after_construction() -> None:
    registry = RuntimeHandlerRegistry()
    planner = RuntimeGoalPlanner(registry)
    registry.register(
        RuntimeHandlerDescriptor(handler_id="tool.late", kind="tool"),
        lambda _run, node: RuntimeObservation(node_id=node.node_id),
    )

    plan = planner.build(
        RuntimeGoal(
            objective="use a late-registered capability",
            required_capabilities=["late"],
        ),
        plan_id="late-handler-goal",
    ).plan

    assert plan.nodes[0].handler_id == "tool.late"
