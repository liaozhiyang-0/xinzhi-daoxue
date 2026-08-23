from __future__ import annotations

from collections.abc import Mapping

from app.circuit.contracts import CircuitRenderRequest
from app.circuit.renderer import render_circuit


def circuit_render_tool(
    payload: CircuitRenderRequest | Mapping[str, object],
) -> dict[str, object]:
    """Return a JSON-safe render result for a registry payload."""

    try:
        request = (
            payload
            if isinstance(payload, CircuitRenderRequest)
            else CircuitRenderRequest.model_validate(payload)
        )
        result = render_circuit(request.circuit, request.render_options)
    except Exception as exc:
        return {
            "status": "failed",
            "svg": None,
            "artifact_ref": None,
            "validation_state": "invalid",
            "warnings": [f"tool_contract_failure:{type(exc).__name__}"],
            "validation": {"status": "invalid", "issues": [], "warnings": []},
            "render_latency_ms": 0.0,
            "renderer": "none",
        }
    return result.model_dump(mode="json")
