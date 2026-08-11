from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.package_learning_runtime_pair_bundle import build_bundle, package_bundle


def _report(*, case_id: str, mode: str) -> dict[str, object]:
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
                "case_id": case_id,
                "mode": mode,
                "task_id": f"task-{case_id}",
                "result_status": "completed",
                "observed_runtime_route": mode == "runtime",
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
                },
                "events": {
                    "count": 25,
                    "strictly_increasing": True,
                },
                "student_answer": "must-not-escape",
            }
        ],
    }


def test_learning_pair_bundle_is_multi_case_and_redacted() -> None:
    bundle = build_bundle(
        [
            _report(case_id="case-a", mode="runtime"),
            _report(case_id="case-b", mode="runtime"),
        ],
        [
            _report(case_id="case-a", mode="legacy"),
            _report(case_id="case-b", mode="legacy"),
        ],
        bundle_id="learning-dev-bundle-001",
    )

    assert bundle["case_count"] == 2
    assert bundle["case_ids"] == ["case-a", "case-b"]
    assert bundle["structural_checks"] == {"passed": True, "reasons": []}
    assert bundle["release_ready"] is False
    serialized = json.dumps(bundle, ensure_ascii=False)
    assert "student_answer" not in serialized
    assert "must-not-escape" not in serialized


def test_learning_pair_bundle_rejects_duplicate_case_ids() -> None:
    bundle = build_bundle(
        [
            _report(case_id="case-a", mode="runtime"),
            _report(case_id="case-a", mode="runtime"),
        ],
        [
            _report(case_id="case-a", mode="legacy"),
            _report(case_id="case-a", mode="legacy"),
        ],
        bundle_id="learning-dev-bundle-duplicate",
    )

    assert bundle["structural_checks"]["passed"] is False
    assert "duplicate_case_id:case-a" in bundle["structural_checks"]["reasons"]
    assert bundle["release_ready"] is False


def test_learning_pair_bundle_requires_matching_report_counts() -> None:
    with pytest.raises(ValueError, match="same non-zero count"):
        build_bundle(
            [_report(case_id="case-a", mode="runtime")],
            [],
            bundle_id="learning-dev-bundle-mismatch",
        )


def test_learning_pair_bundle_writes_a_safe_json_artifact(tmp_path: Path) -> None:
    runtime_path = tmp_path / "runtime.json"
    legacy_path = tmp_path / "legacy.json"
    output_path = tmp_path / "bundle.json"
    runtime_path.write_text(
        json.dumps(_report(case_id="case-a", mode="runtime")),
        encoding="utf-8",
    )
    legacy_path.write_text(
        json.dumps(_report(case_id="case-a", mode="legacy")),
        encoding="utf-8",
    )

    bundle = package_bundle(
        [runtime_path],
        [legacy_path],
        output_path,
        bundle_id="learning-dev-bundle-file",
    )

    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf-8"))["case_count"] == 1
    assert bundle["release_ready"] is False
