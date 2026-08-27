from __future__ import annotations

import pytest
from app.circuit import CircuitIR
from app.circuit import renderer as renderer_module
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
from app.services.academic_solver_runtime import AcademicSolverRuntimeService
from app.services.canonical_plan_adapter import CanonicalPlanAdapter
from app.services.circuit_visualization import (
    decide_circuit_visualization,
    project_circuit_artifact,
    resolve_circuit_visualization_mode,
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


def _valid_circuit() -> CircuitIR:
    return CircuitIR.model_validate(
        {
            "components": [
                {
                    "id": "r1",
                    "type": "resistor",
                    "ports": {"p": "in", "n": "gnd"},
                    "value": "1k",
                },
                {"id": "gnd", "type": "ground", "ports": {"g": "gnd"}},
            ],
            "nets": [{"id": "in"}, {"id": "gnd"}],
        }
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
    explicit_ae = decide_circuit_visualization(
        _request(text="请生成这个分压电路的电路图", circuit_ir=circuit),
        feature_mode="controlled",
        course_id="AE",
    )
    off = decide_circuit_visualization(
        _request(text="请画图", circuit_ir=circuit),
        feature_mode="off",
    )
    unavailable = decide_circuit_visualization(
        _request(text="请画图"),
        feature_mode="controlled",
    )

    assert shadow.decision == "REQUIRED"
    assert not shadow.should_schedule
    assert controlled.should_schedule
    assert explicit_ae.should_schedule
    assert off.decision == "SKIP"
    assert "CIRCUIT_IR_UNAVAILABLE" in unavailable.reason_codes
    assert not unavailable.should_schedule


def test_workspace_toggle_resolves_controlled_mode_per_task() -> None:
    request = _request(text="请画图", circuit_ir=_valid_circuit()).model_copy(
        update={"options": {"circuit_visualization_mode": "controlled"}}
    )

    assert (
        resolve_circuit_visualization_mode(
            request,
            configured_mode="off",
            frontend_enabled=True,
        )
        == "controlled"
    )
    assert (
        resolve_circuit_visualization_mode(
            request.model_copy(
                update={"options": {"circuit_visualization_mode": "off"}}
            ),
            configured_mode="controlled",
            frontend_enabled=True,
        )
        == "off"
    )
    assert (
        resolve_circuit_visualization_mode(
            _request(text="请画图：这个分压电路", circuit_ir=_valid_circuit()),
            configured_mode="off",
            auto_enabled=True,
        )
        == "controlled"
    )
    assert (
        resolve_circuit_visualization_mode(
            request,
            configured_mode="off",
            frontend_enabled=False,
        )
        == "off"
    )
    assert (
        resolve_circuit_visualization_mode(
            request,
            configured_mode="controlled",
            render_enabled=False,
        )
        == "off"
    )
    assert (
        resolve_circuit_visualization_mode(
            _request(text="请解释分压原理", circuit_ir=_valid_circuit()),
            configured_mode="controlled",
            auto_enabled=False,
        )
        == "off"
    )


def test_canonical_plan_binds_circuit_visualization_to_tool() -> None:
    plan = CanonicalPlan(
        plan_id="canonical:v3",
        goal=CanonicalGoal(objective="draw"),
        nodes=[
            CanonicalPlanNode(
                node_id="circuit.visualize",
                node_type="tool",
                target_id="circuit.visualize",
                input_ref="CircuitIR",
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
    assert node.input_ref == "CircuitIR"
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
    controlled_plan, controlled_decision = PlannerService._append_circuit_visualization(
        request,
        route,
        Settings(circuit_visualization_mode="controlled"),
        plan,
    )

    assert shadow_decision.decision == "REQUIRED"
    assert not any(node.node_id == "circuit.visualize" for node in shadow_plan.nodes)
    assert controlled_decision.should_schedule
    assert any(node.node_id == "circuit.visualize" for node in controlled_plan.nodes)


def test_academic_solver_runtime_reuses_controlled_circuit_tool_node() -> None:
    circuit = _valid_circuit()
    canonical = {
        "circuit_visualization": {
            "decision": "OPTIONAL",
            "feature_mode": "controlled",
            "blocked": False,
        }
    }
    request = _request(text="请画图", circuit_ir=circuit).model_copy(
        update={
            "options": {
                "_canonical_plan": canonical,
                "_planner_snapshot": {"canonical_plan": canonical},
            }
        }
    )
    service = AcademicSolverRuntimeService(
        None,
        enabled=True,
        tool_registry=default_tool_registry(circuit_render_enabled=True),
    )

    assert service._requested_tool_id(request) == "circuit.render"
    node = next(
        node
        for node in service.build_plan(request).nodes
        if node.target_id == "circuit.render"
    )
    assert node.handler_id == "academic.solver.tool.circuit.render"


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


def test_primary_schemdraw_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        renderer_module,
        "_try_schemdraw",
        lambda circuit, options: "<svg data-renderer='schemdraw' />",
    )
    result = renderer_module.render_circuit(_valid_circuit())

    assert result.status == "rendered"
    assert result.renderer == "schemdraw"


def test_deterministic_fallback_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(circuit: CircuitIR, options: object) -> str:
        raise ModuleNotFoundError("schemdraw")

    monkeypatch.setattr(renderer_module, "_try_schemdraw", unavailable)
    result = renderer_module.render_circuit(_valid_circuit())

    assert result.status == "degraded"
    assert result.renderer == "fallback_svg"
    assert result.svg is not None


def test_dependency_unavailable_is_projected_as_nonfatal_failure() -> None:
    observation = runtime_observation_from_tool(
        node_id="circuit.visualize",
        execution_key="run:circuit.visualize",
        circuit_payload=None,
        result=None,
        error="schemdraw_dependency_unavailable",
    )

    nested = observation.facts["circuit_render_observation"]
    assert observation.terminal_status.value == "succeeded"
    assert nested["status"] == "failed"
    assert nested["renderer"] == "none"


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


def test_explicit_circuit_render_projects_image_only_presentation_mode() -> None:
    observation = runtime_observation_from_tool(
        node_id="circuit.visualize",
        execution_key="run:circuit.visualize:image-only",
        circuit_payload={},
        result={
            "status": "rendered",
            "svg": "<svg />",
            "artifact_ref": None,
            "validation_state": "validated",
            "warnings": [],
            "validation": {"status": "validated", "issues": [], "warnings": []},
            "render_latency_ms": 1.0,
            "renderer": "professional_svg",
        },
    )
    request = _request(text="请画出这个典型分压电路")
    request = request.model_copy(
        update={"options": {"circuit_visualization_mode": "controlled"}}
    )
    run = AgentRun(
        run_id="run-v3-image-only",
        task_id="task-v3-image-only",
        goal="draw",
        plan=AgentRunPlan(
            plan_id="plan-v3-image-only",
            goal="draw",
            nodes=[
                RuntimeNode(
                    node_id="circuit.visualize",
                    node_type="tool",
                    handler_id="tool.circuit.render",
                )
            ],
        ),
        request_snapshot=request.model_dump(mode="json"),
        observations=[observation],
    )
    result = AgentResult(agent_id="ACADEMIC_PROBLEM_SOLVER", provider="test")

    projected = project_circuit_artifact(result, run)

    assert (
        projected.structured_result["circuit_artifact"]["metadata"][
            "presentation_mode"
        ]
        == "image_only"
    )


def test_circuit_tool_is_opt_in_at_registry_composition_root() -> None:
    assert not default_tool_registry().describe("circuit.render").enabled
    assert (
        default_tool_registry(circuit_render_enabled=True)
        .describe("circuit.render")
        .enabled
    )
