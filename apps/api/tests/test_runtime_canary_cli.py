from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeCanaryPair,
    RuntimeCanarySuite,
    RuntimeCheckpointRecord,
    RuntimeLaunchSnapshot,
    RuntimeNode,
)

from scripts.collect_runtime_canary import build_suite

ROOT = Path(__file__).resolve().parents[3]
EVALUATOR = ROOT / "scripts" / "evaluate_runtime_canary.py"
COLLECTOR = ROOT / "scripts" / "collect_runtime_canary.py"


def _checkpoints() -> list[dict[str, object]]:
    run = AgentRun(
        run_id="run-cli",
        task_id="task-cli",
        goal="canary cli",
        plan=AgentRunPlan(
            plan_id="plan-cli",
            version="general-qa-v1",
            goal="canary cli",
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
            reason="offline cli test",
        ),
    )
    return [
        RuntimeCheckpointRecord(
            sequence=1,
            state_version=1,
            state_data=run.model_dump(mode="json"),
        ).model_dump(mode="json")
    ]


def _payloads() -> tuple[dict[str, object], dict[str, object]]:
    common = {
        "agent_id": "GENERAL_QUESTION_V1",
        "status": "completed",
        "answer": "same",
    }
    return common.copy(), common.copy()


def _authorized_suite() -> RuntimeCanarySuite:
    legacy, runtime = _payloads()
    return build_suite(
        agent_id="GENERAL_QUESTION_V1",
        agent_version="1.0",
        runtime_plan_version="general-qa-v1",
        suite_id="cli-authorized",
        case_id="cli-case",
        authorization_ref="change-cli-1",
        captured_at=datetime(2026, 8, 9, tzinfo=UTC),
        legacy_payload=legacy,
        runtime_payload=runtime,
        runtime_checkpoints=_checkpoints(),
    )


def _run(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_evaluator_cli_supports_explicit_release_gate_and_legacy_alias(
    tmp_path: Path,
) -> None:
    suite_path = tmp_path / "authorized-suite.json"
    suite_path.write_text(
        json.dumps(_authorized_suite().model_dump(mode="json")),
        encoding="utf-8",
    )

    explicit = _run(
        EVALUATOR,
        str(suite_path),
        "--require-release-eligible",
    )
    legacy_alias = _run(
        EVALUATOR,
        str(suite_path),
        "--require-canary-eligible",
    )

    assert explicit.returncode == 0, explicit.stderr
    assert legacy_alias.returncode == 0, legacy_alias.stderr
    assert json.loads(explicit.stdout)["release_eligible"] is True
    assert json.loads(legacy_alias.stdout)["canary_eligible"] is True

    help_result = _run(EVALUATOR, "--help")
    assert help_result.returncode == 0
    assert "--require-release-eligible" in help_result.stdout
    assert "legacy compatibility alias" in help_result.stdout


def test_evaluator_cli_reports_json_and_fails_both_release_gate_spellings(
    tmp_path: Path,
) -> None:
    legacy, runtime = _payloads()
    suite = RuntimeCanarySuite(
        suite_id="cli-synthetic",
        pairs=[
            RuntimeCanaryPair(
                case_id="cli-synthetic-case",
                legacy_payload=legacy,
                runtime_payload=runtime,
                runtime_checkpoints=_checkpoints(),
            )
        ],
    )
    suite_path = tmp_path / "synthetic-suite.json"
    suite_path.write_text(
        json.dumps(suite.model_dump(mode="json")),
        encoding="utf-8",
    )

    without_gate = _run(EVALUATOR, str(suite_path))
    old_gate = _run(
        EVALUATOR,
        str(suite_path),
        "--require-canary-eligible",
    )
    release_gate = _run(
        EVALUATOR,
        str(suite_path),
        "--require-release-eligible",
    )

    assert without_gate.returncode == 0, without_gate.stderr
    assert json.loads(without_gate.stdout)["canary_eligible"] is True
    assert json.loads(without_gate.stdout)["release_eligible"] is False
    assert old_gate.returncode == 1
    assert release_gate.returncode == 1
    assert json.loads(old_gate.stdout)["release_eligible"] is False


def test_collector_cli_writes_release_suite_and_report_without_provider(
    tmp_path: Path,
) -> None:
    legacy, runtime = _payloads()
    legacy_path = tmp_path / "legacy.json"
    runtime_path = tmp_path / "runtime.json"
    checkpoints_path = tmp_path / "checkpoints.json"
    output_path = tmp_path / "suite.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    checkpoints_path.write_text(
        json.dumps({"checkpoints": _checkpoints()}),
        encoding="utf-8",
    )

    result = _run(
        COLLECTOR,
        "--agent-id",
        "GENERAL_QUESTION_V1",
        "--agent-version",
        "1.0",
        "--runtime-plan-version",
        "general-qa-v1",
        "--suite-id",
        "cli-collector",
        "--case-id",
        "cli-collector-case",
        "--authorization-ref",
        "change-cli-collector-1",
        "--captured-at",
        "2026-08-09T00:00:00+08:00",
        "--legacy",
        str(legacy_path),
        "--runtime",
        str(runtime_path),
        "--checkpoints",
        str(checkpoints_path),
        "--output",
        str(output_path),
    )

    assert result.returncode == 0, result.stderr
    assert output_path.is_file()
    assert json.loads(result.stdout)["release_eligible"] is True
    assert json.loads(output_path.read_text(encoding="utf-8"))["suite_id"] == (
        "cli-collector"
    )


def test_collector_cli_fails_without_writing_an_invalid_artifact(
    tmp_path: Path,
) -> None:
    legacy, runtime = _payloads()
    legacy_path = tmp_path / "legacy.json"
    runtime_path = tmp_path / "runtime.json"
    checkpoints_path = tmp_path / "invalid-checkpoints.json"
    output_path = tmp_path / "should-not-exist.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    checkpoints_path.write_text(json.dumps({"checkpoints": []}), encoding="utf-8")

    result = _run(
        COLLECTOR,
        "--agent-id",
        "GENERAL_QUESTION_V1",
        "--agent-version",
        "1.0",
        "--runtime-plan-version",
        "general-qa-v1",
        "--suite-id",
        "cli-invalid",
        "--case-id",
        "cli-invalid-case",
        "--authorization-ref",
        "change-cli-invalid-1",
        "--captured-at",
        "2026-08-09T00:00:00+08:00",
        "--legacy",
        str(legacy_path),
        "--runtime",
        str(runtime_path),
        "--checkpoints",
        str(checkpoints_path),
        "--output",
        str(output_path),
    )

    assert result.returncode != 0
    assert "invalid" in result.stderr.lower()
    assert not output_path.exists()
