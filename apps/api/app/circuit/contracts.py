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
        "zener_diode",
        "coupled_inductor",
        "open_circuit",
        "short_circuit",
        "and_gate",
        "or_gate",
        "not_gate",
        "nand_gate",
        "nor_gate",
        "xor_gate",
        "xnor_gate",
        "buffer",
        "schmitt_trigger",
        "d_flip_flop",
        "jk_flip_flop",
        "t_flip_flop",
        "sr_latch",
        "mux",
        "demux",
        "encoder",
        "decoder",
        "half_adder",
        "full_adder",
        "clock",
        "logic_input",
        "logic_output",
        "bus",
        "vcc",
        "vdd",
        "vss",
        "vee",
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
    "zener_diode": (frozenset({"a", "k"}), frozenset()),
    "coupled_inductor": (frozenset({"p1", "n1", "p2", "n2"}), frozenset()),
    "open_circuit": (frozenset({"p", "n"}), frozenset()),
    "short_circuit": (frozenset({"p", "n"}), frozenset()),
    "and_gate": (frozenset({"in1", "in2", "out"}), frozenset()),
    "or_gate": (frozenset({"in1", "in2", "out"}), frozenset()),
    "not_gate": (frozenset({"in", "out"}), frozenset()),
    "nand_gate": (frozenset({"in1", "in2", "out"}), frozenset()),
    "nor_gate": (frozenset({"in1", "in2", "out"}), frozenset()),
    "xor_gate": (frozenset({"in1", "in2", "out"}), frozenset()),
    "xnor_gate": (frozenset({"in1", "in2", "out"}), frozenset()),
    "buffer": (frozenset({"in", "out"}), frozenset()),
    "schmitt_trigger": (frozenset({"in", "out"}), frozenset()),
    "d_flip_flop": (frozenset({"d", "clk", "q"}), frozenset({"qb", "reset", "set"})),
    "jk_flip_flop": (
        frozenset({"j", "k", "clk", "q"}),
        frozenset({"qb", "reset", "set"}),
    ),
    "t_flip_flop": (frozenset({"t", "clk", "q"}), frozenset({"qb", "reset", "set"})),
    "sr_latch": (frozenset({"s", "r", "q"}), frozenset({"qb", "enable"})),
    "mux": (frozenset({"in1", "in2", "sel", "out"}), frozenset()),
    "demux": (frozenset({"in", "sel", "out1", "out2"}), frozenset()),
    "encoder": (frozenset({"in1", "in2", "in3", "in4", "out1", "out2"}), frozenset()),
    "decoder": (frozenset({"in1", "in2", "out1", "out2", "out3", "out4"}), frozenset()),
    "half_adder": (frozenset({"a", "b", "sum", "carry"}), frozenset()),
    "full_adder": (frozenset({"a", "b", "cin", "sum", "carry"}), frozenset()),
    "clock": (frozenset({"out"}), frozenset()),
    "logic_input": (frozenset({"p"}), frozenset()),
    "logic_output": (frozenset({"p"}), frozenset()),
    "bus": (frozenset({"in", "out"}), frozenset()),
    "vcc": (frozenset({"p"}), frozenset()),
    "vdd": (frozenset({"p"}), frozenset()),
    "vss": (frozenset({"p"}), frozenset()),
    "vee": (frozenset({"p"}), frozenset()),
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
    schema_status: Literal["validated", "invalid"] = "validated"
    topology_status: Literal["validated", "invalid", "uncertain"] = "validated"
    semantic_status: Literal["validated", "partially_validated", "needs_review"] = (
        "validated"
    )
    render_status: Literal["not_run", "validated", "degraded", "invalid"] = "not_run"


class CircuitRenderOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template: str = "generic_left_to_right"
    width: int = Field(default=900, ge=320, le=4000)
    height: int = Field(default=520, ge=180, le=2400)
    include_values: bool = True
    include_labels: bool = True
    professional_renderer: bool = True


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
    professional_renderer_success: bool = False
    layout_schema_version: str = ""
    template: str = ""
    width: int = 0
    height: int = 0


class CircuitRenderObservation(BaseModel):
    """Stable Runtime projection for circuit rendering.

    ``CircuitRenderResult`` remains the renderer-facing compatibility
    contract.  This smaller projection is the only circuit shape that the
    Planner/Runtime boundary needs to understand.
    """

    model_config = ConfigDict(extra="forbid")

    status: RenderStatus
    validation_state: Literal[
        "validated", "partially_validated", "needs_review", "invalid"
    ]
    renderer: Literal["professional_svg", "schemdraw", "deterministic_fallback", "none"]
    warnings: list[str] = Field(default_factory=list, max_length=32)
    svg: str | None = None
    artifact_ref: str | None = None
    render_latency_ms: float = Field(default=0.0, ge=0)
    circuit_ir_version: Literal["circuit_ir.v1"] = "circuit_ir.v1"
    critical_uncertainty_count: int = Field(default=0, ge=0)
    recoverable: bool = True
    professional_renderer_success: bool = False
    layout_schema_version: str = ""
    template: str = ""
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
