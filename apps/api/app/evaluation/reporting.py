from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from statistics import mean, median
from typing import Any

from app.evaluation.contracts import (
    EvaluationCase,
    EvaluationReportSummary,
    EvaluationResult,
    EvaluationRunMetadata,
    SuiteReport,
)

EVALUATION_ATTACHMENT_EXTENSIONS = {".jpeg", ".jpg", ".pdf", ".png", ".webp"}


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


def evaluation_case_ids_sha256(case_ids: Iterable[str]) -> str:
    """Hash the sorted report case-id set using the canonical v1 encoding."""

    return hashlib.sha256("\n".join(sorted(case_ids)).encode("utf-8")).hexdigest()


def evaluation_case_catalog_content_sha256(
    cases: Iterable[EvaluationCase],
) -> str:
    """Hash normalized case payloads without exposing their source text."""

    payload = [
        case.model_dump(mode="json")
        for case in sorted(cases, key=lambda item: item.case_id)
    ]
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluation_case_source_files_sha256(root: Path) -> str:
    """Hash source YAML/JSON paths and bytes for a case catalog manifest."""

    paths = sorted([*root.rglob("*.yaml"), *root.rglob("*.json")])
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_evaluation_attachment(
    reference: Any,
    *,
    root: Path,
    case_id: str,
    ordinal: int,
) -> tuple[str, Path]:
    if not isinstance(reference, dict):
        raise ValueError(
            f"{case_id}: attachment {ordinal} must be an object with a relative path"
        )
    raw_path = reference.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError(
            f"{case_id}: attachment {ordinal} requires a non-empty path"
        )
    normalized = raw_path.replace("\\", "/").strip()
    posix_path = PurePosixPath(normalized)
    candidate_path = Path(normalized)
    if (
        "\x00" in normalized
        or candidate_path.is_absolute()
        or bool(candidate_path.drive)
        or posix_path.is_absolute()
        or ".." in posix_path.parts
    ):
        raise ValueError(
            f"{case_id}: attachment {ordinal} path must stay inside the case root"
        )
    root_resolved = root.resolve()
    resolved = (root_resolved / Path(*posix_path.parts)).resolve()
    try:
        relative = resolved.relative_to(root_resolved).as_posix()
    except ValueError as exc:
        raise ValueError(
            f"{case_id}: attachment {ordinal} path escapes the case root"
        ) from exc
    if resolved.suffix.lower() not in EVALUATION_ATTACHMENT_EXTENSIONS:
        raise ValueError(
            f"{case_id}: attachment {ordinal} must be an image or PDF file"
        )
    if not resolved.is_file():
        raise ValueError(f"{case_id}: attachment {ordinal} file does not exist")
    return relative, resolved


def _file_sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def evaluation_case_attachment_manifest(
    cases: Iterable[EvaluationCase], root: Path
) -> tuple[str, int]:
    """Hash validated, root-relative image/PDF attachments without exposing paths."""

    entries: list[dict[str, Any]] = []
    for case in sorted(cases, key=lambda item: item.case_id):
        for ordinal, reference in enumerate(case.file_refs):
            relative, path = resolve_evaluation_attachment(
                reference,
                root=root,
                case_id=case.case_id,
                ordinal=ordinal,
            )
            content_sha256, size_bytes = _file_sha256(path)
            entries.append(
                {
                    "case_id": case.case_id,
                    "ordinal": ordinal,
                    "relative_path": relative,
                    "size_bytes": size_bytes,
                    "content_sha256": content_sha256,
                }
            )
    encoded = json.dumps(
        entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), len(entries)


def evaluation_filters_sha256(filters: dict[str, Any] | None) -> str:
    """Hash report filters using a stable JSON representation."""

    payload = filters or {}
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_evaluation_run_metadata(
    cases: list[EvaluationCase],
    *,
    run_id: str,
    implementation_fingerprint: str,
    filters: dict[str, Any] | None = None,
    case_catalog_sha256: str = "",
    case_catalog_content_sha256: str = "",
    case_source_files_sha256: str = "",
    case_attachment_manifest_sha256: str = "",
    case_attachment_count: int = 0,
) -> EvaluationRunMetadata:
    """Build reproducibility metadata without retaining prompts or answers."""

    case_ids = [item.case_id for item in cases]
    return EvaluationRunMetadata(
        run_id=run_id,
        case_count=len(cases),
        case_ids_sha256=evaluation_case_ids_sha256(case_ids),
        case_catalog_sha256=case_catalog_sha256,
        case_catalog_content_sha256=case_catalog_content_sha256,
        case_catalog_content_version=(
            "canonical_evaluation_case_payloads.v1"
            if case_catalog_content_sha256
            else None
        ),
        case_source_files_sha256=case_source_files_sha256,
        case_source_files_version=(
            "evaluation_case_source_files.v1"
            if case_source_files_sha256
            else None
        ),
        case_attachment_manifest_sha256=case_attachment_manifest_sha256,
        case_attachment_manifest_version=(
            "evaluation_case_attachments.v1"
            if case_attachment_manifest_sha256
            else None
        ),
        case_attachment_count=case_attachment_count,
        filters_sha256=evaluation_filters_sha256(filters),
        implementation_fingerprint=implementation_fingerprint,
    )


def build_report_summary(report: SuiteReport) -> EvaluationReportSummary:
    status_counts = Counter(item.status for item in report.results)
    result_status_counts = {
        str(status): count for status, count in status_counts.items()
    }
    # The summary endpoint must not expose the size of the case catalog as if
    # it were part of the summary payload.  Full reproducibility metadata
    # remains available in the offline report itself.
    summary_metadata = report.run_metadata.model_copy(update={"case_count": 0})
    return EvaluationReportSummary(
        schema_version=report.schema_version,
        mode=report.mode,
        started_at=report.started_at,
        completed_at=report.completed_at,
        filters=report.filters,
        summary=report.summary,
        statistics=report.statistics,
        run_metadata=summary_metadata,
        result_status_counts=result_status_counts,
    )


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
