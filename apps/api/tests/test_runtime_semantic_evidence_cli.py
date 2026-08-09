from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.runtime.semantic_evidence import payload_sha256

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "collect_runtime_semantic_evidence.py"


def _suite(*, kind: str = "authorized_paired") -> dict[str, Any]:
    return {
        "suite_id": "semantic-cli-suite",
        "evidence": {
            "kind": kind,
            "agent_id": "GENERAL_QUESTION_V1",
            "agent_version": "1.0",
            "runtime_plan_version": "general-qa-v1",
            "authorization_ref": "review-change-1",
            "captured_at": "2026-08-09T09:00:00+08:00",
            "redaction_status": "redacted",
        },
        "pairs": [
            {
                "case_id": "case-1",
                "input_sha256": payload_sha256(_inputs()["case-1"])
                if kind == "authorized_paired"
                else None,
                "legacy_payload": {"status": "completed", "answer": "legacy"},
                "runtime_payload": {
                    "status": "completed",
                    "answer": "runtime",
                },
                "runtime_checkpoints": [],
            },
            {
                "case_id": "case-2",
                "input_sha256": payload_sha256(_inputs()["case-2"])
                if kind == "authorized_paired"
                else None,
                "legacy_payload": {"status": "completed", "answer": "old-2"},
                "runtime_payload": {
                    "status": "completed",
                    "answer": "new-2",
                },
                "runtime_checkpoints": [],
            },
        ],
    }


def _inputs() -> dict[str, Any]:
    return {
        "case-1": {"question": "What is an agent?", "order": 1},
        "case-2": {"question": "What is a plan?", "order": 2},
    }


def _judgements(*, reviewed_at: str = "2026-08-09T10:00:00+08:00") -> dict[str, Any]:
    return {
        case_id: {
            "dimensions": {
                "task_fulfillment": 1,
                "factual_correctness": 1,
                "evidence_faithfulness": None,
                "safety": 1,
            },
            "decision": "pass",
            "judge_type": "human",
            "rubric_version": "general-question-v1",
            "reviewer_ref": "reviewer-1",
            "reviewed_at": reviewed_at,
            "redaction_status": "redacted",
            "authorization_ref": "review-change-1",
        }
        for case_id in ("case-1", "case-2")
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_cli(
    tmp_path: Path,
    *,
    suite: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
    judgements: dict[str, Any] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    suite_path = tmp_path / "suite.json"
    inputs_path = tmp_path / "inputs.json"
    judgements_path = tmp_path / "judgements.json"
    output_path = tmp_path / "sidecar.json"
    _write_json(suite_path, suite if suite is not None else _suite())
    _write_json(inputs_path, inputs if inputs is not None else _inputs())
    _write_json(
        judgements_path,
        judgements if judgements is not None else _judgements(),
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--suite",
            str(suite_path),
            "--inputs",
            str(inputs_path),
            "--judgements",
            str(judgements_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, output_path


def test_cli_writes_all_cases_without_raw_inputs_and_is_reproducible(
    tmp_path: Path,
) -> None:
    first, output_path = _run_cli(tmp_path)

    assert first.returncode == 0, first.stderr
    first_bytes = output_path.read_bytes()
    sidecar = json.loads(first_bytes)
    assert [item["case_id"] for item in sidecar] == ["case-1", "case-2"]
    assert all("input" not in item for item in sidecar)
    assert all("What is" not in json.dumps(item) for item in sidecar)

    second_output = tmp_path / "sidecar-second.json"
    second = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--suite",
            str(tmp_path / "suite.json"),
            "--inputs",
            str(tmp_path / "inputs.json"),
            "--judgements",
            str(tmp_path / "judgements.json"),
            "--output",
            str(second_output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    assert second_output.read_bytes() == first_bytes


def test_cli_binds_input_and_output_hashes_to_each_pair(tmp_path: Path) -> None:
    result, output_path = _run_cli(tmp_path)

    assert result.returncode == 0, result.stderr
    sidecar = json.loads(output_path.read_text(encoding="utf-8"))
    suite = _suite()
    inputs = _inputs()
    pairs = {pair["case_id"]: pair for pair in suite["pairs"]}
    for item in sidecar:
        pair = pairs[item["case_id"]]
        assert item["input_sha256"] == payload_sha256(inputs[item["case_id"]])
        assert item["legacy_output_sha256"] == payload_sha256(
            pair["legacy_payload"]
        )
        assert item["runtime_output_sha256"] == payload_sha256(
            pair["runtime_payload"]
        )


def test_cli_rejects_case_mismatch_without_writing_output(tmp_path: Path) -> None:
    inputs = _inputs()
    del inputs["case-2"]
    result, output_path = _run_cli(tmp_path, inputs=inputs)

    assert result.returncode != 0
    assert "case_id mismatch" in result.stderr
    assert not output_path.exists()


def test_cli_rejects_unauthorized_suite_without_writing_output(tmp_path: Path) -> None:
    suite = _suite()
    suite["evidence"]["authorization_ref"] = ""
    result, output_path = _run_cli(tmp_path, suite=suite)

    assert result.returncode != 0
    assert "not authorized" in result.stderr
    assert not output_path.exists()


def test_cli_accepts_legacy_synthetic_suite_without_input_hash(
    tmp_path: Path,
) -> None:
    result, output_path = _run_cli(tmp_path, suite=_suite(kind="synthetic"))

    assert result.returncode == 0, result.stderr
    assert output_path.exists()


def test_cli_rejects_authorized_pair_missing_input_hash_without_writing_output(
    tmp_path: Path,
) -> None:
    suite = _suite()
    del suite["pairs"][0]["input_sha256"]
    result, output_path = _run_cli(tmp_path, suite=suite)

    assert result.returncode != 0
    assert "missing input_sha256" in result.stderr
    assert not output_path.exists()


def test_cli_rejects_authorized_pair_input_hash_mismatch_without_writing_output(
    tmp_path: Path,
) -> None:
    suite = _suite()
    suite["pairs"][0]["input_sha256"] = "0" * 64
    result, output_path = _run_cli(tmp_path, suite=suite)

    assert result.returncode != 0
    assert "input_sha256 mismatch" in result.stderr
    assert not output_path.exists()


def test_cli_rejects_reviewed_at_without_timezone_without_writing_output(
    tmp_path: Path,
) -> None:
    result, output_path = _run_cli(
        tmp_path,
        judgements=_judgements(reviewed_at="2026-08-09T10:00:00"),
    )

    assert result.returncode != 0
    assert "timezone" in result.stderr
    assert not output_path.exists()


def test_cli_rejects_non_redacted_judgement_without_writing_output(
    tmp_path: Path,
) -> None:
    judgements = _judgements()
    judgements["case-1"]["redaction_status"] = "unknown"
    result, output_path = _run_cli(tmp_path, judgements=judgements)

    assert result.returncode != 0
    assert "redacted" in result.stderr
    assert not output_path.exists()
