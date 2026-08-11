from __future__ import annotations

import json
from typing import Any

from scripts.check_runtime_readiness_projection import (
    run,
    validate_projections,
)


def _payloads() -> tuple[dict[str, Any], dict[str, Any]]:
    agent = {
        "agent_id": "GENERAL_QUESTION_V1",
        "structural_release_eligible": True,
        "semantic_release_eligible": False,
        "canary_release_eligible": False,
    }
    capability = {
        "capability_id": "GENERAL_QUESTION_V1",
        "domain": "task_agent",
        **{field: agent[field] for field in (
            "structural_release_eligible",
            "semantic_release_eligible",
            "canary_release_eligible",
        )},
    }
    return (
        {
            "provider_called": False,
            "agents": [agent],
            "capabilities": [capability],
        },
        {
            "provider_called": False,
            "capabilities": [
                {
                    "capability_id": "LEARNING_PROGRESS_V1",
                    "domain": "learning_loop",
                    "structural_release_eligible": False,
                    "semantic_release_eligible": False,
                    "canary_release_eligible": False,
                }
            ],
        },
    )


def test_validate_projections_checks_cross_entry_evidence_state() -> None:
    task, learning = _payloads()

    report = validate_projections(
        task_payload=task,
        learning_payload=learning,
    )

    assert report["valid"] is True
    assert report["provider_free"] is True
    assert report["task_agent_count"] == 1
    assert report["task_capability_count"] == 1
    assert report["learning_capability_count"] == 1


def test_validate_projections_rejects_mismatched_capability_state() -> None:
    task, learning = _payloads()
    task["capabilities"][0]["semantic_release_eligible"] = True

    report = validate_projections(
        task_payload=task,
        learning_payload=learning,
    )

    assert report["valid"] is False
    assert any("disagrees with Agent" in item for item in report["errors"])


def test_validate_projections_rejects_provider_execution_signal() -> None:
    task, learning = _payloads()
    task["provider_called"] = True

    report = validate_projections(
        task_payload=task,
        learning_payload=learning,
    )

    assert report["valid"] is False
    assert report["provider_free"] is False
    assert "provider_called must be false" in report["errors"][0]


def test_run_fetches_both_readiness_endpoints_without_exposing_payloads(
    monkeypatch,
) -> None:
    task, learning = _payloads()
    calls: list[str] = []

    class _Response:
        status = 200

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"{}"

    def fake_urlopen(request: Any, *, timeout: int) -> _Response:
        del timeout
        calls.append(request.full_url)
        response = _Response()
        response.read = lambda: json.dumps(
            task if request.full_url.endswith("agents/runtime-readiness") else learning
        ).encode("utf-8")
        return response

    monkeypatch.setattr(
        "scripts.check_runtime_readiness_projection.urlopen",
        fake_urlopen,
    )

    report, exit_code = run("http://localhost:8000")

    assert exit_code == 0
    assert report["valid"] is True
    assert calls == [
        "http://localhost:8000/api/v1/agents/runtime-readiness",
        "http://localhost:8000/api/v1/learning/runtime-readiness",
    ]
