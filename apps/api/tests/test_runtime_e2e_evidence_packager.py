from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.runtime import AgentRun, AgentRunPlan, RuntimeLaunchSnapshot, RuntimeNode
from app.runtime.semantic_evidence import payload_sha256

from scripts.package_runtime_e2e_evidence import package_e2e_evidence


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _create_runtime_run(
    database: Path,
    *,
    task_id: str,
    agent_id: str = "GENERAL_QUESTION_V1",
    sensitive: bool = False,
) -> None:
    run = AgentRun(
        run_id="runtime-e2e-run",
        task_id=task_id,
        goal="controlled E2E evidence",
        plan=AgentRunPlan(
            plan_id="runtime-e2e-plan",
            version="general-qa-v1",
            goal="controlled E2E evidence",
            nodes=[
                RuntimeNode(
                    node_id="final",
                    node_type="terminal",
                    handler_id="runtime.final",
                )
            ],
        ),
        launch_decision=RuntimeLaunchSnapshot(
            agent_id=agent_id,
            mode="canary",
            source="test",
            reason="controlled evidence packager test",
        ),
    )
    state_data = run.model_dump(mode="json")
    if sensitive:
        state_data["control_data"] = {"token": "must-not-export"}
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE agent_runs (
                id TEXT PRIMARY KEY,
                task_id TEXT,
                agent_id TEXT,
                run_kind TEXT,
                parent_run_id TEXT,
                agent_version TEXT,
                plan_version TEXT,
                created_at TEXT
            );
            CREATE TABLE agent_checkpoints (
                run_id TEXT,
                sequence INTEGER,
                state_version INTEGER,
                state_data TEXT,
                event_sequence INTEGER,
                created_at TEXT
            );
            """
        )
        created_at = datetime(2026, 8, 10, tzinfo=UTC).isoformat()
        connection.execute(
            """
            INSERT INTO agent_runs
            (id, task_id, agent_id, run_kind, parent_run_id, agent_version,
             plan_version, created_at)
            VALUES (?, ?, ?, 'runtime', '', '1.0.0', 'general-qa-v1', ?)
            """,
            (run.run_id, task_id, agent_id, created_at),
        )
        connection.execute(
            """
            INSERT INTO agent_checkpoints
            (run_id, sequence, state_version, state_data, event_sequence, created_at)
            VALUES (?, 1, 1, ?, 0, ?)
            """,
            (run.run_id, json.dumps(state_data), created_at),
        )


def _create_pair_artifacts(
    root: Path,
    *,
    task_id: str = "runtime-task",
    legacy_latency_ms: int = 0,
    runtime_latency_ms: int = 0,
) -> None:
    base = root / "artifacts" / "GENERAL_QUESTION_V1" / "general-case"
    input_payload = {"question": "controlled private input"}
    for mode in ("legacy", "runtime"):
        _write_json(base / mode / "input.json", input_payload)
        _write_json(
            base / mode / "task.json",
            {
                "id": task_id if mode == "runtime" else "legacy-task",
                "agent_id": "GENERAL_QUESTION_V1",
                "status": "completed",
                "provider": "mock",
                "result_content": {
                    "answer": "controlled answer",
                    "metrics": {
                        "latency_ms": (
                            legacy_latency_ms
                            if mode == "legacy"
                            else runtime_latency_ms
                        )
                    },
                },
            },
        )


def test_packager_exports_unchanged_trace_and_builds_structural_suite(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "e2e"
    database = tmp_path / "isolated.db"
    _create_pair_artifacts(output_root)
    _create_runtime_run(database, task_id="runtime-task")

    report = package_e2e_evidence(
        output_root=output_root,
        sqlite_database=database,
        authorization_ref="authorized-dev-test-2026-08-10",
    )

    assert report["semantic_review_required"] is True
    assert report["human_release_decision_required"] is True
    agent = report["agents"][0]
    assert agent["structural_release_eligible"] is True
    checkpoints_path = (
        output_root
        / "artifacts"
        / "GENERAL_QUESTION_V1"
        / "general-case"
        / "runtime"
        / "checkpoints.json"
    )
    checkpoints = json.loads(checkpoints_path.read_text(encoding="utf-8"))
    assert checkpoints["checkpoints"][0]["state_data"]["run_id"] == "runtime-e2e-run"
    suite_path = output_root / agent["structural_suite"]
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    assert suite["evidence"]["kind"] == "authorized_paired"
    assert "controlled private input" not in json.dumps(suite)
    semantic_inputs = json.loads(
        (output_root / agent["semantic_inputs"]).read_text(encoding="utf-8")
    )
    judgement_template = json.loads(
        (output_root / agent["semantic_judgements_template"]).read_text(
            encoding="utf-8"
        )
    )
    assert semantic_inputs == {"general-case": {"question": "controlled private input"}}
    review_packet = json.loads(
        (output_root / agent["semantic_review_packet"]).read_text(encoding="utf-8")
    )
    assert review_packet["review_boundary"].startswith("Paired output excerpts")
    case = review_packet["cases"][0]
    assert case["case_id"] == "general-case"
    assert case["redacted_input"] == {"question": "controlled private input"}
    assert case["legacy_output"] == {
        "status": "completed",
        "answer": "controlled answer",
    }
    assert case["runtime_output"] == {
        "status": "completed",
        "answer": "controlled answer",
    }
    assert case["input_sha256"] == suite["pairs"][0]["input_sha256"]
    assert case["legacy_payload_sha256"] == payload_sha256(
        suite["pairs"][0]["legacy_payload"]
    )
    assert case["runtime_payload_sha256"] == payload_sha256(
        suite["pairs"][0]["runtime_payload"]
    )
    assert case["runtime_checkpoint_path"] == (
        "artifacts/GENERAL_QUESTION_V1/general-case/runtime/checkpoints.json"
    )
    assert judgement_template["general-case"]["decision"] == "needs_review"
    assert (
        judgement_template["general-case"]["reviewer_ref"]
        == "TO_BE_COMPLETED_BY_INDEPENDENT_REVIEWER"
    )


def test_packager_rejects_sensitive_checkpoint_state(tmp_path: Path) -> None:
    output_root = tmp_path / "e2e"
    database = tmp_path / "isolated.db"
    _create_pair_artifacts(output_root)
    _create_runtime_run(database, task_id="runtime-task", sensitive=True)

    report = package_e2e_evidence(
        output_root=output_root,
        sqlite_database=database,
        authorization_ref="authorized-dev-test-2026-08-10",
    )

    agent = report["agents"][0]
    assert agent["structural_release_eligible"] is False
    assert "sensitive keys" in agent["blocking_reasons"][0]
    assert not (output_root / "structural_suites").exists()


def test_packager_rejects_sensitive_paired_output(tmp_path: Path) -> None:
    output_root = tmp_path / "e2e"
    database = tmp_path / "isolated.db"
    _create_pair_artifacts(output_root)
    runtime_task = (
        output_root
        / "artifacts"
        / "GENERAL_QUESTION_V1"
        / "general-case"
        / "runtime"
        / "task.json"
    )
    task_payload = json.loads(runtime_task.read_text(encoding="utf-8"))
    task_payload["result_content"]["api_key"] = "must-not-export"
    _write_json(runtime_task, task_payload)
    _create_runtime_run(database, task_id="runtime-task")

    report = package_e2e_evidence(
        output_root=output_root,
        sqlite_database=database,
        authorization_ref="authorized-dev-test-2026-08-10",
    )

    agent = report["agents"][0]
    assert agent["structural_release_eligible"] is False
    assert "result_content contains sensitive keys" in agent["blocking_reasons"][0]
    assert not (output_root / "semantic_review_packets").exists()


def test_packager_records_a_structural_gate_failure_without_faking_a_suite(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "e2e"
    database = tmp_path / "isolated.db"
    _create_pair_artifacts(
        output_root,
        legacy_latency_ms=100,
        runtime_latency_ms=200,
    )
    _create_runtime_run(database, task_id="runtime-task")

    report = package_e2e_evidence(
        output_root=output_root,
        sqlite_database=database,
        authorization_ref="authorized-dev-test-2026-08-10",
    )

    agent = report["agents"][0]
    assert agent["structural_release_eligible"] is False
    assert "latency_regression_above_threshold" in agent["blocking_reasons"][0]
    assert not (output_root / "structural_suites").exists()
