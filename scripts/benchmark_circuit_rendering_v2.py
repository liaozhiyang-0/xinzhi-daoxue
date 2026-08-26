from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.circuit import (  # noqa: E402
    CircuitIR,
    CircuitRenderOptions,
    build_schematic_layout,
    render_circuit,
)
from app.circuit.contracts import PORT_CONTRACTS  # noqa: E402
from app.circuit.renderer import _symbol_body  # noqa: E402
from app.circuit.validator import validate_circuit  # noqa: E402
from app.services.circuit_visualization import observation_from_result  # noqa: E402


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    course: str
    category: str
    circuit: CircuitIR
    template: str


def _make_ct_case(index: int, category: str) -> BenchmarkCase:
    prefix = f"{category[:2]}{index}"
    if category == "rlc":
        components = [
            {
                "id": f"v{prefix}",
                "type": "voltage_source",
                "ports": {"p": "in", "n": "gnd"},
                "value": "5V",
            },
            {
                "id": f"r{prefix}",
                "type": "resistor",
                "ports": {"p": "in", "n": "n1"},
                "value": "1k",
            },
            {
                "id": f"l{prefix}",
                "type": "inductor",
                "ports": {"p": "n1", "n": "n2"},
                "value": "10mH",
            },
            {
                "id": f"c{prefix}",
                "type": "capacitor",
                "ports": {"p": "n2", "n": "gnd"},
                "value": "1uF",
            },
        ]
        nets = ["in", "n1", "n2", "gnd"]
        template = "rlc_series"
    elif category == "dependent":
        components = [
            {
                "id": f"e{prefix}",
                "type": "dependent_voltage_source",
                "ports": {"p": "out", "n": "gnd", "cp": "sense_p", "cn": "sense_n"},
                "value": "2",
            },
            {
                "id": f"r{prefix}",
                "type": "resistor",
                "ports": {"p": "sense_p", "n": "sense_n"},
                "value": "1k",
            },
            {
                "id": f"load{prefix}",
                "type": "resistor",
                "ports": {"p": "out", "n": "gnd"},
                "value": "2k",
            },
        ]
        nets = ["out", "sense_p", "sense_n", "gnd"]
        template = "generic_left_to_right"
    elif category == "bridge":
        components = [
            {
                "id": f"v{prefix}",
                "type": "voltage_source",
                "ports": {"p": "in", "n": "gnd"},
                "value": "5V",
            },
            {
                "id": f"r1{prefix}",
                "type": "resistor",
                "ports": {"p": "in", "n": "left"},
                "value": "1k",
            },
            {
                "id": f"r2{prefix}",
                "type": "resistor",
                "ports": {"p": "left", "n": "gnd"},
                "value": "2k",
            },
            {
                "id": f"r3{prefix}",
                "type": "resistor",
                "ports": {"p": "in", "n": "right"},
                "value": "3k",
            },
            {
                "id": f"r4{prefix}",
                "type": "resistor",
                "ports": {"p": "right", "n": "gnd"},
                "value": "4k",
            },
            {
                "id": f"rb{prefix}",
                "type": "resistor",
                "ports": {"p": "left", "n": "right"},
                "value": "5k",
            },
        ]
        nets = ["in", "left", "right", "gnd"]
        template = "bridge"
    elif category == "coupled_special":
        components = [
            {
                "id": f"v{prefix}",
                "type": "voltage_source",
                "ports": {"p": "in", "n": "gnd1"},
                "value": "5V",
            },
            {
                "id": f"k{prefix}",
                "type": "coupled_inductor",
                "ports": {
                    "p1": "in",
                    "n1": "gnd1",
                    "p2": "out",
                    "n2": "gnd2",
                },
                "value": "k=0.9",
            },
            {
                "id": f"r{prefix}",
                "type": "resistor",
                "ports": {"p": "out", "n": "gnd2"},
                "value": "1k",
            },
        ]
        components.extend(
            [
                {"id": f"g1{prefix}", "type": "ground", "ports": {"g": "gnd1"}},
                {"id": f"g2{prefix}", "type": "ground", "ports": {"g": "gnd2"}},
            ]
        )
        nets = ["in", "out", "gnd1", "gnd2"]
        template = "generic_left_to_right"
    else:
        components = [
            {
                "id": f"v{prefix}",
                "type": "voltage_source",
                "ports": {"p": "in", "n": "gnd"},
                "value": "5V",
            },
            {
                "id": f"r1{prefix}",
                "type": "resistor",
                "ports": {"p": "in", "n": "mid"},
                "value": "1k",
            },
            {
                "id": f"r2{prefix}",
                "type": "resistor",
                "ports": {"p": "mid", "n": "gnd"},
                "value": "2k",
            },
        ]
        if category == "kcl_kvl":
            components.append(
                {
                    "id": f"i{prefix}",
                    "type": "current_source",
                    "ports": {"p": "mid", "n": "gnd"},
                    "value": "1mA",
                }
            )
        elif category == "thevenin_norton":
            components.append(
                {
                    "id": f"rl{prefix}",
                    "type": "resistor",
                    "ports": {"p": "mid", "n": "gnd"},
                    "value": "3k",
                }
            )
        else:
            components.append(
                {
                    "id": f"s{prefix}",
                    "type": "switch",
                    "ports": {"p": "mid", "n": "gnd"},
                    "value": "open",
                }
            )
        nets = ["in", "mid", "gnd"]
        template = (
            "divider"
            if category in {"simple_series_parallel", "thevenin_norton"}
            else "generic_left_to_right"
        )
    if category != "coupled_special":
        components.append({"id": f"g{prefix}", "type": "ground", "ports": {"g": "gnd"}})
    return BenchmarkCase(
        "CT",
        category,
        CircuitIR.model_validate(
            {
                "components": components,
                "nets": [
                    {"id": item, "kind": "reference" if item == "gnd" else "signal"}
                    for item in nets
                ],
            }
        ),
        template,
    )


def _make_ae_case(index: int, category: str) -> BenchmarkCase:
    prefix = f"{category[:2]}{index}"
    if category == "diode":
        components = [
            {
                "id": f"v{prefix}",
                "type": "voltage_source",
                "ports": {"p": "in", "n": "gnd"},
                "value": "5V",
            },
            {
                "id": f"d{prefix}",
                "type": "diode",
                "ports": {"a": "in", "k": "out"},
                "value": "Si",
            },
            {
                "id": f"r{prefix}",
                "type": "resistor",
                "ports": {"p": "out", "n": "gnd"},
                "value": "1k",
            },
        ]
        template = "series"
    elif category in {"bjt", "bias"}:
        components = [
            {
                "id": f"q{prefix}",
                "type": "bjt",
                "ports": {"b": "base", "c": "collector", "e": "gnd"},
                "parameters": {"symbol_variant": "npn" if category == "bjt" else "pnp"},
            },
            {
                "id": f"rb{prefix}",
                "type": "resistor",
                "ports": {"p": "in", "n": "base"},
                "value": "100k",
            },
            {
                "id": f"rc{prefix}",
                "type": "resistor",
                "ports": {"p": "vcc", "n": "collector"},
                "value": "2k",
            },
            {
                "id": f"v{prefix}",
                "type": "voltage_source",
                "ports": {"p": "vcc", "n": "gnd"},
                "value": "12V",
            },
            {"id": f"in{prefix}", "type": "input", "ports": {"p": "in"}},
        ]
        template = "transistor_stage"
    elif category in {"mos", "small_signal"}:
        components = [
            {
                "id": f"m{prefix}",
                "type": "mosfet",
                "ports": {"g": "gate", "d": "drain", "s": "gnd"},
                "parameters": {"symbol_variant": "nmos", "gm": "0.01S"},
            },
            {
                "id": f"rg{prefix}",
                "type": "resistor",
                "ports": {"p": "in", "n": "gate"},
                "value": "1M",
            },
            {
                "id": f"rd{prefix}",
                "type": "resistor",
                "ports": {"p": "vdd", "n": "drain"},
                "value": "2k",
            },
            {
                "id": f"v{prefix}",
                "type": "voltage_source",
                "ports": {"p": "vdd", "n": "gnd"},
                "value": "5V",
            },
            {"id": f"in{prefix}", "type": "input", "ports": {"p": "in"}},
        ]
        template = "small_signal" if category == "small_signal" else "transistor_stage"
    else:
        components = [
            {
                "id": f"a{prefix}",
                "type": "opamp",
                "ports": {
                    "plus": "in",
                    "minus": "fb",
                    "out": "out",
                    "vplus": "vcc",
                    "vminus": "gnd",
                },
                "parameters": {"model": "ideal"},
            },
            {
                "id": f"rin{prefix}",
                "type": "resistor",
                "ports": {"p": "input", "n": "fb"},
                "value": "10k",
            },
            {
                "id": f"rf{prefix}",
                "type": "resistor",
                "ports": {"p": "fb", "n": "out"},
                "value": "100k",
            },
            {"id": f"in{prefix}", "type": "input", "ports": {"p": "input"}},
        ]
        if category == "feedback":
            components.append(
                {
                    "id": f"c{prefix}",
                    "type": "capacitor",
                    "ports": {"p": "out", "n": "fb"},
                    "value": "10pF",
                }
            )
        template = (
            "opamp_feedback" if category in {"feedback", "opamp"} else "opamp_inverting"
        )
    components.append({"id": f"g{prefix}", "type": "ground", "ports": {"g": "gnd"}})
    net_ids = sorted({net for item in components for net in item["ports"].values()})
    return BenchmarkCase(
        "AE",
        category,
        CircuitIR.model_validate(
            {
                "components": components,
                "nets": [
                    {
                        "id": item,
                        "kind": "reference"
                        if item == "gnd"
                        else "power"
                        if item in {"vcc", "vdd"}
                        else "signal",
                    }
                    for item in net_ids
                ],
            }
        ),
        template,
    )


def _make_de_case(index: int, category: str) -> BenchmarkCase:
    prefix = f"{category[:2]}{index}"
    kinds = {
        "basic_gates": (
            "and_gate",
            "or_gate",
            "not_gate",
            "nand_gate",
            "nor_gate",
            "xor_gate",
            "xnor_gate",
            "buffer",
            "schmitt_trigger",
            "and_gate",
        ),
        "combinational": (
            "half_adder",
            "full_adder",
            "encoder",
            "decoder",
            "demux",
            "half_adder",
            "full_adder",
            "encoder",
            "decoder",
            "demux",
        ),
        "mux_decoder": (
            "mux",
            "decoder",
            "mux",
            "decoder",
            "mux",
            "demux",
            "encoder",
            "decoder",
            "mux",
            "demux",
        ),
        "flip_flop": (
            "d_flip_flop",
            "jk_flip_flop",
            "t_flip_flop",
            "sr_latch",
            "d_flip_flop",
            "jk_flip_flop",
            "t_flip_flop",
            "sr_latch",
            "d_flip_flop",
            "jk_flip_flop",
        ),
        "timing": (
            "clock",
            "buffer",
            "schmitt_trigger",
            "clock",
            "and_gate",
            "clock",
            "buffer",
            "schmitt_trigger",
            "clock",
            "and_gate",
        ),
    }
    kind = kinds[category][index % 10]
    required, optional = PORT_CONTRACTS[kind]
    ports = {port: f"n{prefix}_{port}" for port in sorted(required | optional)}
    components: list[dict[str, object]] = [
        {"id": f"u{prefix}", "type": kind, "ports": ports}
    ]
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
    for port, net_id in ports.items():
        endpoint_type = "logic_output" if port in output_ports else "logic_input"
        components.append(
            {
                "id": f"{endpoint_type}_{prefix}_{port}",
                "type": endpoint_type,
                "ports": {"p": net_id},
            }
        )
    net_ids = sorted(ports.values())
    return BenchmarkCase(
        "DE",
        category,
        CircuitIR.model_validate(
            {
                "components": components,
                "nets": [{"id": item, "kind": "signal"} for item in net_ids],
            }
        ),
        "logic_flow",
    )


def coverage_cases() -> list[BenchmarkCase]:
    distributions = {
        "CT": {
            "simple_series_parallel": 10,
            "kcl_kvl": 10,
            "thevenin_norton": 10,
            "rlc": 5,
            "dependent": 5,
            "bridge": 5,
            "coupled_special": 5,
        },
        "AE": {
            "diode": 5,
            "bjt": 10,
            "mos": 10,
            "opamp": 10,
            "feedback": 5,
            "bias": 5,
            "small_signal": 5,
        },
        "DE": {
            "basic_gates": 10,
            "combinational": 10,
            "mux_decoder": 10,
            "flip_flop": 10,
            "timing": 10,
        },
    }
    result: list[BenchmarkCase] = []
    for course, groups in distributions.items():
        for category, count in groups.items():
            for index in range(count):
                result.append(
                    _make_ct_case(index, category)
                    if course == "CT"
                    else _make_ae_case(index, category)
                    if course == "AE"
                    else _make_de_case(index, category)
                )
    return result


def semantic_metrics(cases: list[BenchmarkCase]) -> dict[str, float]:
    totals = {
        key: 0
        for key in (
            "components",
            "types",
            "values",
            "nodes",
            "branches",
            "polarity",
            "ports",
            "renders",
        )
    }
    hits = dict(totals)
    for case in cases:
        circuit = case.circuit
        layout = build_schematic_layout(circuit, case.template)
        rendered = render_circuit(circuit, CircuitRenderOptions(template=case.template))
        expected_components = {item.id for item in circuit.components}
        rendered_components = {item.component_id for item in layout.placements}
        totals["components"] += len(expected_components)
        hits["components"] += len(expected_components & rendered_components)
        totals["types"] += len(circuit.components)
        hits["types"] += sum(
            'class="unknown"' not in _symbol_body(item) for item in circuit.components
        )
        value_items = [item for item in circuit.components if item.value is not None]
        totals["values"] += len(value_items)
        hits["values"] += sum(
            str(item.value) in (rendered.svg or "") for item in value_items
        )
        expected_nodes = {
            net_id for item in circuit.components for net_id in item.ports.values()
        }
        actual_nodes = {item.net_id for item in layout.ports}
        totals["nodes"] += len(expected_nodes)
        hits["nodes"] += len(expected_nodes & actual_nodes)
        expected_branches = {
            item.id
            for item in circuit.nets
            if sum(
                item.id == net
                for component in circuit.components
                for net in component.ports.values()
            )
            >= 2
        }
        actual_branches = {item.net_id for item in layout.wires}
        totals["branches"] += len(expected_branches)
        hits["branches"] += len(expected_branches & actual_branches)
        source_count = sum(
            item.type in {"voltage_source", "dependent_voltage_source"}
            for item in circuit.components
        )
        totals["polarity"] += source_count
        hits["polarity"] += min(source_count, len(layout.polarity_markers))
        expected_ports = {
            (item.id, port) for item in circuit.components for port in item.ports
        }
        actual_ports = {(item.component_id, item.port) for item in layout.ports}
        totals["ports"] += len(expected_ports)
        hits["ports"] += len(expected_ports & actual_ports)
        hits["renders"] += int(
            rendered.svg is not None and rendered.professional_renderer_success
        )
        totals["renders"] += 1
    names = {
        "components": "ComponentRecall",
        "types": "ComponentTypeAccuracy",
        "values": "ValueAccuracy",
        "nodes": "NodeAccuracy",
        "branches": "BranchAccuracy",
        "polarity": "PolarityAccuracy",
        "ports": "PortAccuracy",
        "renders": "RenderSuccess",
    }
    return {
        names[key]: round(100 * hits[key] / totals[key], 2) if totals[key] else 100.0
        for key in names
    }


def representative_cases() -> list[tuple[str, CircuitIR, str]]:
    return [
        (
            "CT",
            CircuitIR.model_validate(
                {
                    "components": [
                        {
                            "id": "v1",
                            "type": "voltage_source",
                            "ports": {"p": "vin", "n": "gnd"},
                            "value": "5 V",
                        },
                        {
                            "id": "r1",
                            "type": "resistor",
                            "ports": {"p": "vin", "n": "vout"},
                            "value": "1 kΩ",
                        },
                        {
                            "id": "r2",
                            "type": "resistor",
                            "ports": {"p": "vout", "n": "gnd"},
                            "value": "1 kΩ",
                        },
                        {"id": "gnd", "type": "ground", "ports": {"g": "gnd"}},
                    ],
                    "nets": [
                        {"id": "vin", "kind": "power"},
                        {"id": "vout", "kind": "signal", "label": "Vmid"},
                        {"id": "gnd", "kind": "reference"},
                    ],
                    "topology_hint": "divider",
                }
            ),
            "divider",
        ),
        (
            "AE",
            CircuitIR.model_validate(
                {
                    "components": [
                        {
                            "id": "op1",
                            "type": "opamp",
                            "ports": {
                                "plus": "in",
                                "minus": "fb",
                                "out": "out",
                                "vplus": "vcc",
                                "vminus": "gnd",
                            },
                            "label": "A1",
                        },
                        {
                            "id": "rin",
                            "type": "resistor",
                            "ports": {"p": "in", "n": "fb"},
                            "value": "10 kΩ",
                        },
                        {
                            "id": "rf",
                            "type": "resistor",
                            "ports": {"p": "fb", "n": "out"},
                            "value": "100 kΩ",
                        },
                    ],
                    "nets": [
                        {"id": "in"},
                        {"id": "fb"},
                        {"id": "out", "label": "vo"},
                        {"id": "vcc", "kind": "power"},
                        {"id": "gnd", "kind": "reference"},
                    ],
                    "topology_hint": "opamp_inverting",
                }
            ),
            "opamp_inverting",
        ),
        (
            "DE",
            CircuitIR.model_validate(
                {
                    "components": [
                        {
                            "id": "u1",
                            "type": "and_gate",
                            "ports": {"in1": "a", "in2": "b", "out": "y"},
                            "label": "U1",
                        },
                        {"id": "a", "type": "logic_input", "ports": {"p": "a"}},
                        {"id": "b", "type": "logic_input", "ports": {"p": "b"}},
                        {"id": "y", "type": "logic_output", "ports": {"p": "y"}},
                    ],
                    "nets": [
                        {"id": "a"},
                        {"id": "b"},
                        {"id": "y"},
                    ],
                    "topology_hint": "logic_flow",
                }
            ),
            "logic_flow",
        ),
    ]


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[index]


def measure(
    name: str,
    operation: Callable[[], Any],
    iterations: int,
) -> dict[str, float | int | str]:
    samples: list[float] = []
    for _ in range(iterations):
        started = perf_counter()
        operation()
        samples.append((perf_counter() - started) * 1000)
    return {
        "name": name,
        "iterations": iterations,
        "p50_ms": round(percentile(samples, 0.50), 3),
        "p95_ms": round(percentile(samples, 0.95), 3),
        "p99_ms": round(percentile(samples, 0.99), 3),
        "mean_ms": round(statistics.mean(samples), 3),
        "max_ms": round(max(samples), 3),
    }


def run(iterations: int) -> dict[str, Any]:
    cases = representative_cases()
    coverage = coverage_cases()
    timings: list[dict[str, float | int | str]] = []
    total_renders = 0
    for course, circuit, template in cases:
        options = CircuitRenderOptions(template=template)
        timings.extend(
            [
                measure(
                    f"{course}.validation",
                    lambda circuit=circuit: validate_circuit(circuit),
                    iterations,
                ),
                measure(
                    f"{course}.layout",
                    lambda circuit=circuit, template=template: build_schematic_layout(
                        circuit, template
                    ),
                    iterations,
                ),
                measure(
                    f"{course}.render_and_project",
                    lambda circuit=circuit, options=options: observation_from_result(
                        circuit, render_circuit(circuit, options)
                    ),
                    iterations,
                ),
            ]
        )
        total_renders += iterations
    coverage_failures = [
        {
            "course": case.course,
            "category": case.category,
            "status": result.status,
        }
        for case in coverage
        for result in [
            render_circuit(case.circuit, CircuitRenderOptions(template=case.template))
        ]
        if result.svg is None or not result.professional_renderer_success
    ]
    total_renders += len(coverage)
    return {
        "schema": "circuit_rendering_v2_benchmark.v1",
        "iterations_per_case": iterations,
        "representative_cases": len(cases),
        "coverage_cases": len(coverage),
        "coverage_distribution": {
            f"{case.course}.{case.category}": sum(
                item.course == case.course and item.category == case.category
                for item in coverage
            )
            for case in coverage
        },
        "total_continuous_renders": total_renders,
        "failures": coverage_failures,
        "metrics": semantic_metrics(coverage),
        "timings": timings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark deterministic CircuitIR SVG rendering"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Iterations per representative case",
    )
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    print(json.dumps(run(args.iterations), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
