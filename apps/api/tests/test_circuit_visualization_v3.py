from __future__ import annotations

from app.circuit import CircuitIR
from app.contracts import AgentRequest, AgentResult
from app.contracts.planner import (
    CanonicalGoal,
    CanonicalPlan,
    CanonicalPlanNode,
    CapabilityBinding,
)
from app.contracts.routing import RouteDecision, RouteStatus
from app.core.config import Settings
from app.runtime import AgentRun, AgentRunPlan, RuntimeNode
from app.services.canonical_plan_adapter import CanonicalPlanAdapter
from app.services.circuit_visualization import (
    decide_circuit_visualization,
    project_circuit_artifact,
    runtime_observation_from_tool,
)
from app.services.planner import PlannerService
from app.tools import default_tool_registry


def _request(*, text: str, circuit_ir: CircuitIR | None = None) -> AgentRequest:
    canonical_input: dict[str, object] = {"text": text}
    if circuit_ir is not None:
        canonical_input["circuit_ir"] = circuit_ir.model_dump(mode="json")
    return AgentRequest(
        session_id="session-v3",
        user_id="user-v3",
        canonical_input=canonical_input,
    )


def test_circuit_feature_mode_controls_shadow_and_runtime_schedule() -> None:
    circuit = CircuitIR()
    shadow = decide_circuit_visualization(
        _request(text="请画图", circuit_ir=circuit),
        feature_mode="shadow",
    )
    controlled = decide_circuit_visualization(
        _request(text="请画图", circuit_ir=circuit),
        feature_mode="controlled",
    )
    off = decide_circuit_visualization(
        _request(text="请画图", circuit_ir=circuit),
        feature_mode="off",
    )

    assert shadow.decision == "REQUIRED"
    assert not shadow.should_schedule
    assert controlled.should_schedule
    assert off.decision == "SKIP"


def test_canonical_plan_binds_circuit_visualization_to_tool() -> None:
    plan = CanonicalPlan(
        plan_id="canonical:v3",
        goal=CanonicalGoal(objective="draw"),
        nodes=[
            CanonicalPlanNode(
                node_id="circuit.visualize",
                node_type="tool",
                target_id="circuit.visualize",
                optional=True,
                failure_policy="nonfatal",
            )
        ],
        capabilities=["circuit.visualize"],
        capability_bindings=[
            CapabilityBinding(
                capability_id="circuit.visualize",
                handler_id="tool.circuit.render",
            )
        ],
    )

    runtime_plan = CanonicalPlanAdapter.to_runtime_plan(plan)
    node = runtime_plan.nodes[0]
    assert node.handler_id == "tool.circuit.render"
    assert node.target_id == "circuit.render"
    assert node.failure_policy == "nonfatal"


def test_planner_shadow_records_but_controlled_appends_the_tool_node() -> None:
    request = _request(text="请画图", circuit_ir=CircuitIR())
    route = RouteDecision(
        agent_id="ACADEMIC_PROBLEM_SOLVER",
        scene="solving",
        course_id="CT",
        intent="solve_problem",
        route_status=RouteStatus.SELECTED,
        reason="test",
        retrieval_required=False,
        provider_required=False,
    )
    plan = CanonicalPlan(
        plan_id="canonical:v3-planner",
        goal=CanonicalGoal(objective="draw"),
        nodes=[
            CanonicalPlanNode(
                node_id="solve",
                node_type="agent",
                target_id="academic.solve",
            )
        ],
    )

    shadow_plan, shadow_decision = PlannerService._append_circuit_visualization(
        request, route, Settings(circuit_visualization_mode="shadow"), plan
    )
    controlled_plan, controlled_decision = (
        PlannerService._append_circuit_visualization(
            request,
            route,
            Settings(circuit_visualization_mode="controlled"),
            plan,
        )
    )

    assert shadow_decision.decision == "REQUIRED"
    assert not any(node.node_id == "circuit.visualize" for node in shadow_plan.nodes)
    assert controlled_decision.should_schedule
    assert any(
        node.node_id == "circuit.visualize" for node in controlled_plan.nodes
    )


def test_failed_circuit_render_is_a_nonfatal_runtime_observation() -> None:
    observation = runtime_observation_from_tool(
        node_id="circuit.visualize",
        execution_key="run:circuit.visualize",
        circuit_payload={},
        result={
            "status": "failed",
            "svg": None,
            "artifact_ref": None,
            "validation_state": "invalid",
            "warnings": ["invalid_fixture"],
            "validation": {"status": "invalid", "issues": [], "warnings": []},
            "render_latency_ms": 0.0,
            "renderer": "none",
        },
    )

    assert observation.terminal_status.value == "succeeded"
    nested = observation.facts["circuit_render_observation"]
    assert nested["status"] == "failed"
    assert nested["recoverable"] is False


def test_rendered_observation_projects_to_a_circuit_svg_artifact() -> None:
    observation = runtime_observation_from_tool(
        node_id="circuit.visualize",
        execution_key="run:circuit.visualize",
        circuit_payload={},
        result={
            "status": "rendered",
            "svg": "<svg />",
            "artifact_ref": None,
            "validation_state": "validated",
            "warnings": [],
            "validation": {"status": "validated", "issues": [], "warnings": []},
            "render_latency_ms": 1.0,
            "renderer": "schemdraw",
        },
    )
    run = AgentRun(
        run_id="run-v3-artifact",
        task_id="task-v3-artifact",
        goal="draw",
        plan=AgentRunPlan(
            plan_id="plan-v3-artifact",
            goal="draw",
            nodes=[
                RuntimeNode(
                    node_id="circuit.visualize",
                    node_type="tool",
                    handler_id="tool.circuit.render",
                )
            ],
        ),
        observations=[observation],
    )
    result = AgentResult(agent_id="ACADEMIC_PROBLEM_SOLVER", provider="test")

    projected = project_circuit_artifact(result, run)
    assert projected.artifacts[0].artifact_type.value == "circuit_svg"
    assert projected.structured_result["circuit_artifact"]["type"] == "circuit_svg"
    assert projected.structured_result["circuit_artifact"]["svg"] == "<svg />"


def test_circuit_tool_is_opt_in_at_registry_composition_root() -> None:
    assert not default_tool_registry().describe("circuit.render").enabled
    assert default_tool_registry(circuit_render_enabled=True).describe(
        "circuit.render"
    ).enabled
