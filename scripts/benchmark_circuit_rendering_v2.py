from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Callable
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
from app.circuit.validator import validate_circuit  # noqa: E402
from app.services.circuit_visualization import observation_from_result  # noqa: E402


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
    failures = [
        {
            "course": course,
            "status": render_circuit(
                circuit, CircuitRenderOptions(template=template)
            ).status,
        }
        for course, circuit, template in cases
        if render_circuit(circuit, CircuitRenderOptions(template=template)).svg is None
    ]
    return {
        "schema": "circuit_rendering_v2_benchmark.v1",
        "iterations_per_case": iterations,
        "representative_cases": len(cases),
        "total_continuous_renders": total_renders,
        "failures": failures,
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
