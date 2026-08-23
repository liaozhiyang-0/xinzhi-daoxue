from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.circuit.contracts import (
    CircuitIR,
    CircuitRenderObservation,
    CircuitRenderResult,
)
from app.contracts.agent import AgentRequest, AgentResult, Artifact, ArtifactType
from app.observability.architecture_telemetry import architecture_telemetry
from app.runtime.contracts import AgentRun, RuntimeObservation

CircuitVisualizationMode = Literal["off", "shadow", "controlled"]
CircuitDecision = Literal["SKIP", "OPTIONAL", "REQUIRED"]


class CircuitVisualizationDecision(BaseModel):
    """Planner-only decision; it never performs parsing or rendering."""

    model_config = ConfigDict(extra="forbid")

    decision: CircuitDecision
    reason_codes: list[str] = Field(default_factory=list, max_length=16)
    feature_mode: CircuitVisualizationMode
    circuit_ir_available: bool = False
    topology_signal: bool = False
    critical_uncertainty_count: int = Field(default=0, ge=0)
    component_count: int = Field(default=0, ge=0)
    blocked: bool = False

    @property
    def should_schedule(self) -> bool:
        return (
            self.feature_mode == "controlled"
            and self.decision in {"OPTIONAL", "REQUIRED"}
            and self.circuit_ir_available
            and not self.blocked
        )


def decide_circuit_visualization(
    request: AgentRequest,
    *,
    feature_mode: CircuitVisualizationMode,
    course_id: str | None = None,
) -> CircuitVisualizationDecision:
    """Make a bounded, provider-free Planner Shadow decision.

    Only trusted structured ``circuit_ir`` input is eligible for execution.
    Images and free text can express intent, but they are never converted to
    CircuitIR here.
    """

    circuit = extract_circuit_ir(request)
    text = request.input_text().casefold()
    explicit = any(
        marker in text
        for marker in (
            "画图",
            "重绘",
            "绘制电路",
            "生成电路图",
            "等效电路",
            "draw circuit",
            "redraw circuit",
            "circuit diagram",
        )
    )
    topology_signal = any(
        marker in text
        for marker in (
            "电路",
            "rc",
            "rlc",
            "运放",
            "op amp",
            "opamp",
            "二极管",
            "diode",
            "bjt",
            "mosfet",
            "低通",
            "高通",
        )
    ) or bool(circuit and circuit.topology_hint)
    critical = sum(
        item.severity == "critical" for item in circuit.uncertainties
    ) if circuit else 0
    component_count = len(circuit.components) if circuit else 0
    reasons: list[str] = []
    decision: CircuitDecision

    if feature_mode == "off":
        reasons.append("feature_mode_off")
        decision = "SKIP"
    elif not explicit and not topology_signal:
        reasons.append("no_visualization_signal")
        decision = "SKIP"
    elif explicit:
        reasons.append("explicit_draw_request")
        decision = "REQUIRED"
    else:
        reasons.append("topology_material_to_answer")
        decision = "OPTIONAL"

    if not circuit and decision != "SKIP":
        reasons.append("circuit_ir_unavailable")
    if component_count > 64:
        reasons.append("complexity_budget_exceeded")
    if critical:
        reasons.append("critical_uncertainty")

    blocked = not circuit or component_count > 64 or critical > 0
    if feature_mode == "controlled" and decision != "SKIP" and not explicit:
        normalized_course = (course_id or request.course_id).upper()
        controlled_allowlist = (
            normalized_course == "CT"
            or (
                normalized_course == "AE"
                and any(marker in text for marker in ("ideal", "理想"))
                and any(marker in text for marker in ("op amp", "opamp", "运放"))
            )
        )
        if not controlled_allowlist:
            reasons.append("controlled_allowlist_miss")
            decision = "SKIP"
            blocked = True

    result = CircuitVisualizationDecision(
        decision=decision,
        reason_codes=list(dict.fromkeys(reasons)),
        feature_mode=feature_mode,
        circuit_ir_available=circuit is not None,
        topology_signal=topology_signal,
        critical_uncertainty_count=critical,
        component_count=component_count,
        blocked=blocked,
    )
    architecture_telemetry.increment("circuit_decision_total")
    architecture_telemetry.increment(
        f"circuit_decision_total_{result.decision.casefold()}"
    )
    return result


def extract_circuit_ir(request: AgentRequest) -> CircuitIR | None:
    """Read only trusted structured IR; do not infer IR from text or images."""

    for container in (request.canonical_input, request.options):
        candidate = container.get("circuit_ir")
        if isinstance(candidate, CircuitIR):
            return candidate
        if isinstance(candidate, Mapping):
            try:
                return CircuitIR.model_validate(candidate)
            except ValueError:
                return None
    return None


def observation_from_result(
    circuit: CircuitIR, result: CircuitRenderResult | Mapping[str, Any]
) -> CircuitRenderObservation:
    render_result = (
        result
        if isinstance(result, CircuitRenderResult)
        else CircuitRenderResult.model_validate(result)
    )
    validation_state = cast(
        Literal["validated", "partially_validated", "needs_review", "invalid"],
        {
            "validated": "validated",
            "uncertain": "needs_review",
            "invalid": "invalid",
            "unvalidated": "partially_validated",
        }[render_result.validation_state],
    )
    renderer = cast(
        Literal["schemdraw", "deterministic_fallback", "none"],
        "none"
        if render_result.status == "failed"
        else {
            "schemdraw": "schemdraw",
            "fallback_svg": "deterministic_fallback",
        }.get(render_result.renderer, "none"),
    )
    recoverable = render_result.status != "failed" or validation_state != "invalid"
    observation = CircuitRenderObservation(
        status=render_result.status,
        validation_state=validation_state,
        renderer=renderer,
        warnings=list(dict.fromkeys(render_result.warnings))[:32],
        svg=render_result.svg,
        artifact_ref=render_result.artifact_ref,
        render_latency_ms=render_result.render_latency_ms,
        critical_uncertainty_count=sum(
            item.severity == "critical" for item in circuit.uncertainties
        ),
        recoverable=recoverable,
    )
    architecture_telemetry.increment("circuit_render_total")
    architecture_telemetry.increment(
        f"circuit_render_total_{observation.status.casefold()}"
    )
    architecture_telemetry.increment("circuit_renderer_total")
    architecture_telemetry.increment(
        "circuit_renderer_total_"
        + ("fallback" if renderer == "deterministic_fallback" else renderer)
    )
    architecture_telemetry.increment("circuit_validation_state_total")
    architecture_telemetry.increment(
        "circuit_validation_state_total_" + observation.validation_state
    )
    architecture_telemetry.observe(
        "circuit_render_latency_ms", observation.render_latency_ms
    )
    if observation.status == "failed":
        architecture_telemetry.increment("circuit_nonfatal_failure_total")
    return observation


def runtime_observation_from_tool(
    *,
    node_id: str,
    execution_key: str,
    circuit_payload: Mapping[str, Any] | None,
    result: Mapping[str, Any] | None,
    error: str = "",
) -> RuntimeObservation:
    try:
        circuit = CircuitIR.model_validate(circuit_payload or {})
        if result is None:
            raise ValueError(error or "circuit_render_result_missing")
        stable = observation_from_result(circuit, result)
    except (TypeError, ValueError) as exc:
        stable = CircuitRenderObservation(
            status="failed",
            validation_state="invalid",
            renderer="none",
            warnings=[f"circuit_render_nonfatal:{type(exc).__name__}"],
            render_latency_ms=0.0,
            critical_uncertainty_count=0,
            recoverable=False,
        )
        architecture_telemetry.increment("circuit_nonfatal_failure_total")
    return RuntimeObservation(
        node_id=node_id,
        # The Runtime node itself completes successfully; render failure is
        # carried as a bounded nested observation and cannot trigger reroute.
        facts={
            "tool_id": "circuit.render",
            "execution_key": execution_key,
            "circuit_render_observation": stable.model_dump(mode="json"),
        },
        warnings=list(stable.warnings),
    )


def project_circuit_artifact(result: AgentResult, run: AgentRun) -> AgentResult:
    """Project the latest circuit observation into the formal task result."""

    raw: Mapping[str, Any] | None = None
    for runtime_observation in reversed(run.observations):
        candidate = runtime_observation.facts.get("circuit_render_observation")
        if isinstance(candidate, Mapping):
            raw = candidate
            break
    if raw is None:
        return result
    try:
        render_observation = CircuitRenderObservation.model_validate(raw)
    except ValueError:
        return result
    structured = dict(result.structured_result)
    structured["circuit_render_observation"] = render_observation.model_dump(
        mode="json"
    )
    artifacts = list(result.artifacts)
    if render_observation.svg:
        artifact = Artifact(
            artifact_type=ArtifactType.CIRCUIT_SVG,
            owner_id=result.agent_id,
            task_id=result.task_id,
            course_id=result.course_id or "CT",
            content={
                "type": "circuit_svg",
                "status": render_observation.status,
                "validation_state": render_observation.validation_state,
                "artifact_ref": render_observation.artifact_ref,
                "svg": render_observation.svg,
                "warnings": list(render_observation.warnings),
                "metadata": {
                    "circuit_ir_version": render_observation.circuit_ir_version,
                    "critical_uncertainty_count": (
                        render_observation.critical_uncertainty_count
                    ),
                    "render_latency_ms": render_observation.render_latency_ms,
                },
            },
        )
        render_observation = render_observation.model_copy(
            update={
                "artifact_ref": render_observation.artifact_ref
                or artifact.artifact_id
            }
        )
        artifacts.append(artifact)
        structured["circuit_artifact"] = artifact.content
    else:
        structured["circuit_artifact"] = {
            "type": "circuit_svg",
            "status": render_observation.status,
            "validation_state": render_observation.validation_state,
            "warnings": list(render_observation.warnings),
            "metadata": {
                "circuit_ir_version": render_observation.circuit_ir_version,
                "critical_uncertainty_count": (
                    render_observation.critical_uncertainty_count
                ),
                "render_latency_ms": render_observation.render_latency_ms,
            },
        }
    structured["circuit_render_observation"] = render_observation.model_dump(
        mode="json"
    )
    return result.model_copy(
        update={"structured_result": structured, "artifacts": artifacts}
    )
