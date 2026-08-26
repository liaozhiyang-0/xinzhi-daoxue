from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from app.circuit import (
    CircuitAnnotation,
    CircuitComponent,
    CircuitIR,
    CircuitRenderOptions,
    build_schematic_layout,
    render_circuit,
)
from app.circuit import renderer as renderer_module
from app.circuit.contracts import PORT_CONTRACTS
from app.circuit.renderer import _symbol_body
from app.services.circuit_visualization import observation_from_result

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "circuit_golden_cases.json"
DIGITAL_TYPES = (
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
    "bus",
)


def _golden_circuits() -> list[CircuitIR]:
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    return [
        CircuitIR.model_validate({key: case[key] for key in ("components", "nets")})
        for case in cases
    ]


def _benchmark_cases() -> list[tuple[str, CircuitIR]]:
    cases: list[tuple[str, CircuitIR]] = []
    for index in range(50):
        cases.append(("CT", _ct_case(index)))
        cases.append(("AE", _ae_case(index)))
        cases.append(("DE", _de_case(index)))
    return cases


def _ct_case(index: int) -> CircuitIR:
    kind = (
        "resistor",
        "capacitor",
        "inductor",
        "diode",
        "zener_diode",
        "switch",
        "open_circuit",
        "short_circuit",
        "voltage_source",
        "current_source",
    )[index % 10]
    ports = {"p": "in", "n": "out"}
    return CircuitIR.model_validate(
        {
            "components": [
                {
                    "id": f"v{index}",
                    "type": "voltage_source",
                    "ports": {"p": "in", "n": "gnd"},
                    "value": "5 V",
                },
                {
                    "id": f"x{index}",
                    "type": kind,
                    "ports": (
                        {"a": "in", "k": "out"}
                        if kind in {"diode", "zener_diode"}
                        else ports
                    ),
                    "value": "1 kΩ",
                },
                {
                    "id": f"r{index}",
                    "type": "resistor",
                    "ports": {"p": "out", "n": "gnd"},
                    "value": "1 kΩ",
                },
                {
                    "id": f"g{index}",
                    "type": "ground",
                    "ports": {"g": "gnd"},
                },
            ],
            "nets": [
                {"id": "in"},
                {"id": "out"},
                {"id": "gnd", "kind": "reference"},
            ],
        }
    )


def _ae_case(index: int) -> CircuitIR:
    family = index % 5
    if family == 0:
        components = [
            {
                "id": f"op{index}",
                "type": "opamp",
                "ports": {
                    "plus": "in",
                    "minus": "fb",
                    "out": "out",
                    "vplus": "vcc",
                    "vminus": "gnd",
                },
            },
            {
                "id": f"rin{index}",
                "type": "resistor",
                "ports": {"p": "in", "n": "fb"},
                "value": "10 kΩ",
            },
            {
                "id": f"rf{index}",
                "type": "resistor",
                "ports": {"p": "fb", "n": "out"},
                "value": "100 kΩ",
            },
        ]
    elif family == 1:
        components = [
            {
                "id": f"q{index}",
                "type": "bjt",
                "ports": {"b": "base", "c": "collector", "e": "emitter"},
            },
            {
                "id": f"rb{index}",
                "type": "resistor",
                "ports": {"p": "base", "n": "bias"},
            },
            {
                "id": f"rc{index}",
                "type": "resistor",
                "ports": {"p": "collector", "n": "vcc"},
            },
            {
                "id": f"re{index}",
                "type": "resistor",
                "ports": {"p": "emitter", "n": "gnd"},
            },
        ]
    elif family == 2:
        components = [
            {
                "id": f"m{index}",
                "type": "mosfet",
                "ports": {"g": "gate", "d": "drain", "s": "source"},
            },
            {
                "id": f"rg{index}",
                "type": "resistor",
                "ports": {"p": "gate", "n": "gnd"},
            },
            {
                "id": f"rd{index}",
                "type": "resistor",
                "ports": {"p": "drain", "n": "vcc"},
            },
            {
                "id": f"rs{index}",
                "type": "resistor",
                "ports": {"p": "source", "n": "gnd"},
            },
        ]
    else:
        diode = "diode" if family == 3 else "zener_diode"
        components = [
            {
                "id": f"v{index}",
                "type": "voltage_source",
                "ports": {"p": "in", "n": "gnd"},
            },
            {
                "id": f"d{index}",
                "type": diode,
                "ports": {"a": "in", "k": "out"},
            },
            {
                "id": f"rl{index}",
                "type": "resistor",
                "ports": {"p": "out", "n": "gnd"},
            },
        ]
    components.extend(
        [
            {"id": f"g{index}", "type": "ground", "ports": {"g": "gnd"}},
            {
                "id": f"in{index}",
                "type": "input",
                "ports": {
                    "p": "in"
                    if family == 0
                    else "base"
                    if family == 1
                    else "gate"
                    if family == 2
                    else "in"
                },
            },
        ]
    )
    net_ids = {
        net_id
        for component in components
        for net_id in cast(dict[str, str], component["ports"]).values()
    }
    return CircuitIR.model_validate(
        {
            "components": components,
            "nets": [
                {
                    "id": net_id,
                    "kind": "reference"
                    if net_id == "gnd"
                    else "power"
                    if net_id == "vcc"
                    else "signal",
                }
                for net_id in sorted(net_ids)
            ],
        }
    )


def _de_case(index: int) -> CircuitIR:
    kind = DIGITAL_TYPES[index % len(DIGITAL_TYPES)]
    required, _ = PORT_CONTRACTS[kind]
    ports = {port: f"n{index}_{port}" for port in sorted(required)}
    output_ports = {
        "out",
        "out1",
        "out2",
        "q",
        "qb",
        "sum",
        "carry",
        "y",
        "y0",
        "y1",
        "y2",
        "y3",
    }
    components: list[dict[str, object]] = [
        {"id": f"u{index}", "type": kind, "ports": ports}
    ]
    for port, net_id in ports.items():
        endpoint_type = "logic_output" if port in output_ports else "logic_input"
        components.append(
            {
                "id": f"{endpoint_type}_{index}_{port}",
                "type": endpoint_type,
                "ports": {"p": net_id},
            }
        )
    return CircuitIR.model_validate(
        {
            "components": components,
            "nets": [{"id": net_id, "kind": "signal"} for net_id in ports.values()],
        }
    )


def test_layout_contract_is_deterministic_and_orthogonal() -> None:
    for circuit in _golden_circuits():
        first = build_schematic_layout(circuit)
        second = build_schematic_layout(circuit)
        assert first.model_dump(mode="json") == second.model_dump(mode="json")
        assert first.schema_version == "schematic_layout.v1"
        assert {item.component_id for item in first.placements} == {
            item.id for item in circuit.components
        }
        for wire in first.wires:
            assert all(
                start.x == end.x or start.y == end.y
                for start, end in zip(wire.points, wire.points[1:], strict=False)
            )


def test_layout_contract_carries_reference_direction_and_annotation_layers() -> None:
    voltage_case = _golden_circuits()[0]
    layout = build_schematic_layout(voltage_case)
    assert layout.schema_version == "schematic_layout.v1"
    assert layout.polarity_markers
    assert layout.groups
    assert layout.annotations == []

    current_case = _golden_circuits()[6]
    current_layout = build_schematic_layout(current_case)
    assert current_layout.direction_arrows

    annotated = current_case.model_copy(
        update={
            "annotations": [
                CircuitAnnotation(kind="equation", text="i = v / R", target_id="r1")
            ]
        }
    )
    annotated_layout = build_schematic_layout(annotated)
    assert annotated_layout.annotations[0].kind == "equation"

    arrow_annotated = current_case.model_copy(
        update={
            "annotations": [
                CircuitAnnotation(kind="arrow", text="Iout", target_id="i1")
            ]
        }
    )
    arrow_layout = build_schematic_layout(arrow_annotated)
    assert not any(label.text == "Iout" for label in arrow_layout.labels)
    assert arrow_layout.annotations[0].text == "Iout"


def test_layout_emits_junctions_and_unknown_value_marker() -> None:
    parallel = build_schematic_layout(_golden_circuits()[2], "parallel")
    assert any(junction.net_id == "gnd" for junction in parallel.junctions)

    unknown = CircuitIR.model_validate(
        {
            "components": [
                {"id": "r1", "type": "resistor", "ports": {"p": "in", "n": "gnd"}},
                {"id": "gnd", "type": "ground", "ports": {"g": "gnd"}},
            ],
            "nets": [{"id": "in"}, {"id": "gnd", "kind": "reference"}],
        }
    )
    layout = build_schematic_layout(unknown)
    assert any(label.text == "?" and label.kind == "value" for label in layout.labels)


def test_professional_renderer_preserves_component_and_wire_metadata() -> None:
    circuit = _golden_circuits()[8]
    result = render_circuit(circuit, CircuitRenderOptions(template="opamp_inverting"))

    assert result.status in {"rendered", "degraded"}
    assert result.renderer == "professional_svg"
    assert result.professional_renderer_success is True
    assert result.layout_schema_version == "schematic_layout.v1"
    assert result.svg is not None
    assert 'data-component-id="op1"' in result.svg
    assert 'data-wire-net="out"' in result.svg


def test_professional_renderer_emits_polarity_and_direction_metadata() -> None:
    voltage_result = render_circuit(_golden_circuits()[0])
    assert voltage_result.svg is not None
    assert 'data-polarity="v1:positive"' in voltage_result.svg

    current_result = render_circuit(_golden_circuits()[6])
    assert current_result.svg is not None
    assert 'data-direction-target="i1"' in current_result.svg
    assert 'marker-end="url(#circuit-arrow)"' in current_result.svg


def test_runtime_projection_accepts_professional_renderer_metadata() -> None:
    circuit = _golden_circuits()[0]
    result = render_circuit(circuit, CircuitRenderOptions(template="series"))

    observation = observation_from_result(circuit, result)

    assert observation.renderer == "professional_svg"
    assert observation.professional_renderer_success is True
    assert observation.layout_schema_version == "schematic_layout.v1"
    assert observation.template == "series"


def test_known_analog_and_digital_symbols_are_not_unknown_placeholders() -> None:
    kinds = {
        "resistor",
        "capacitor",
        "inductor",
        "voltage_source",
        "current_source",
        "dependent_voltage_source",
        "dependent_current_source",
        "diode",
        "zener_diode",
        "opamp",
        "bjt",
        "mosfet",
        "and_gate",
        "or_gate",
        "not_gate",
        "d_flip_flop",
        "mux",
        "clock",
        "vcc",
        "ground",
    }
    for kind in kinds:
        body = _symbol_body(CircuitComponent(id=kind, type=kind))
        assert 'class="unknown"' not in body


def test_invalid_circuit_does_not_emit_svg() -> None:
    circuit = CircuitIR.model_validate(
        {
            "components": [{"id": "bad", "type": "future_part", "ports": {"p": "n1"}}],
            "nets": [{"id": "n1"}],
        }
    )
    result = render_circuit(circuit)

    assert result.status == "failed"
    assert result.svg is None
    assert result.professional_renderer_success is False
    assert result.validation.render_status == "invalid"


def test_renderer_and_layout_failures_are_nonfatal_to_the_circuit_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    circuit = _golden_circuits()[0]

    def fail_layout(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("layout-injected")

    monkeypatch.setattr(renderer_module, "build_schematic_layout", fail_layout)
    layout_failure = render_circuit(circuit)
    assert layout_failure.status == "failed"
    assert layout_failure.svg is None
    assert layout_failure.professional_renderer_success is False

    monkeypatch.undo()

    def fail_render(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("render-injected")

    monkeypatch.setattr(renderer_module, "_render_svg", fail_render)
    render_failure = render_circuit(circuit)
    assert render_failure.status == "failed"
    assert render_failure.svg is None
    assert render_failure.professional_renderer_success is False


def _large_chain(component_count: int) -> CircuitIR:
    components: list[dict[str, object]] = [
        {
            "id": "v1",
            "type": "voltage_source",
            "ports": {"p": "n0", "n": "gnd"},
            "value": "5V",
        }
    ]
    for index in range(component_count):
        components.append(
            {
                "id": f"r{index}",
                "type": "resistor",
                "ports": {
                    "p": f"n{index}",
                    "n": ("gnd" if index == component_count - 1 else f"n{index + 1}"),
                },
                "value": "1k",
            }
        )
    components.append({"id": "gnd", "type": "ground", "ports": {"g": "gnd"}})
    net_ids = ["gnd", *[f"n{index}" for index in range(component_count)]]
    return CircuitIR.model_validate(
        {
            "components": components,
            "nets": [
                {
                    "id": net_id,
                    "kind": "reference" if net_id == "gnd" else "signal",
                }
                for net_id in net_ids
            ],
        }
    )


@pytest.mark.parametrize("component_count", [5, 10, 20, 30, 50])
def test_large_circuits_stay_bounded_and_renderable(component_count: int) -> None:
    result = render_circuit(_large_chain(component_count))
    assert result.status in {"rendered", "degraded"}
    assert result.svg is not None
    assert result.professional_renderer_success is True


def test_rendering_benchmark_has_50_cases_per_course_and_no_failed_renders() -> None:
    cases = _benchmark_cases()
    assert len(cases) == 150
    assert {
        course: sum(item[0] == course for item in cases)
        for course in ("CT", "AE", "DE")
    } == {
        "CT": 50,
        "AE": 50,
        "DE": 50,
    }
    for _course, circuit in cases:
        result = render_circuit(circuit, CircuitRenderOptions(template="logic_flow"))
        assert result.status in {"rendered", "degraded"}
        assert result.svg is not None
        assert result.renderer == "professional_svg"
        assert result.professional_renderer_success is True


@pytest.mark.parametrize("kind", ["and_gate", "d_flip_flop", "mux", "full_adder"])
def test_digital_benchmark_case_has_structured_ports(kind: str) -> None:
    circuit = _de_case(DIGITAL_TYPES.index(kind))
    component = next(item for item in circuit.components if item.type == kind)
    required, _ = PORT_CONTRACTS[kind]
    assert required <= set(component.ports)
