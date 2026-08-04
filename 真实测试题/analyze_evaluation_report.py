from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_CASES = ROOT / "统一格式" / "balanced_336" / "all_cases.json"
DEFAULT_CONFIG = ROOT / "evaluation_metrics.json"
DEFAULT_OUTPUT_DIR = ROOT / "统一格式" / "evaluation_reports"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError(f'{path}: 顶层必须为 {{"cases": [...]}}')
    return cases


def load_results(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = load_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError(f"{path}: 顶层必须包含 results 数组")
    return payload["results"], payload


def case_role(case: dict[str, Any]) -> str:
    structured = case.get("structured_input") or {}
    return str(structured.get("balanced_suite_role") or "unclassified")


def case_cohorts(case: dict[str, Any], config: dict[str, Any]) -> set[str]:
    role = case_role(case)
    tags = {str(item) for item in case.get("tags") or []}
    matched: set[str] = set()
    for name, rule in config["cohorts"].items():
        roles = set(rule.get("balanced_suite_roles") or [])
        required_tag = rule.get("required_tag")
        excluded_tags = set(rule.get("excluded_tags") or [])
        if roles and role in roles and not (excluded_tags & tags):
            matched.add(name)
        if required_tag and required_tag in tags:
            matched.add(name)
    return matched


def _as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def normalize_result(
    raw: dict[str, Any],
    case: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    status = str(raw.get("status") or "unknown").casefold()
    elapsed_ms = _as_int(raw.get("elapsed_ms"))
    if elapsed_ms is None and isinstance(raw.get("elapsed_seconds"), (int, float)):
        elapsed_ms = round(float(raw["elapsed_seconds"]) * 1000)

    model_calls = raw.get("model_calls")
    if not isinstance(model_calls, list):
        model_calls = []
    known_calls = [
        call
        for call in model_calls
        if isinstance(call, dict) and _as_int(call.get("total_tokens")) is not None
    ]
    total_tokens = sum(int(call["total_tokens"]) for call in known_calls)
    prompt_tokens = sum(
        value
        for call in model_calls
        if isinstance(call, dict)
        for value in [_as_int(call.get("prompt_tokens"))]
        if value is not None
    )
    completion_tokens = sum(
        value
        for call in model_calls
        if isinstance(call, dict)
        for value in [_as_int(call.get("completion_tokens"))]
        if value is not None
    )
    token_usage_complete = bool(model_calls) and len(known_calls) == len(model_calls)
    raw_actual = raw.get("actual")
    actual: dict[str, Any] = raw_actual if isinstance(raw_actual, dict) else {}
    answer_evaluation = actual.get("answer_evaluation")
    answer_evaluation = answer_evaluation if isinstance(answer_evaluation, dict) else {}
    judgement_policy = config["answer_judgement_policy"]
    valid_answer_evaluation = (
        set(judgement_policy["required_fields"]).issubset(answer_evaluation)
        and isinstance(answer_evaluation.get("passed"), bool)
        and isinstance(answer_evaluation.get("score"), (int, float))
        and str(answer_evaluation.get("judge"))
        in set(judgement_policy["accepted_judges"])
        and answer_evaluation.get("reference_used") is True
        and bool(str(answer_evaluation.get("reason") or "").strip())
    )
    has_explicit_rule = any(
        case.get(key)
        for key in (
            "required_keywords",
            "required_equations",
            "required_steps",
            "numeric_expectations",
        )
    )
    contract_answer_passed = _as_bool(raw.get("answer_passed"))
    substantive_answer_passed = (
        _as_bool(answer_evaluation.get("passed")) if valid_answer_evaluation else None
    )
    answer_judge = answer_evaluation.get("judge") if valid_answer_evaluation else None
    answer_score = (
        float(answer_evaluation["score"]) if valid_answer_evaluation else None
    )
    if substantive_answer_passed is None and has_explicit_rule:
        substantive_answer_passed = contract_answer_passed
        answer_judge = "explicit_rule_constraints"
        answer_score = 1.0 if contract_answer_passed is True else 0.0
    error_types = [
        str(item.get("value") if isinstance(item, dict) else item)
        for item in raw.get("error_types") or []
    ]
    evaluation_record = any(
        key in raw
        for key in (
            "answer_passed",
            "route_passed",
            "structure_passed",
            "safety_passed",
        )
    )
    execution_completed = (
        status in {"passed", "failed", "cached"}
        if evaluation_record
        else status == "completed"
    )
    cohorts = case_cohorts(case, config)
    return {
        "case_id": str(case["case_id"]),
        "course": str(case["course"]),
        "cohort": "|".join(sorted(cohorts)) or "unclassified",
        "cohorts": cohorts,
        "role": case_role(case),
        "input_type": str(case.get("input_type") or "unknown"),
        "status": status,
        "execution_completed": execution_completed,
        "evaluation_record": evaluation_record,
        "answer_passed": substantive_answer_passed,
        "answer_contract_passed": contract_answer_passed,
        "answer_judge": answer_judge,
        "answer_score": answer_score,
        "route_passed": _as_bool(raw.get("route_passed")),
        "course_passed": _as_bool(raw.get("course_passed")),
        "agent_passed": _as_bool(raw.get("agent_passed")),
        "structure_passed": _as_bool(raw.get("structure_passed")),
        "tools_passed": _as_bool(raw.get("tools_passed")),
        "citations_passed": _as_bool(raw.get("citations_passed")),
        "safety_passed": _as_bool(raw.get("safety_passed")),
        "forbidden_claim_count": len(raw.get("forbidden_claims_found") or []),
        "failure_stage": str(raw.get("failure_stage") or "none"),
        "error_types": error_types,
        "elapsed_ms": elapsed_ms,
        "model_count": len(model_calls),
        "known_token_call_count": len(known_calls),
        "case_total_tokens": total_tokens if known_calls else None,
        "case_prompt_tokens": prompt_tokens if known_calls else None,
        "case_completion_tokens": completion_tokens if known_calls else None,
        "token_usage_complete": token_usage_complete,
        "fallback_used": any(
            bool(call.get("fallback_used"))
            for call in model_calls
            if isinstance(call, dict)
        ),
        "retry_count": sum(
            _as_int(call.get("retry_count")) or 0
            for call in model_calls
            if isinstance(call, dict)
        ),
        "trace_id": raw.get("trace_id"),
        "actual": actual,
        "raw": raw,
    }


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator <= 0:
        return {
            "value": None,
            "numerator": numerator,
            "denominator": denominator,
            "ci95": None,
        }
    value = numerator / denominator
    z = 1.959963984540054
    adjusted = 1 + z * z / denominator
    center = (value + z * z / (2 * denominator)) / adjusted
    margin = (
        z
        * math.sqrt(
            value * (1 - value) / denominator + z * z / (4 * denominator * denominator)
        )
        / adjusted
    )
    return {
        "value": round(value, 6),
        "numerator": numerator,
        "denominator": denominator,
        "ci95": [
            round(max(0.0, center - margin), 6),
            round(min(1.0, center + margin), 6),
        ],
    }


def share(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "value": round(numerator / denominator, 6) if denominator else None,
        "numerator": numerator,
        "denominator": denominator,
        "ci95": None,
    }


def percentile(values: Iterable[int], quantile: float) -> int | None:
    ordered = sorted(values)
    if not ordered:
        return None
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * quantile) - 1))
    return ordered[index]


def distribution(values: Iterable[int], percentiles: list[int]) -> dict[str, Any]:
    materialized = list(values)
    if not materialized:
        return {
            "count": 0,
            "sum": 0,
            "mean": None,
            "min": None,
            "max": None,
            **{f"p{item}": None for item in percentiles},
        }
    return {
        "count": len(materialized),
        "sum": sum(materialized),
        "mean": round(mean(materialized), 2),
        "min": min(materialized),
        "max": max(materialized),
        **{f"p{item}": percentile(materialized, item / 100) for item in percentiles},
    }


def error_detection_passed(row: dict[str, Any], case: dict[str, Any]) -> bool:
    actual = row["actual"]
    checks = [
        row["answer_contract_passed"] is True,
        actual.get("verification_report_valid") is True,
        actual.get("first_confirmed_error_found") is True,
    ]
    for expected_key in ("expected_verification_status", "expected_error_type"):
        expected = case.get(expected_key)
        if expected is not None:
            checks.append(str(actual.get(expected_key)) == str(expected))
    return all(checks)


def boundary_passed(row: dict[str, Any]) -> bool:
    return (
        row["answer_contract_passed"] is True
        and row["safety_passed"] is True
        and row["forbidden_claim_count"] == 0
    )


def selected_rows(
    rows: list[dict[str, Any]], case_ids: set[str]
) -> list[dict[str, Any]]:
    return [row for row in rows if row["case_id"] in case_ids]


def summarize_group(
    cases: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    expected_ids = {str(case["case_id"]) for case in cases}
    result_rows = selected_rows(rows, expected_ids)
    case_by_id = {str(case["case_id"]): case for case in cases}
    source_ids = {
        case_id
        for case_id, case in case_by_id.items()
        if "standard_answer" in case_cohorts(case, config)
    }
    error_ids = {
        case_id
        for case_id, case in case_by_id.items()
        if "error_detection" in case_cohorts(case, config)
    }
    boundary_ids = {
        case_id
        for case_id, case in case_by_id.items()
        if "boundary" in case_cohorts(case, config)
    }

    source_rows = selected_rows(result_rows, source_ids)
    error_rows = selected_rows(result_rows, error_ids)
    boundary_rows = selected_rows(result_rows, boundary_ids)
    answer_scored = [row for row in source_rows if row["answer_passed"] is not None]
    answer_correct = sum(row["answer_passed"] is True for row in source_rows)
    error_correct = sum(
        error_detection_passed(row, case_by_id[row["case_id"]]) for row in error_rows
    )
    boundary_correct = sum(boundary_passed(row) for row in boundary_rows)
    completed = sum(row["execution_completed"] for row in result_rows)
    evaluation_passed = sum(row["status"] == "passed" for row in result_rows)
    route_scored = [row for row in result_rows if row["route_passed"] is not None]
    route_passed = sum(row["route_passed"] is True for row in route_scored)
    structure_passed = sum(row["structure_passed"] is True for row in result_rows)
    all_calls = sum(row["model_count"] for row in result_rows)
    known_calls = sum(row["known_token_call_count"] for row in result_rows)
    complete_token_rows = [row for row in result_rows if row["token_usage_complete"]]
    known_token_rows = [
        row for row in result_rows if row["case_total_tokens"] is not None
    ]
    known_tokens = sum(int(row["case_total_tokens"]) for row in known_token_rows)
    wasted_tokens = sum(
        int(row["case_total_tokens"])
        for row in known_token_rows
        if row["status"] in {"failed", "error", "timeout", "request_error", "cancelled"}
    )
    correct_complete_token_rows = [
        row
        for row in source_rows
        if row["answer_passed"] is True and row["token_usage_complete"]
    ]
    answer_token_rows = [
        row
        for row in source_rows
        if row["token_usage_complete"] and row["case_total_tokens"] is not None
    ]
    answer_tokens = sum(int(row["case_total_tokens"]) for row in answer_token_rows)
    failure_count = sum(
        row["status"] in {"failed", "error", "timeout", "request_error", "cancelled"}
        for row in result_rows
    )
    has_evaluation_data = any(row["evaluation_record"] for row in result_rows)
    strict_source_denominator = len(source_ids) if has_evaluation_data else 0
    error_denominator = len(error_ids) if has_evaluation_data else 0
    boundary_denominator = len(boundary_ids) if has_evaluation_data else 0
    quality_failures = sum(
        row["status"] == "failed" and row["evaluation_record"] for row in result_rows
    )
    execution_errors = sum(
        (
            row["status"] in {"error", "request_error", "cancelled"}
            if row["evaluation_record"]
            else row["status"] in {"failed", "error", "request_error", "cancelled"}
        )
        for row in result_rows
    )

    return {
        "expected_cases": len(expected_ids),
        "observed_results": len(result_rows),
        "coverage": {
            "result_coverage_rate": rate(len(result_rows), len(expected_ids)),
        },
        "quality": {
            "strict_answer_accuracy": rate(answer_correct, strict_source_denominator),
            "conditional_answer_accuracy": rate(answer_correct, len(answer_scored)),
            "answer_score_coverage_rate": rate(
                len(answer_scored), strict_source_denominator
            ),
            "error_detection_accuracy": rate(error_correct, error_denominator),
            "boundary_compliance_rate": rate(boundary_correct, boundary_denominator),
            "overall_evaluation_pass_rate": rate(
                evaluation_passed, len(expected_ids) if has_evaluation_data else 0
            ),
        },
        "routing": {
            "routing_accuracy": rate(route_passed, len(route_scored)),
        },
        "reliability": {
            "execution_success_rate": rate(completed, len(expected_ids)),
            "timeout_rate": rate(
                sum(row["status"] == "timeout" for row in result_rows),
                len(expected_ids),
            ),
            "fallback_rate": rate(
                sum(row["fallback_used"] for row in result_rows),
                len(result_rows),
            ),
            "retry_count": sum(row["retry_count"] for row in result_rows),
        },
        "failures": {
            "total_failure_count": failure_count,
            "quality_failure_count": quality_failures,
            "execution_error_count": execution_errors,
            "timeout_count": sum(row["status"] == "timeout" for row in result_rows),
            "missing_result_count": len(expected_ids) - len(result_rows),
        },
        "latency": distribution(
            (
                int(row["elapsed_ms"])
                for row in result_rows
                if row["elapsed_ms"] is not None
            ),
            config["latency_percentiles"],
        ),
        "tokens": {
            "model_calls": all_calls,
            "calls_with_known_tokens": known_calls,
            "token_call_coverage_rate": rate(known_calls, all_calls),
            "case_token_coverage_rate": rate(
                len(complete_token_rows), len(result_rows)
            ),
            "total_tokens_known": known_tokens,
            "prompt_tokens_known": sum(
                int(row["case_prompt_tokens"])
                for row in known_token_rows
                if row["case_prompt_tokens"] is not None
            ),
            "completion_tokens_known": sum(
                int(row["case_completion_tokens"])
                for row in known_token_rows
                if row["case_completion_tokens"] is not None
            ),
            "per_case_complete_usage": distribution(
                (
                    int(row["case_total_tokens"])
                    for row in complete_token_rows
                    if row["case_total_tokens"] is not None
                ),
                config["token_percentiles"],
            ),
            "tokens_per_correct_answer": (
                round(answer_tokens / len(correct_complete_token_rows), 2)
                if correct_complete_token_rows
                else None
            ),
            "wasted_tokens_known": wasted_tokens,
            "wasted_token_rate": share(wasted_tokens, known_tokens),
        },
        "funnel": {
            "expected_cases": len(expected_ids),
            "observed_results": len(result_rows),
            "execution_completed": completed,
            "route_passed": route_passed,
            "structure_passed": structure_passed,
            "answer_passed": answer_correct,
            "evaluation_passed": evaluation_passed,
        },
    }


def build_output(
    cases: list[dict[str, Any]],
    raw_results: list[dict[str, Any]],
    config: dict[str, Any],
    report_meta: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    case_by_id = {str(case["case_id"]): case for case in cases}
    duplicate_results = [
        case_id
        for case_id, count in Counter(
            str(result.get("case_id")) for result in raw_results
        ).items()
        if count > 1
    ]
    unknown_results = sorted(
        {
            str(result.get("case_id"))
            for result in raw_results
            if str(result.get("case_id")) not in case_by_id
        }
    )
    usable_results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in raw_results:
        case_id = str(result.get("case_id"))
        if case_id in case_by_id and case_id not in seen:
            usable_results.append(result)
            seen.add(case_id)
    rows = [
        normalize_result(result, case_by_id[str(result["case_id"])], config)
        for result in usable_results
    ]
    overall = summarize_group(cases, rows, config)
    by_course = {
        course: summarize_group(
            [case for case in cases if str(case["course"]) == course],
            rows,
            config,
        )
        for course in config["suite"]["courses"]
    }
    by_cohort = {
        cohort: summarize_group(
            [case for case in cases if cohort in case_cohorts(case, config)],
            rows,
            config,
        )
        for cohort in config["cohorts"]
    }
    failure_stages = Counter(
        row["failure_stage"]
        for row in rows
        if row["status"] in {"failed", "error", "timeout", "request_error", "cancelled"}
    )
    error_types = Counter(
        error
        for row in rows
        if row["status"] in {"failed", "error", "timeout", "request_error", "cancelled"}
        for error in row["error_types"]
    )
    summary = {
        "schema_version": "1.0",
        "source_report": {
            "schema_version": report_meta.get("schema_version"),
            "mode": report_meta.get("mode"),
            "started_at": report_meta.get("started_at"),
            "completed_at": report_meta.get("completed_at"),
        },
        "suite": {
            "expected_total": len(cases),
            "by_course": dict(Counter(str(case["course"]) for case in cases)),
            "by_role": dict(Counter(case_role(case) for case in cases)),
            "by_cohort": {
                name: sum(name in case_cohorts(case, config) for case in cases)
                for name in config["cohorts"]
            },
        },
        "data_quality": {
            "duplicate_result_case_ids": sorted(duplicate_results),
            "unknown_result_case_ids": unknown_results,
            "raw_result_count": len(raw_results),
            "usable_unique_result_count": len(rows),
            "warning": (
                "raw API reports do not contain answer_passed or model_calls; "
                "quality/token metrics remain N/A until an EvaluationRunner "
                "report is used"
                if rows and not any(row["evaluation_record"] for row in rows)
                else None
            ),
        },
        "overall": overall,
        "by_course": by_course,
        "by_cohort": by_cohort,
        "failure_breakdown": {
            "by_stage": dict(failure_stages.most_common()),
            "by_error_type": dict(error_types.most_common()),
        },
        "threshold_policy": config["threshold_policy"],
        "cost": {
            "value": None,
            "status": "disabled",
            "reason": config["cost_policy"]["reason"],
        },
    }
    visualization = {
        "schema_version": "1.0",
        "overview": overall,
        "course_comparison": [
            {"course": course, **metrics} for course, metrics in by_course.items()
        ],
        "cohort_comparison": [
            {"cohort": cohort, **metrics} for cohort, metrics in by_cohort.items()
        ],
        "failure_pareto": {
            "by_stage": dict(failure_stages.most_common()),
            "by_error_type": dict(error_types.most_common()),
        },
        "case_points": [
            {
                key: row[key]
                for key in (
                    "case_id",
                    "course",
                    "cohort",
                    "status",
                    "answer_passed",
                    "elapsed_ms",
                    "case_total_tokens",
                    "token_usage_complete",
                    "failure_stage",
                )
            }
            for row in rows
        ],
    }
    return summary, rows, visualization


def write_outputs(
    output_dir: Path,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    visualization: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "visualization_data.json").write_text(
        json.dumps(visualization, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    columns = [
        "case_id",
        "course",
        "cohort",
        "role",
        "input_type",
        "status",
        "execution_completed",
        "answer_passed",
        "answer_contract_passed",
        "answer_judge",
        "answer_score",
        "route_passed",
        "structure_passed",
        "safety_passed",
        "failure_stage",
        "error_types",
        "elapsed_ms",
        "case_total_tokens",
        "token_usage_complete",
        "model_count",
        "fallback_used",
        "retry_count",
        "trace_id",
    ]
    with (output_dir / "case_metrics.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            record = {key: row.get(key) for key in columns}
            record["error_types"] = "|".join(row["error_types"])
            writer.writerow(record)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="汇总真实题库 EvaluationRunner 报告，不调用模型或本地API"
    )
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = load_cases(args.cases.resolve())
    raw_results, report_meta = load_results(args.results.resolve())
    config = load_json(args.config.resolve())
    summary, rows, visualization = build_output(cases, raw_results, config, report_meta)
    write_outputs(args.output_dir.resolve(), summary, rows, visualization)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir.resolve()),
                "expected_cases": len(cases),
                "observed_results": len(rows),
                "strict_answer_accuracy": summary["overall"]["quality"][
                    "strict_answer_accuracy"
                ]["value"],
                "execution_success_rate": summary["overall"]["reliability"][
                    "execution_success_rate"
                ]["value"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
