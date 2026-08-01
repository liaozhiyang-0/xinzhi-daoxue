from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

from app.evaluation.contracts import EvaluationCase, EvaluationResult, SuiteReport


def build_statistics(
    cases: list[EvaluationCase], results: list[EvaluationResult]
) -> dict[str, Any]:
    case_by_id = {item.case_id: item for item in cases}
    by_course: dict[str, list[EvaluationResult]] = defaultdict(list)
    by_problem_type: dict[str, list[EvaluationResult]] = defaultdict(list)
    by_path: dict[str, list[EvaluationResult]] = defaultdict(list)
    model_counter: Counter[str] = Counter()
    for result in results:
        case = case_by_id[result.case_id]
        by_course[case.course].append(result)
        by_problem_type[case.problem_type or "unspecified"].append(result)
        by_path[str(result.actual.get("execution_path") or "none")].append(result)
        for call in result.model_calls:
            model_counter[str(call.get("model") or "unknown")] += 1
    elapsed = sorted(item.elapsed_ms for item in results)
    model_calls = sum(len(item.model_calls) for item in results)
    fallback_model_calls = sum(
        bool(call.get("fallback_used"))
        for result in results
        for call in result.model_calls
    )
    fallback_cases = sum(
        bool(result.actual.get("fallback_used"))
        or any(bool(call.get("fallback_used")) for call in result.model_calls)
        for result in results
    )
    high_risk_conflicts = sum(
        result.actual.get("verification_status") in {"conflict", "failed"}
        for result in results
        if result.actual.get("execution_path") == "HIGH_RISK"
    )
    judged_answers = [
        (case_by_id[result.case_id], result, evaluation)
        for result in results
        if isinstance(
            evaluation := result.actual.get("answer_evaluation"),
            dict,
        )
        and isinstance(evaluation.get("passed"), bool)
    ]
    judged_passed = sum(
        bool(evaluation["passed"]) for _, _, evaluation in judged_answers
    )
    answer_failures_by_course = Counter(
        case.course
        for case, _, evaluation in judged_answers
        if not bool(evaluation["passed"])
    )
    return {
        "by_course": _group_summary(by_course),
        "by_problem_type": _group_summary(by_problem_type),
        "by_execution_path": _group_summary(by_path),
        "routing_accuracy": _ratio(
            sum(item.route_passed for item in results), len(results)
        ),
        "tool_mismatches": Counter(
            mismatch.get("reason", "unknown")
            for result in results
            for mismatch in result.tool_mismatches
        ),
        "high_risk_conflicts": high_risk_conflicts,
        "model_calls_total": model_calls,
        "model_calls_by_model": dict(model_counter),
        "average_model_calls_per_case": _ratio(model_calls, len(results)),
        "average_elapsed_ms": round(mean(elapsed), 2) if elapsed else 0,
        "p50_elapsed_ms": median(elapsed) if elapsed else 0,
        "p95_elapsed_ms": _percentile(elapsed, 0.95),
        "fallback_rate": _ratio(fallback_cases, len(results)),
        "fallback_case_count": fallback_cases,
        "fallback_model_call_rate": _ratio(fallback_model_calls, model_calls),
        "timeout_rate": _ratio(
            sum(item.status == "timeout" for item in results), len(results)
        ),
        "answer_judge_total": len(judged_answers),
        "answer_judge_passed": judged_passed,
        "answer_judge_pass_rate": _ratio(judged_passed, len(judged_answers)),
        "answer_judge_failures_by_course": dict(answer_failures_by_course),
        "error_types": dict(
            Counter(error.value for item in results for error in item.error_types)
        ),
    }


def write_report(report: SuiteReport, root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "latest.json"
    markdown_path = root / "latest.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def render_markdown(report: SuiteReport) -> str:
    summary = report.summary
    statistics = report.statistics
    failures = [item for item in report.results if item.status != "passed"]
    answer_failures = [
        item
        for item in report.results
        if isinstance(item.actual.get("answer_evaluation"), dict)
        and item.actual["answer_evaluation"].get("passed") is False
    ]
    common_errors = Counter(
        error.value for item in failures for error in item.error_types
    )
    lines = [
        "# 多学科评测报告",
        "",
        "## 1. 执行摘要",
        "",
        f"- 模式：{report.mode}",
        (
            f"- 案例：{summary['total']}，通过：{summary['passed']}，"
            f"失败：{summary['failed']}，错误：{summary['errors']}，"
            f"超时：{summary['timeouts']}"
        ),
        f"- 总体通过率：{summary['pass_rate']:.2%}",
        "",
        "## 2. 按课程统计",
        "",
        "| 课程 | 案例 | 通过率 |",
        "|---|---:|---:|",
    ]
    for name, item in statistics["by_course"].items():
        lines.append(f"| {name} | {item['total']} | {item['pass_rate']:.2%} |")
    lines.extend(
        [
            "",
            "## 3. 关键指标",
            "",
            f"- 路由准确率：{statistics['routing_accuracy']:.2%}",
            (
                f"- 模型调用：{statistics['model_calls_total']}，平均每题 "
                f"{statistics['average_model_calls_per_case']:.2f}"
            ),
            (
                f"- 耗时：平均 {statistics['average_elapsed_ms']} ms，"
                f"P50 {statistics['p50_elapsed_ms']} ms，"
                f"P95 {statistics['p95_elapsed_ms']} ms"
            ),
            (
                f"- 案例回退率：{statistics['fallback_rate']:.2%}；"
                f"模型调用回退率："
                f"{statistics.get('fallback_model_call_rate', 0.0):.2%}；"
                f"超时率：{statistics['timeout_rate']:.2%}"
            ),
            f"- HIGH_RISK冲突：{statistics['high_risk_conflicts']}",
            (
                f"- 答案质量判定："
                f"{statistics.get('answer_judge_passed', 0)} / "
                f"{statistics.get('answer_judge_total', 0)} 通过"
                + (
                    f"（{statistics.get('answer_judge_pass_rate', 0.0):.2%}）"
                    if statistics.get("answer_judge_total", 0)
                    else ""
                )
            ),
            "",
            "## 4. 运行失败案例",
            "",
            "| case_id | 课程 | 失败阶段 | 错误类型 | 简短原因 | trace_id |",
            "|---|---|---|---|---|---|",
        ]
    )
    case_courses = {
        item.case_id: item.expected.get("course", "UNKNOWN") for item in report.results
    }
    for item in failures:
        errors = (
            ", ".join(error.value for error in item.error_types[:3])
            or "execution_error"
        )
        reason = (
            ", ".join(item.missing_keywords[:2])
            or ", ".join(item.warnings[:1])
            or errors
        )
        lines.append(
            f"| {item.case_id} | {case_courses[item.case_id]} | "
            f"{item.failure_stage or 'unknown'} | {errors} | {reason[:100]} | "
            f"{item.trace_id or '-'} |"
        )
    lines.extend(
        [
            "",
            "## 5. 答案质量未通过",
            "",
            "| case_id | 课程 | 分数 | 判定 | 简短原因 | trace_id |",
            "|---|---|---:|---|---|---|",
        ]
    )
    for item in answer_failures:
        evaluation = item.actual["answer_evaluation"]
        reason = " ".join(str(evaluation.get("reason", "")).split())
        reason = reason.replace("|", "\\|")
        lines.append(
            f"| {item.case_id} | {case_courses[item.case_id]} | "
            f"{float(evaluation.get('score', 0)):.2f} | "
            f"{evaluation.get('verdict', 'not_passed')} | {reason[:160]} | "
            f"{item.trace_id or '-'} |"
        )
    if not answer_failures:
        lines.append("| - | - | - | - | 本次没有答案质量判定失败 | - |")
    lines.extend(["", "## 6. 最常见错误与建议", ""])
    if common_errors:
        for error, count in common_errors.most_common(5):
            lines.append(f"- {error}: {count}")
    else:
        lines.append("- 本次没有运行级评分失败。")
    if answer_failures:
        by_course = Counter(
            case_courses[item.case_id] for item in answer_failures
        )
        lines.append(
            "- 答案质量未通过："
            + "，".join(
                f"{course} {count} 例"
                for course, count in by_course.most_common()
            )
            + "。"
        )
    lines.append("- 优先修复出现频率最高且位于最早失败阶段的问题。")
    return "\n".join(lines) + "\n"


def _group_summary(values: dict[str, list[EvaluationResult]]) -> dict[str, Any]:
    return {
        name: {
            "total": len(items),
            "passed": sum(item.status == "passed" for item in items),
            "pass_rate": _ratio(
                sum(item.status == "passed" for item in items), len(items)
            ),
        }
        for name, items in sorted(values.items())
    }


def _ratio(value: int | float, total: int) -> float:
    return float(value / total) if total else 0.0


def _percentile(values: list[int], quantile: float) -> int:
    if not values:
        return 0
    index = min(len(values) - 1, max(0, math.ceil(len(values) * quantile) - 1))
    return values[index]
