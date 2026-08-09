from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeCheckpointRecord,
    RuntimeLaunchSnapshot,
    RuntimeNode,
)
from app.runtime.semantic_evidence import payload_sha256

from scripts.collect_runtime_canary import build_suite, build_suite_from_manifest

ROOT = Path(__file__).resolve().parents[3]
COLLECTOR = ROOT / "scripts" / "collect_runtime_canary.py"


def test_build_suite_requires_a_structurally_valid_paired_trace() -> None:
    run = AgentRun(
        run_id="run-collection",
        task_id="task-collection",
        goal="collect",
        plan=AgentRunPlan(
            plan_id="plan-collection",
            version="general-qa-v1",
            goal="collect",
            nodes=[
                RuntimeNode(
                    node_id="final",
                    node_type="terminal",
                    handler_id="runtime.final",
                )
            ],
        ),
        launch_decision=RuntimeLaunchSnapshot(
            agent_id="GENERAL_QUESTION_V1",
            mode="canary",
            source="test",
            reason="paired trace test",
        ),
    )
    checkpoints = [
        RuntimeCheckpointRecord(
            sequence=1,
            state_version=1,
            state_data=run.model_dump(mode="json"),
        ).model_dump(mode="json")
    ]

    suite = build_suite(
        agent_id="GENERAL_QUESTION_V1",
        suite_id="collection-suite",
        case_id="collection-case",
        authorization_ref="change-collection-1",
        captured_at=datetime(2026, 8, 9, tzinfo=UTC),
        input_payload={"question": "private collection input"},
        agent_version="1.0",
        runtime_plan_version="general-qa-v1",
        legacy_payload={
            "agent_id": "GENERAL_QUESTION_V1",
            "status": "completed",
            "answer": "same",
        },
        runtime_payload={
            "agent_id": "GENERAL_QUESTION_V1",
            "status": "completed",
            "answer": "same",
        },
        runtime_checkpoints=checkpoints,
    )

    assert suite.evidence.kind == "authorized_paired"
    assert suite.evidence.release_ready is True
    assert suite.pairs[0].runtime_checkpoints == checkpoints
    assert suite.pairs[0].input_sha256 == payload_sha256(
        {"question": "private collection input"}
    )
    assert "private collection input" not in suite.model_dump_json()


def test_build_suite_rejects_an_invalid_trace() -> None:
    with pytest.raises(ValueError, match="not release eligible"):
        build_suite(
            agent_id="GENERAL_QUESTION_V1",
            agent_version="1.0",
            runtime_plan_version="general-qa-v1",
            suite_id="invalid-suite",
            case_id="invalid-case",
            authorization_ref="change-invalid-1",
            captured_at=datetime(2026, 8, 9, tzinfo=UTC),
            input_payload={"question": "private invalid input"},
            legacy_payload={"status": "completed", "answer": "same"},
            runtime_payload={"status": "completed", "answer": "same"},
            runtime_checkpoints=[],
        )


def _write_case_files(root: Path, case_id: str) -> None:
    (root / f"{case_id}-input.json").write_text(
        json.dumps({"question": f"private-{case_id}"}), encoding="utf-8"
    )
    payload = {
        "agent_id": "GENERAL_QUESTION_V1",
        "status": "completed",
        "answer": f"answer-{case_id}",
    }
    (root / f"{case_id}-legacy.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / f"{case_id}-runtime.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / f"{case_id}-checkpoints.json").write_text(
        json.dumps({"checkpoints": _checkpoints_for_manifest()}),
        encoding="utf-8",
    )


def _checkpoints_for_manifest() -> list[dict[str, object]]:
    run = AgentRun(
        run_id="run-manifest",
        task_id="task-manifest",
        goal="manifest canary",
        plan=AgentRunPlan(
            plan_id="plan-manifest",
            version="general-qa-v1",
            goal="manifest canary",
            nodes=[
                RuntimeNode(
                    node_id="final",
                    node_type="terminal",
                    handler_id="runtime.final",
                )
            ],
        ),
        launch_decision=RuntimeLaunchSnapshot(
            agent_id="GENERAL_QUESTION_V1",
            mode="canary",
            source="test",
            reason="manifest fixture",
        ),
    )
    return [
        RuntimeCheckpointRecord(
            sequence=1,
            state_version=1,
            state_data=run.model_dump(mode="json"),
        ).model_dump(mode="json")
    ]


def _manifest(case_ids: list[str]) -> dict[str, object]:
    return {
        "schema_version": "runtime_canary_manifest.v2",
        "agent_id": "GENERAL_QUESTION_V1",
        "agent_version": "1.0",
        "runtime_plan_version": "general-qa-v1",
        "suite_id": "manifest-suite",
        "authorization_ref": "change-manifest-1",
        "captured_at": "2026-08-09T00:00:00+08:00",
        "cases": [
            {
                "case_id": case_id,
                "input": f"{case_id}-input.json",
                "legacy": f"{case_id}-legacy.json",
                "runtime": f"{case_id}-runtime.json",
                "checkpoints": f"{case_id}-checkpoints.json",
            }
            for case_id in case_ids
        ],
    }


def test_manifest_builds_one_authorized_suite_for_multiple_cases(
    tmp_path: Path,
) -> None:
    _write_case_files(tmp_path, "case-a")
    _write_case_files(tmp_path, "case-b")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest(["case-a", "case-b"])), encoding="utf-8"
    )

    suite = build_suite_from_manifest(manifest_path)

    assert suite.suite_version == "2"
    assert suite.evidence.kind == "authorized_paired"
    assert suite.evidence.release_ready is True
    assert [pair.case_id for pair in suite.pairs] == ["case-a", "case-b"]
    assert all(pair.input_sha256 for pair in suite.pairs)
    assert "private-case-a" not in suite.model_dump_json()
    assert "private-case-b" not in suite.model_dump_json()
    assert "schema_version" not in suite.model_dump(mode="json")


def test_manifest_v1_is_rejected_after_input_binding_protocol_upgrade(
    tmp_path: Path,
) -> None:
    _write_case_files(tmp_path, "legacy-v1")
    manifest = _manifest(["legacy-v1"])
    manifest["schema_version"] = "runtime_canary_manifest.v1"
    manifest_path = tmp_path / "manifest-v1.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="runtime_canary_manifest.v2"):
        build_suite_from_manifest(manifest_path)


def test_manifest_cli_supports_multi_case_input_without_provider(
    tmp_path: Path,
) -> None:
    _write_case_files(tmp_path, "case-cli-a")
    _write_case_files(tmp_path, "case-cli-b")
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "suite.json"
    manifest_path.write_text(
        json.dumps(_manifest(["case-cli-a", "case-cli-b"])), encoding="utf-8"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(COLLECTOR),
            "--manifest",
            str(manifest_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["release_eligible"] is True
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert [pair["case_id"] for pair in output["pairs"]] == [
        "case-cli-a",
        "case-cli-b",
    ]


def test_manifest_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    _write_case_files(tmp_path, "duplicate")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest(["duplicate", "duplicate"])), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="duplicate case_id"):
        build_suite_from_manifest(manifest_path)


@pytest.mark.parametrize(
    ("manifest_update", "message"),
    [
        (lambda manifest: manifest.pop("cases"), "cases"),
        (
            lambda manifest: manifest["cases"].__setitem__(0, {"case_id": "broken"}),
            "legacy",
        ),
        (
            lambda manifest: (
                manifest["cases"].__getitem__(0).update({"legacy": "../outside.json"})
            ),
            "outside",
        ),
        (
            lambda manifest: manifest.update({"authorization_ref": ""}),
            "authorization_ref",
        ),
    ],
)
def test_manifest_rejects_missing_malformed_or_unauthorized_cases(
    tmp_path: Path,
    manifest_update: object,
    message: str,
) -> None:
    _write_case_files(tmp_path, "valid")
    manifest = _manifest(["valid"])
    if callable(manifest_update):
        manifest_update(manifest)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        build_suite_from_manifest(manifest_path)


def test_manifest_rejects_a_case_with_an_invalid_runtime_trace(
    tmp_path: Path,
) -> None:
    _write_case_files(tmp_path, "invalid-trace")
    (tmp_path / "invalid-trace-checkpoints.json").write_text(
        json.dumps({"checkpoints": []}), encoding="utf-8"
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest(["invalid-trace"])), encoding="utf-8")

    with pytest.raises(ValueError, match="runtime checkpoint trace is invalid"):
        build_suite_from_manifest(manifest_path)
