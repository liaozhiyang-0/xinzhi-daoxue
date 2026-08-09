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
    for handler_id in ("tool.search", "tool.calculate", "tool.report"):
        registry.register(
            RuntimeHandlerDescriptor(handler_id=handler_id, kind="tool"),
            lambda _run, node: RuntimeObservation(node_id=node.node_id),
        )
    return registry


def test_explicit_parallel_groups_compile_into_ordered_batches() -> None:
    result = RuntimeGoalPlanner(_registry()).build(
        RuntimeGoal(
            objective="research and report",
            required_capabilities=[
                "tool.search",
                "tool.calculate",
                "tool.report",
            ],
            parallel_groups=[
                ["tool.search", "tool.calculate"],
                ["tool.report"],
            ],
        ),
        plan_id="parallel-plan",
        max_parallelism=2,
    )

    search, calculate, report = result.plan.nodes
    assert search.parallel_group == "goal.phase.1"
    assert calculate.parallel_group == "goal.phase.1"
    assert search.depends_on == []
    assert calculate.depends_on == []
    assert report.depends_on == [search.node_id, calculate.node_id]


@pytest.mark.parametrize(
    ("groups", "message"),
    [
        ([[]], "parallel_group_empty"),
        ([["tool.search"]], "parallel_capability_missing"),
        (
            [["tool.search", "tool.search"], ["tool.calculate"]],
            "parallel_capability_duplicate",
        ),
        (
            [["tool.unknown"], ["tool.calculate"]],
            "parallel_capability_not_required",
        ),
    ],
)
def test_parallel_groups_fail_closed_for_ambiguous_goal_contract(
    groups: list[list[str]], message: str
) -> None:
    goal = RuntimeGoal(
        objective="bounded goal",
        required_capabilities=["tool.search", "tool.calculate"],
        parallel_groups=groups,
    )
    with pytest.raises(RuntimeGoalPlannerError, match=message):
        RuntimeGoalPlanner(_registry()).build(goal, plan_id="invalid-parallel-plan")
