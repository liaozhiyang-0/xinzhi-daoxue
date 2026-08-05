from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path

from analyze_evaluation_report import (
    DEFAULT_CASES,
    DEFAULT_CONFIG,
    build_output,
    load_cases,
    load_json,
    write_outputs,
)


def synthetic_case(
    case_id: str,
    *,
    role: str,
    tags: list[str] | None = None,
    expected_error_type: str | None = None,
) -> dict[str, object]:
    case: dict[str, object] = {
        "case_id": case_id,
        "course": "CT",
        "input_type": "text",
        "structured_input": {"balanced_suite_role": role},
        "tags": tags or [],
    }
    if expected_error_type:
        case["expected_verification_status"] = "verified_incorrect"
        case["expected_error_type"] = expected_error_type
    return case


def synthetic_result(
    case_id: str,
    *,
    status: str,
    answer_passed: bool,
    tokens: int | None,
    elapsed_ms: int,
    actual: dict[str, object] | None = None,
) -> dict[str, object]:
    actual_payload = dict(actual or {})
    actual_payload.setdefault(
        "answer_evaluation",
        {
            "passed": answer_passed,
            "score": 1.0 if answer_passed else 0.0,
            "judge": "hybrid",
            "reference_used": True,
            "reason": "synthetic validation",
        },
    )
    return {
        "case_id": case_id,
        "status": status,
        "route_passed": status != "timeout",
        "course_passed": status != "timeout",
        "agent_passed": status != "timeout",
        "structure_passed": status != "timeout",
        "tools_passed": status != "timeout",
        "answer_passed": answer_passed,
        "citations_passed": True,
        "safety_passed": True,
        "forbidden_claims_found": [],
        "failure_stage": "answer" if status == "failed" else "none",
        "error_types": ["answer_mismatch"] if status == "failed" else [],
        "elapsed_ms": elapsed_ms,
        "model_calls": (
            [
                {
                    "model": "synthetic-model",
                    "prompt_tokens": tokens - 20,
                    "completion_tokens": 20,
                    "total_tokens": tokens,
                    "retry_count": 0,
                    "fallback_used": False,
                }
            ]
            if tokens is not None
            else []
        ),
        "actual": actual_payload,
        "trace_id": f"trace-{case_id}",
    }


def assert_real_suite_contract(config: dict[str, object]) -> None:
    cases = load_cases(DEFAULT_CASES)
    expected = config["cohorts"]
    assert isinstance(expected, dict)
    suite = config["suite"]
    assert isinstance(suite, dict)
    by_course = Counter(case["course"] for case in cases)
    roles: dict[str, int] = {}
    tags: dict[str, int] = {}
    for case in cases:
        role = case["structured_input"]["balanced_suite_role"]
        roles[role] = roles.get(role, 0) + 1
        for tag in case.get("tags", []):
            tags[tag] = tags.get(tag, 0) + 1
    assert len(cases) == suite["expected_total"]
    assert set(by_course) == set(suite["courses"])
    assert set(by_course.values()) == {suite["expected_per_course"]}
    assert roles["verified_original_answer"] == 121
    assert roles["curated_answer_or_error"] == 36
    assert (
        roles["verified_original_answer"] + roles["curated_answer_or_error"]
        == expected["source_answer"]["expected_count"]
    )
    assert (
        expected["source_answer"]["expected_count"]
        - expected["error_detection"]["expected_count"]
        == expected["standard_answer"]["expected_count"]
    )
    assert roles["synthetic_boundary"] == expected["boundary"]["expected_count"]
    assert roles["question_only_filler"] == expected["question_only"]["expected_count"]
    assert (
        tags["part2_error_detection"] == expected["error_detection"]["expected_count"]
    )
    assert all(
        case.get("reference_answer")
        for case in cases
        if case["structured_input"]["balanced_suite_role"]
        in {"verified_original_answer", "curated_answer_or_error"}
    )
    assert all(
        case.get("reference_answer") is None
        for case in cases
        if case["structured_input"]["balanced_suite_role"] == "question_only_filler"
    )


def main() -> int:
    config = load_json(DEFAULT_CONFIG)
    assert_real_suite_contract(config)
    cases = [
        synthetic_case("S1", role="verified_original_answer"),
        synthetic_case("S2", role="verified_original_answer"),
        synthetic_case(
            "E1",
            role="curated_answer_or_error",
            tags=["part2_error_detection"],
            expected_error_type="sign_error",
        ),
        synthetic_case("B1", role="synthetic_boundary"),
        synthetic_case("Q1", role="question_only_filler"),
    ]
    results = [
        synthetic_result(
            "S1", status="passed", answer_passed=True, tokens=100, elapsed_ms=100
        ),
        synthetic_result(
            "S2", status="failed", answer_passed=False, tokens=200, elapsed_ms=200
        ),
        synthetic_result(
            "E1",
            status="passed",
            answer_passed=True,
            tokens=300,
            elapsed_ms=300,
            actual={
                "verification_report_valid": True,
                "first_confirmed_error_found": True,
                "expected_verification_status": "verified_incorrect",
                "expected_error_type": "sign_error",
            },
        ),
        synthetic_result(
            "B1", status="passed", answer_passed=True, tokens=400, elapsed_ms=400
        ),
        synthetic_result(
            "Q1", status="timeout", answer_passed=False, tokens=None, elapsed_ms=500
        ),
    ]
    summary, rows, visualization = build_output(
        cases,
        results,
        config,
        {"schema_version": "synthetic", "mode": "synthetic"},
    )
    overall = summary["overall"]
    assert overall["quality"]["strict_answer_accuracy"]["value"] == 0.5
    assert overall["quality"]["conditional_answer_accuracy"]["value"] == 0.5
    assert overall["quality"]["error_detection_accuracy"]["value"] == 1.0
    assert overall["quality"]["boundary_compliance_rate"]["value"] == 1.0
    assert overall["reliability"]["execution_success_rate"]["value"] == 0.8
    assert overall["failures"]["quality_failure_count"] == 1
    assert overall["failures"]["timeout_count"] == 1
    assert overall["latency"]["p95"] == 500
    assert overall["tokens"]["total_tokens_known"] == 1000
    assert overall["tokens"]["token_call_coverage_rate"]["value"] == 1.0
    assert overall["tokens"]["case_token_coverage_rate"]["value"] == 0.8
    assert overall["tokens"]["tokens_per_correct_answer"] == 300.0
    assert overall["tokens"]["wasted_token_rate"]["value"] == 0.2

    raw_summary, _, _ = build_output(
        cases,
        [
            {
                "case_id": case["case_id"],
                "status": "completed",
                "elapsed_seconds": 1.0,
            }
            for case in cases
        ],
        config,
        {"schema_version": "raw-api", "mode": "raw-api"},
    )
    assert raw_summary["overall"]["quality"]["strict_answer_accuracy"]["value"] is None
    assert raw_summary["overall"]["tokens"]["token_call_coverage_rate"]["value"] is None
    assert (
        raw_summary["overall"]["reliability"]["execution_success_rate"]["value"] == 1.0
    )

    with tempfile.TemporaryDirectory(prefix="xzd-eval-metrics-") as temp_dir:
        output_dir = Path(temp_dir)
        write_outputs(output_dir, summary, rows, visualization)
        assert (output_dir / "metrics_summary.json").is_file()
        assert (output_dir / "case_metrics.csv").is_file()
        assert (output_dir / "visualization_data.json").is_file()

    print("evaluation metrics validation passed: real suite contract + synthetic math")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
