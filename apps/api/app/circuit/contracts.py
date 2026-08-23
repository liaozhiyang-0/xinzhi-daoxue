from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ComponentKind = str
ValidationState = Literal["unvalidated", "validated", "invalid", "uncertain"]
RenderStatus = Literal["rendered", "degraded", "failed"]

SUPPORTED_COMPONENT_TYPES = frozenset(
    {
        "resistor",
        "capacitor",
        "inductor",
        "voltage_source",
        "current_source",
        "dependent_voltage_source",
        "dependent_current_source",
        "ground",
        "switch",
        "diode",
        "opamp",
        "bjt",
        "mosfet",
        "input",
        "output",
        "node_label",
    }
)
PORT_CONTRACTS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "resistor": (frozenset({"p", "n"}), frozenset()),
    "capacitor": (frozenset({"p", "n"}), frozenset()),
    "inductor": (frozenset({"p", "n"}), frozenset()),
    "voltage_source": (frozenset({"p", "n"}), frozenset()),
    "current_source": (frozenset({"p", "n"}), frozenset()),
    "dependent_voltage_source": (frozenset({"p", "n", "cp", "cn"}), frozenset()),
    "dependent_current_source": (frozenset({"p", "n", "cp", "cn"}), frozenset()),
    "ground": (frozenset({"g"}), frozenset()),
    "switch": (frozenset({"p", "n"}), frozenset()),
    "diode": (frozenset({"a", "k"}), frozenset()),
    "opamp": (frozenset({"plus", "minus", "out", "vplus", "vminus"}), frozenset()),
    "bjt": (frozenset({"b", "c", "e"}), frozenset()),
    "mosfet": (frozenset({"g", "d", "s"}), frozenset({"b"})),
    "input": (frozenset({"p"}), frozenset()),
    "output": (frozenset({"p"}), frozenset()),
    "node_label": (frozenset({"p"}), frozenset()),
}
OUTPUT_PORT_NAMES = frozenset({"out", "output", "y"})


class CircuitComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    type: ComponentKind = Field(min_length=1, max_length=64)
    ports: dict[str, str] = Field(default_factory=dict)
    value: str | float | None = None
    label: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class CircuitNet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    label: str | None = None
    kind: Literal["signal", "reference", "power", "unknown"] = "unknown"


class CircuitAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["text", "value", "arrow", "equation"] = "text"
    text: str = Field(max_length=500)
    target_id: str | None = None


class CircuitUncertainty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=500)
    severity: Literal["info", "warning", "critical"] = "warning"
    component_ids: list[str] = Field(default_factory=list)
    net_ids: list[str] = Field(default_factory=list)


class CircuitIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["circuit_ir.v1"] = "circuit_ir.v1"
    components: list[CircuitComponent] = Field(default_factory=list)
    nets: list[CircuitNet] = Field(default_factory=list)
    annotations: list[CircuitAnnotation] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    uncertainties: list[CircuitUncertainty] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    topology_hint: str | None = None
    validation_state: ValidationState = "unvalidated"


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    component_id: str | None = None
    net_id: str | None = None


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ValidationState
    issues: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class CircuitRenderOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template: str = "generic_left_to_right"
    width: int = Field(default=900, ge=320, le=4000)
    height: int = Field(default=360, ge=180, le=2400)
    include_values: bool = True
    include_labels: bool = True


class CircuitRenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    circuit: CircuitIR
    render_options: CircuitRenderOptions = Field(default_factory=CircuitRenderOptions)


class CircuitRenderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RenderStatus
    svg: str | None = None
    artifact_ref: str | None = None
    validation_state: ValidationState
    warnings: list[str] = Field(default_factory=list)
    validation: ValidationReport
    render_latency_ms: float = 0.0
    renderer: str = "fallback_svg"
