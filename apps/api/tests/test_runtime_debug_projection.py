from __future__ import annotations

from app.api.v1.debug_execution import _order_runtime_nodes
from app.models import AgentRunNodeModel
from app.runtime import AgentRun, AgentRunPlan, RuntimeNode


def _node(node_id: str) -> AgentRunNodeModel:
    return AgentRunNodeModel(
        run_id="runtime-debug-order",
        node_id=node_id,
        node_type="tool",
        handler_id=f"{node_id}.handler",
    )


def test_debug_projection_preserves_declared_runtime_plan_order() -> None:
    run = AgentRun(
        run_id="runtime-debug-order",
        task_id="task-debug-order",
        goal="render a declared plan in order",
        plan=AgentRunPlan(
            plan_id="plan-debug-order",
            goal="render a declared plan in order",
            nodes=[
                RuntimeNode(
                    node_id="step.10",
                    node_type="tool",
                    handler_id="tool.tenth",
                ),
                RuntimeNode(
                    node_id="step.2",
                    node_type="tool",
                    handler_id="tool.second",
                ),
            ],
        ),
    )

    ordered = _order_runtime_nodes(
        [_node("legacy.unknown"), _node("step.2"), _node("step.10")],
        run,
    )

    assert [node.node_id for node in ordered] == [
        "step.10",
        "step.2",
        "legacy.unknown",
    ]
