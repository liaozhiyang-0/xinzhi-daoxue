from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.package_learning_runtime_pair import build_pair_report, package_pair


def _report(*, mode: str, observed_runtime_route: bool) -> dict[str, Any]:
    runtime = {
        "status": "completed",
        "run_kind": "teaching_interaction",
        "state_version": 10,
        "approval_required": False,
        "resumable": False,
        "node_statuses": [
            {
                "node_id": "teaching.feedback.verify",
                "status": "succeeded",
                "effect_status": "completed",
                "attempt": 1,
                "error_code": "",
                "state_data": {"student_answer": "must-not-escape"},
            }
        ],
    }
    if mode == "legacy":
        runtime = {}
    return {
        "schema_version": "learning_runtime_authorized_dev_e2e.v1",
        "results": [
            {
                "case_id": "teaching_request_more_hint",
                "mode": mode,
                "task_id": "task-pair-001",
                "task_status": "completed",
                "action_status": "completed",
                "result_status": "completed",
                "observed_runtime_route": observed_runtime_route,
                "runtime": runtime,
                "runtime_status_history": ["waiting_approval", "completed"],
                "controls": [
                    {
                        "action": "approve",
                        "status": "completed",
                        "result_status": "completed",
                        "data": {"student_answer": "must-not-escape"},
                    }
                ],
                "checkpoints": {
                    "count": 2 if mode == "runtime" else 0,
                    "strictly_increasing": True,
                    "first_event_sequence": 20 if mode == "runtime" else None,
                    "last_event_sequence": 25 if mode == "runtime" else None,
                },
                "events": {
                    "count": 25,
                    "strictly_increasing": True,
                    "first_sequence": 1,
                    "last_sequence": 25,
                },
                "student_answer": "must-not-escape",
            }
        ],
    }


def test_learning_pair_packaging_is_structural_and_redacted(tmp_path: Path) -> None:
    report = build_pair_report(
        _report(mode="runtime", observed_runtime_route=True),
        _report(mode="legacy", observed_runtime_route=False),
    )

    assert report["structural_checks"] == {"passed": True, "reasons": []}
    assert report["release_ready"] is False
    assert report["semantic_review_required"] is True
    serialized = json.dumps(report, ensure_ascii=False)
    assert "student_answer" not in serialized
    assert report["runtime"]["controls"] == [
        {"action": "approve", "status": "completed", "result_status": "completed"}
    ]


def test_learning_pair_packaging_records_route_mismatch(tmp_path: Path) -> None:
    runtime = _report(mode="runtime", observed_runtime_route=False)
    legacy = _report(mode="legacy", observed_runtime_route=False)
    runtime_path = tmp_path / "runtime.json"
    legacy_path = tmp_path / "legacy.json"
    output = tmp_path / "pair.json"
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")

    report = package_pair(
        runtime_path,
        legacy_path,
        output,
        expected_case_id="teaching_request_more_hint",
    )

    assert report["structural_checks"]["passed"] is False
    assert "runtime_route_not_observed" in report["structural_checks"]["reasons"]
    assert json.loads(output.read_text(encoding="utf-8"))["release_ready"] is False
