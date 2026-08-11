from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "analyze_runtime_browser_acceptance.py"
SPEC = importlib.util.spec_from_file_location(
    "browser_acceptance_analysis", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _report(
    root: Path,
    name: str,
    *,
    task_status: str,
    role: str = "researcher",
    agent_id: str = "RESEARCH_02_ACADEMIC_WRITING_V1",
    report_status: str = "completed",
    proposals: int = 0,
    error: str = "",
) -> Path:
    observations = [
        {"plan_proposal_id": f"proposal-{index}"}
        for index in range(proposals)
    ]
    path = root / name / "report.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "status": report_status,
                "approval_observations": observations,
                "evidence": {
                    "identity": {"role": role},
                    "task": {
                        "status": task_status,
                        "agent_id": agent_id,
                        "result_provider": "local_agent"
                        if task_status == "completed"
                        else None,
                        "error_message": error,
                    },
                    "event_count": 27,
                    "event_sequences_strictly_increasing": True,
                    "runtime_events": [],
                },
                "page_errors": [],
                "request_failures": [],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_analysis_counts_valid_terminal_samples_and_proposals(tmp_path: Path) -> None:
    completed = _report(tmp_path, "completed", task_status="completed", proposals=1)
    failed = _report(
        tmp_path,
        "failed",
        task_status="failed",
        report_status="failed",
        proposals=2,
        error="default Runtime execution did not complete (status=failed)",
    )

    result = MODULE.analyze_reports(
        [completed, failed],
        expected_agent_id="RESEARCH_02_ACADEMIC_WRITING_V1",
        expected_identity="researcher",
    )

    assert result["valid_sample_count"] == 2
    assert result["completed_count"] == 1
    assert result["failed_count"] == 1
    assert result["success_rate"] == 0.5
    assert result["structurally_clean_count"] == 2
    assert result["proposal_count_distribution"] == {"1": 1, "2": 1}
    assert result["diagnostic_only"] is True
    assert result["release_decision"] == "not_applicable"


def test_analysis_excludes_identity_and_harness_reports(tmp_path: Path) -> None:
    wrong_identity = _report(
        tmp_path, "wrong-identity", task_status="completed", role="admin"
    )
    non_terminal = _report(tmp_path, "non-terminal", task_status="running")
    wrong_agent = _report(
        tmp_path, "wrong-agent", task_status="failed", agent_id="OTHER"
    )

    result = MODULE.analyze_reports(
        [wrong_identity, non_terminal, wrong_agent],
        expected_agent_id="RESEARCH_02_ACADEMIC_WRITING_V1",
        expected_identity="researcher",
    )

    assert result["valid_sample_count"] == 0
    assert result["excluded_report_count"] == 3
    assert result["completed_count"] == 0
    assert result["failed_count"] == 0


def test_analysis_preserves_runtime_failure_signals(tmp_path: Path) -> None:
    path = _report(
        tmp_path, "failed-signal", task_status="failed", report_status="failed"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evidence"]["runtime_events"] = [
        {
            "sequence": 44,
            "event_type": "plan.node_failed",
            "runtime_event": "node_failed",
            "node_id": "writing.execute.replan.2",
            "status": "failed",
            "error_code": "model_timeout",
            "reason_codes": [],
        }
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = MODULE.analyze_reports(
        [path],
        expected_agent_id="RESEARCH_02_ACADEMIC_WRITING_V1",
        expected_identity="researcher",
    )

    assert result["failure_signals"] == [
        {
            "report_ref": "failed-signal",
            "signals": [
                {
                    "sequence": 44,
                    "event_type": "plan.node_failed",
                    "runtime_event": "node_failed",
                    "node_id": "writing.execute.replan.2",
                    "status": "failed",
                    "error_code": "model_timeout",
                    "reason_codes": [],
                }
            ],
        }
    ]


def test_analysis_requires_a_report() -> None:
    with pytest.raises(ValueError, match="at least one report"):
        MODULE.analyze_reports(
            [],
            expected_agent_id="RESEARCH_02_ACADEMIC_WRITING_V1",
            expected_identity="researcher",
        )
