"""Validate the read-only Runtime readiness projections.

This check is intentionally provider-free.  It verifies that the Task Agent
and LearningLoop readiness APIs expose the evidence-state contract and that
the cross-entry Task capability projection agrees with its Agent projection.
It does not make a launch decision and never executes a task.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EVIDENCE_FIELDS = (
    "structural_release_eligible",
    "semantic_release_eligible",
    "canary_release_eligible",
)


def _read_json(base_url: str, path: str) -> dict[str, Any]:
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        headers={"Accept": "application/json"},
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310
        status = getattr(response, "status", 200)
        if status != 200:
            raise RuntimeError(f"readiness endpoint returned HTTP {status}")
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"readiness endpoint {path} must return an object")
    return payload


def _validate_item(
    item: object,
    *,
    label: str,
    identity_field: str,
    errors: list[str],
) -> str | None:
    if not isinstance(item, Mapping):
        errors.append(f"{label} must be an object")
        return None
    identity = item.get(identity_field)
    if not isinstance(identity, str) or not identity.strip():
        errors.append(f"{label}.{identity_field} is missing")
        identity = None
    for field in EVIDENCE_FIELDS:
        if not isinstance(item.get(field), bool):
            errors.append(f"{label}.{field} must be boolean")
    return identity


def validate_projections(
    *,
    task_payload: Mapping[str, Any],
    learning_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate already-fetched projection payloads without network access."""

    errors: list[str] = []
    if task_payload.get("provider_called") is not False:
        errors.append("task projection provider_called must be false")
    if learning_payload.get("provider_called") is not False:
        errors.append("learning projection provider_called must be false")

    agents = task_payload.get("agents")
    capabilities = task_payload.get("capabilities")
    learning_capabilities = learning_payload.get("capabilities")
    if not isinstance(agents, list):
        errors.append("task projection agents must be a list")
        agents = []
    if not isinstance(capabilities, list):
        errors.append("task projection capabilities must be a list")
        capabilities = []
    if not isinstance(learning_capabilities, list):
        errors.append("learning projection capabilities must be a list")
        learning_capabilities = []

    agent_by_id: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(agents):
        identity = _validate_item(
            item,
            label=f"task.agents[{index}]",
            identity_field="agent_id",
            errors=errors,
        )
        if identity and isinstance(item, Mapping):
            agent_by_id[identity] = item

    task_capability_count = 0
    for index, item in enumerate(capabilities):
        identity = _validate_item(
            item,
            label=f"task.capabilities[{index}]",
            identity_field="capability_id",
            errors=errors,
        )
        if not isinstance(item, Mapping) or item.get("domain") != "task_agent":
            continue
        task_capability_count += 1
        if identity is None:
            continue
        agent = agent_by_id.get(identity)
        if agent is None:
            errors.append(f"task capability {identity} has no Agent projection")
            continue
        for field in EVIDENCE_FIELDS:
            if item.get(field) != agent.get(field):
                errors.append(
                    f"task capability {identity}.{field} disagrees with Agent"
                )

    for index, item in enumerate(learning_capabilities):
        _validate_item(
            item,
            label=f"learning.capabilities[{index}]",
            identity_field="capability_id",
            errors=errors,
        )

    return {
        "provider_free": not errors
        or (
            task_payload.get("provider_called") is False
            and learning_payload.get("provider_called") is False
        ),
        "task_agent_count": len(agents),
        "task_capability_count": task_capability_count,
        "learning_capability_count": len(learning_capabilities),
        "errors": errors,
        "valid": not errors,
    }


def run(base_url: str) -> tuple[dict[str, Any], int]:
    """Fetch and validate both readiness projections."""

    try:
        task_payload = _read_json(base_url, "/api/v1/agents/runtime-readiness")
        learning_payload = _read_json(
            base_url, "/api/v1/learning/runtime-readiness"
        )
        report = validate_projections(
            task_payload=task_payload,
            learning_payload=learning_payload,
        )
    except (HTTPError, URLError, OSError, RuntimeError, ValueError) as exc:
        report = {
            "provider_free": True,
            "valid": False,
            "errors": [f"readiness_projection_check_failed: {exc}"],
        }
    return report, 0 if report["valid"] else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate provider-free Runtime readiness projections."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="API base URL without /api/v1",
    )
    return parser


def main(args: argparse.Namespace) -> int:
    report, exit_code = run(args.base_url)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(_parser().parse_args()))
