from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.circuit import (
    CircuitIR,
    CircuitRenderOptions,
    circuit_render_tool,
    render_circuit,
    validate_circuit,
)
from app.tools.registry import default_tool_registry

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "circuit_golden_cases.json"


def cases() -> list[dict[str, object]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def circuit_from_case(case: dict[str, object]) -> CircuitIR:
    return CircuitIR.model_validate({key: case[key] for key in ("components", "nets")})


@pytest.mark.parametrize("case", cases(), ids=lambda item: str(item["id"]))
def test_golden_circuit_validates(case: dict[str, object]) -> None:
    circuit = circuit_from_case(case)

    report = validate_circuit(circuit)

    assert report.status == "validated"
    assert not [issue for issue in report.issues if issue.severity == "error"]
    assert circuit.validation_state == "validated"


def test_validator_catches_contract_and_topology_errors() -> None:
    circuit = CircuitIR.model_validate(
        {
            "components": [
                {
                    "id": "r1",
                    "type": "resistor",
                    "ports": {"p": "missing", "n": "same"},
                },
                {"id": "r1", "type": "resistor", "ports": {"p": "same", "n": "same"}},
                {"id": "missing", "type": "resistor", "ports": {}},
                {"id": "bad", "type": "future_part", "ports": {}},
            ],
            "nets": [{"id": "same"}],
        }
    )

    report = validate_circuit(circuit)
    codes = {issue.code for issue in report.issues}

    assert report.status == "invalid"
    assert {
        "duplicate_component_id",
        "invalid_component_type",
        "required_port_missing",
        "invalid_net_ref",
        "self_connection",
    } <= codes


def test_critical_topology_uncertainty_cannot_be_validated() -> None:
    circuit = CircuitIR.model_validate(
        {
            "components": [
                {"id": "r1", "type": "resistor", "ports": {"p": "in", "n": "gnd"}},
                {"id": "gnd", "type": "ground", "ports": {"g": "gnd"}},
            ],
            "nets": [{"id": "in"}, {"id": "gnd"}],
            "uncertainties": [
                {
                    "id": "u1",
                    "message": "输入端拓扑来自 OCR，未确认",
                    "severity": "critical",
                    "net_ids": ["in"],
                }
            ],
        }
    )

    report = validate_circuit(circuit)

    assert report.status == "uncertain"
    assert "critical_uncertainty:u1" in report.warnings


@pytest.mark.parametrize("case", cases()[:4], ids=lambda item: str(item["id"]))
def test_renderer_returns_svg_without_raising(case: dict[str, object]) -> None:
    circuit = circuit_from_case(case)

    result = render_circuit(
        circuit, CircuitRenderOptions(template=str(case["template"]))
    )

    assert result.status in {"rendered", "degraded"}
    assert result.svg is not None
    assert result.svg.startswith("<svg") or "<svg" in result.svg
    assert result.validation_state == "validated"


def test_renderer_failure_is_non_fatal() -> None:
    circuit = CircuitIR.model_validate(
        {
            "components": [
                {
                    "id": "r1",
                    "type": "resistor",
                    "ports": {"p": "missing", "n": "missing"},
                }
            ],
            "nets": [{"id": "missing"}],
        }
    )

    result = render_circuit(circuit)

    assert result.status == "failed"
    assert result.svg is None
    assert result.validation_state == "invalid"
    assert result.validation.issues


def test_tool_contract_and_registry_are_controlled() -> None:
    golden = cases()[0]
    payload = {
        "circuit": {key: golden[key] for key in ("components", "nets")},
        "render_options": {"template": "series"},
    }
    result = circuit_render_tool(payload)
    registry = default_tool_registry()
    controlled = default_tool_registry(circuit_render_enabled=True)

    assert result["status"] in {"rendered", "degraded"}
    assert registry.describe("circuit.render").enabled is False
    assert controlled.describe("circuit.render").enabled is True
    assert controlled.get("circuit.render") is circuit_render_tool
