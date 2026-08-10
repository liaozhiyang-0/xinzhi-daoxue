from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "analyze_runtime_paired_samples.py"
SPEC = importlib.util.spec_from_file_location("paired_sample_analysis", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _result(mode: str, *, latency: int, lifecycle: int, wait: int) -> dict[str, object]:
    return {
        "case_id": "solver_case",
        "agent_id": "ACADEMIC_PROBLEM_SOLVER",
        "mode": mode,
        "expected_agent_matched": True,
        "events": {"strictly_increasing": True},
        "result": {
            "status": "completed",
            "task_lifecycle_elapsed_ms": lifecycle,
            "client_observed_terminal_wait_ms": wait,
            "metrics": {"latency_ms": latency},
        },
    }


def _write_report(root: Path, results: list[dict[str, object]]) -> Path:
    path = root / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"results": results}), encoding="utf-8")
    return path


def test_analysis_reports_median_and_single_sample_regression(tmp_path: Path) -> None:
    first = _write_report(
        tmp_path / "sample-one",
        [
            _result("legacy", latency=100, lifecycle=90, wait=110),
            _result("runtime", latency=120, lifecycle=100, wait=130),
        ],
    )
    second = _write_report(
        tmp_path / "sample-two",
        [
            _result("legacy", latency=100, lifecycle=95, wait=120),
            _result("runtime", latency=180, lifecycle=170, wait=190),
        ],
    )

    report = MODULE.analyze_reports([first, second])

    case = report["cases"][0]
    assert report["diagnostic_only"] is True
    assert report["release_decision"] == "not_applicable"
    assert case["usable_sample_count"] == 2
    assert case["metrics"]["metrics.latency_ms"]["runtime"]["median"] == 150
    assert case["metrics"]["metrics.latency_ms"]["runtime_minus_legacy"] == {
        "count": 2,
        "min": 20,
        "median": 50,
        "max": 80,
    }
    assert case["requires_investigation"] is True
    assert case["single_sample_regressions"] == [
        {
            "sample_ref": "sample-two",
            "metric": "metrics.latency_ms",
            "legacy": 100,
            "runtime": 180,
            "regression_ratio": 0.8,
        },
        {
            "sample_ref": "sample-two",
            "metric": "task_lifecycle_elapsed_ms",
            "legacy": 95,
            "runtime": 170,
            "regression_ratio": 0.789474,
        },
        {
            "sample_ref": "sample-two",
            "metric": "client_observed_terminal_wait_ms",
            "legacy": 120,
            "runtime": 190,
            "regression_ratio": 0.583333,
        },
    ]


def test_analysis_marks_missing_or_incomplete_pairs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one report"):
        MODULE.analyze_reports([])

    report_path = _write_report(
        tmp_path / "incomplete",
        [_result("legacy", latency=100, lifecycle=90, wait=110)],
    )
    report = MODULE.analyze_reports([report_path])

    assert report["cases"] == []
    assert report["input_issues"] == [
        "incomplete:solver_case: incomplete Legacy/Runtime pair"
    ]
