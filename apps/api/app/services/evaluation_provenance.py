from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from math import isclose
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.evaluation.contracts import SuiteReport
from app.evaluation.reporting import (
    evaluation_case_ids_sha256,
    evaluation_filters_sha256,
)

EVALUATION_REPORT_PATH = PROJECT_ROOT / "evaluation" / "reports" / "latest.json"
EVALUATION_PROVENANCE_SCHEMA = "course_evaluation_provenance.v1"
_DATA_BOUNDARY = [
    "summary_only_no_case_answers",
    "synthetic_or_local_evaluation_not_learning_effectiveness",
    "model_trace_is_bounded_process_memory",
]


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return 0
    return max(normalized, 0)


def _bounded_ratio(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    return normalized if 0 <= normalized <= 1 else None


def _parse_report_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _metadata_is_present(report: SuiteReport) -> bool:
    """Treat only non-default reproducibility metadata as present."""

    if "run_metadata" not in report.model_fields_set:
        return False
    metadata = report.run_metadata
    return all(
        (
            bool(metadata.run_id),
            bool(metadata.case_ids_sha256),
            bool(metadata.filters_sha256),
            bool(metadata.implementation_fingerprint),
        )
    )


def _base_provenance(course: str, report_ref: str) -> dict[str, Any]:
    snapshot_at = datetime.now(UTC).isoformat()
    return {
        "schema_version": EVALUATION_PROVENANCE_SCHEMA,
        "status": "report_missing",
        "course_id": course,
        "report_path": report_ref,
        "report_present": False,
        "report_valid": None,
        "report_schema_version": None,
        "report_mode": None,
        "started_at": None,
        "completed_at": None,
        "report_filters": {},
        "snapshot_at": snapshot_at,
        "report_age_seconds": None,
        "temporal_consistency": "not_checkable",
        "report_case_count": None,
        "course_case_count": 0,
        "course_passed_count": 0,
        "course_pass_rate": None,
        "run_metadata_present": False,
        "run_id": None,
        "case_ids_sha256": None,
        "case_catalog_sha256": None,
        "case_catalog_content_sha256": None,
        "case_catalog_content_version": None,
        "case_source_files_sha256": None,
        "case_source_files_version": None,
        "case_attachment_manifest_sha256": None,
        "case_attachment_manifest_version": None,
        "case_attachment_count": None,
        "filters_sha256": None,
        "implementation_fingerprint": None,
        "execution_channel": None,
        "model_trace_retention": None,
        "raw_prompts_stored": None,
        "raw_results_included": False,
        "data_boundary": list(_DATA_BOUNDARY),
        "consistency": {
            "status": "not_checkable",
            "schema_version_supported": False,
            "summary_result_count_match": False,
            "summary_status_counts_match": False,
            "course_statistics_match": False,
            "metadata_case_count_match": None,
            "metadata_case_ids_match": None,
            "metadata_filters_match": None,
            "case_catalog_present": None,
            "case_catalog_content_present": None,
            "case_source_files_present": None,
            "case_attachment_manifest_present": None,
            "report_completed_at_parseable": False,
            "report_completed_at_not_future": None,
            "issues": ["report_not_validated"],
        },
    }


def _report_consistency(
    report: SuiteReport,
    *,
    metadata_present: bool,
    snapshot_at: datetime,
) -> dict[str, Any]:
    results = report.results
    issues: list[str] = []
    schema_version_supported = report.schema_version == "1.0"
    if not schema_version_supported:
        issues.append("unsupported_schema_version")

    summary_total = _nonnegative_int(report.summary.get("total"))
    summary_result_count_match = summary_total == len(results)
    if not summary_result_count_match:
        issues.append("summary_total_mismatch")

    expected_summary = {
        "total": len(results),
        "passed": sum(item.status == "passed" for item in results),
        "failed": sum(item.status == "failed" for item in results),
        "errors": sum(item.status == "error" for item in results),
        "timeouts": sum(item.status == "timeout" for item in results),
        "cached": sum(
            "result_loaded_from_cache" in item.warnings for item in results
        ),
    }
    summary_status_counts_match = all(
        _nonnegative_int(report.summary.get(key)) == value
        for key, value in expected_summary.items()
    )
    if not summary_status_counts_match:
        issues.append("summary_status_counts_mismatch")

    result_case_ids = [item.case_id for item in results]
    if len(result_case_ids) != len(set(result_case_ids)):
        issues.append("duplicate_result_case_ids")

    result_by_course: Counter[str] = Counter()
    passed_by_course: Counter[str] = Counter()
    for item in results:
        course = str(item.expected.get("course", "")).strip().upper()
        if not course:
            issues.append("result_course_missing")
            continue
        result_by_course[course] += 1
        if item.status == "passed":
            passed_by_course[course] += 1

    raw_by_course = report.statistics.get("by_course", {})
    course_statistics_match = isinstance(raw_by_course, dict)
    if not course_statistics_match:
        issues.append("course_statistics_missing")
    else:
        if set(raw_by_course) != set(result_by_course):
            course_statistics_match = False
            issues.append("course_statistics_course_set_mismatch")
        for course, total in result_by_course.items():
            item = raw_by_course.get(course)
            if not isinstance(item, dict):
                course_statistics_match = False
                issues.append(f"course_statistics_missing:{course}")
                continue
            passed = passed_by_course[course]
            rate = _bounded_ratio(item.get("pass_rate"))
            expected_rate = passed / total if total else 0.0
            if (
                _nonnegative_int(item.get("total")) != total
                or _nonnegative_int(item.get("passed")) != passed
                or rate is None
                or not isclose(rate, expected_rate, rel_tol=1e-9, abs_tol=1e-9)
            ):
                course_statistics_match = False
                issues.append(f"course_statistics_values_mismatch:{course}")

    metadata_case_count_match: bool | None = None
    metadata_case_ids_match: bool | None = None
    metadata_filters_match: bool | None = None
    case_catalog_present: bool | None = None
    case_catalog_content_present: bool | None = None
    case_source_files_present: bool | None = None
    case_attachment_manifest_present: bool | None = None
    if metadata_present:
        metadata_case_count_match = report.run_metadata.case_count == len(results)
        metadata_case_ids_match = (
            report.run_metadata.case_ids_sha256
            == evaluation_case_ids_sha256(result_case_ids)
        )
        if not metadata_case_count_match:
            issues.append("metadata_case_count_mismatch")
        if not metadata_case_ids_match:
            issues.append("metadata_case_ids_hash_mismatch")
        metadata_filters_match = (
            report.run_metadata.filters_sha256
            == evaluation_filters_sha256(report.filters)
        )
        if not metadata_filters_match:
            issues.append("metadata_filters_hash_mismatch")
        case_catalog_present = bool(report.run_metadata.case_catalog_sha256)
        case_catalog_content_present = bool(
            report.run_metadata.case_catalog_content_sha256
            and report.run_metadata.case_catalog_content_version
            == "canonical_evaluation_case_payloads.v1"
        )
        case_source_files_present = bool(
            report.run_metadata.case_source_files_sha256
            and report.run_metadata.case_source_files_version
            == "evaluation_case_source_files.v1"
        )
        case_attachment_manifest_present = bool(
            report.run_metadata.case_attachment_manifest_sha256
            and report.run_metadata.case_attachment_manifest_version
            == "evaluation_case_attachments.v1"
        )

    completed_at = _parse_report_time(report.completed_at)
    report_completed_at_parseable = completed_at is not None
    report_completed_at_not_future: bool | None = None
    if completed_at is None:
        issues.append("completed_at_invalid")
    else:
        report_completed_at_not_future = completed_at <= snapshot_at
        if not report_completed_at_not_future:
            issues.append("completed_at_in_future")

    status = "inconsistent" if issues else "consistent"
    if (
        status == "consistent"
        and (
            not metadata_present
            or case_catalog_present is False
            or case_catalog_content_present is False
            or case_source_files_present is False
            or case_attachment_manifest_present is False
        )
    ):
        status = "partial"
    return {
        "status": status,
        "schema_version_supported": schema_version_supported,
        "summary_result_count_match": summary_result_count_match,
        "summary_status_counts_match": summary_status_counts_match,
        "course_statistics_match": course_statistics_match,
        "metadata_case_count_match": metadata_case_count_match,
        "metadata_case_ids_match": metadata_case_ids_match,
        "metadata_filters_match": metadata_filters_match,
        "case_catalog_present": case_catalog_present,
        "case_catalog_content_present": case_catalog_content_present,
        "case_source_files_present": case_source_files_present,
        "case_attachment_manifest_present": case_attachment_manifest_present,
        "report_completed_at_parseable": report_completed_at_parseable,
        "report_completed_at_not_future": report_completed_at_not_future,
        "issues": sorted(set(issues)),
    }


def build_evaluation_provenance(
    report_path: Path,
    course: str,
    *,
    report_ref: str = "evaluation/reports/latest.json",
) -> dict[str, Any]:
    """Read a validated, bounded evaluation report view for one course.

    This function never returns case results, answers, prompts, or model traces.
    Invalid reports are represented as evidence gaps instead of being repaired or
    interpreted heuristically.
    """

    normalized_course = course.strip().upper()
    result = _base_provenance(normalized_course, report_ref)
    if not report_path.is_file():
        return result

    result["report_present"] = True
    try:
        report = SuiteReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        result["status"] = "report_invalid"
        result["report_valid"] = False
        return result

    metadata_present = _metadata_is_present(report)
    snapshot_at = _parse_report_time(result["snapshot_at"]) or datetime.now(UTC)
    result["consistency"] = _report_consistency(
        report,
        metadata_present=metadata_present,
        snapshot_at=snapshot_at,
    )
    completed_at = _parse_report_time(report.completed_at)
    if completed_at is None:
        temporal_consistency = "invalid"
        report_age_seconds = None
    elif completed_at > snapshot_at:
        temporal_consistency = "future"
        report_age_seconds = None
    else:
        temporal_consistency = "valid"
        report_age_seconds = max(
            0.0, (snapshot_at - completed_at).total_seconds()
        )
    result.update(
        {
            "report_valid": True,
            "report_schema_version": report.schema_version,
            "report_mode": str(report.mode),
            "started_at": report.started_at,
            "completed_at": report.completed_at,
            "report_filters": dict(report.filters),
            "report_age_seconds": report_age_seconds,
            "temporal_consistency": temporal_consistency,
            "report_case_count": _nonnegative_int(report.summary.get("total")),
        }
    )
    course_stats = report.statistics.get("by_course", {})
    if not isinstance(course_stats, dict):
        course_stats = {}
    raw_course_stats = course_stats.get(normalized_course)
    if not isinstance(raw_course_stats, dict):
        result["status"] = "course_not_covered"
        return result

    result.update(
        {
            "status": "available",
            "course_case_count": _nonnegative_int(raw_course_stats.get("total")),
            "course_passed_count": _nonnegative_int(raw_course_stats.get("passed")),
            "course_pass_rate": _bounded_ratio(raw_course_stats.get("pass_rate")),
        }
    )
    raw_metadata = report.model_dump(mode="python").get("run_metadata")
    metadata = (
        raw_metadata
        if metadata_present and isinstance(raw_metadata, dict)
        else {}
    )
    result.update(
        {
            "run_metadata_present": metadata_present,
            "run_id": str(metadata.get("run_id")) if metadata.get("run_id") else None,
            "case_ids_sha256": (
                str(metadata.get("case_ids_sha256"))
                if metadata.get("case_ids_sha256")
                else None
            ),
            "implementation_fingerprint": (
                str(metadata.get("implementation_fingerprint"))
                if metadata.get("implementation_fingerprint")
                else None
            ),
            "case_catalog_sha256": (
                str(metadata.get("case_catalog_sha256"))
                if metadata.get("case_catalog_sha256")
                else None
            ),
            "case_catalog_content_sha256": (
                str(metadata.get("case_catalog_content_sha256"))
                if metadata.get("case_catalog_content_sha256")
                else None
            ),
            "case_catalog_content_version": (
                str(metadata.get("case_catalog_content_version"))
                if metadata.get("case_catalog_content_version")
                else None
            ),
            "case_source_files_sha256": (
                str(metadata.get("case_source_files_sha256"))
                if metadata.get("case_source_files_sha256")
                else None
            ),
            "case_source_files_version": (
                str(metadata.get("case_source_files_version"))
                if metadata.get("case_source_files_version")
                else None
            ),
            "case_attachment_manifest_sha256": (
                str(metadata.get("case_attachment_manifest_sha256"))
                if metadata.get("case_attachment_manifest_sha256")
                else None
            ),
            "case_attachment_manifest_version": (
                str(metadata.get("case_attachment_manifest_version"))
                if metadata.get("case_attachment_manifest_version")
                else None
            ),
            "case_attachment_count": (
                _nonnegative_int(metadata.get("case_attachment_count"))
                if metadata.get("case_attachment_count") is not None
                else None
            ),
            "filters_sha256": (
                str(metadata.get("filters_sha256"))
                if metadata.get("filters_sha256")
                else None
            ),
            "execution_channel": (
                str(metadata.get("execution_channel"))
                if metadata.get("execution_channel")
                else None
            ),
            "model_trace_retention": (
                str(metadata.get("model_trace_retention"))
                if metadata.get("model_trace_retention")
                else None
            ),
            "raw_prompts_stored": (
                metadata.get("raw_prompts_stored")
                if isinstance(metadata.get("raw_prompts_stored"), bool)
                else None
            ),
        }
    )
    return result
