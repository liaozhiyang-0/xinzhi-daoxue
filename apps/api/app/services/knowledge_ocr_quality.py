from __future__ import annotations

from collections import Counter
from typing import Any

OCR_QUALITY_SUMMARY_SCHEMA = "ocr_quality_summary.v1"


def _decision_evidence_summary(
    queue: dict[str, Any], course_id: str | None
) -> dict[str, Any]:
    reports = queue.get("decision_reports", {})
    selected_reports = {
        str(key): value
        for key, value in reports.items()
        if isinstance(value, dict)
        and (
            course_id is None
            or str(value.get("course_id", key)).upper() == course_id
        )
    }
    rows = [
        item
        for item in queue.get("rows", [])
        if isinstance(item, dict)
        and (course_id is None or str(item.get("course_id", "")).upper() == course_id)
    ]
    decided_rows = [
        item
        for item in rows
        if str(item.get("review_decision", "pending")) != "pending"
    ]
    missing_evidence_refs = sum(
        not isinstance(item.get("evidence_refs"), list)
        or not [str(ref).strip() for ref in item.get("evidence_refs", []) if ref]
        for item in decided_rows
    )
    stale_checksum_errors = sum(
        sum(
            str(error).startswith("stale_checksum:")
            for error in report.get("errors", [])
        )
        for report in selected_reports.values()
    )
    invalid_error_count = sum(
        len(report.get("errors", []))
        for report in selected_reports.values()
        if not report.get("valid", False)
    )
    report_valid = (
        all(bool(report.get("valid")) for report in selected_reports.values())
        if selected_reports
        else None
    )
    review_complete = bool(selected_reports) and all(
        bool(report.get("review_complete")) for report in selected_reports.values()
    )
    if not selected_reports:
        status = "decision_file_missing"
        next_action = "create_pending_ocr_decision_file"
    elif stale_checksum_errors:
        status = "invalid_or_stale"
        next_action = "regenerate_queue_and_reconcile_stale_decisions"
    elif invalid_error_count:
        status = "invalid_or_stale"
        next_action = "fix_ocr_decision_validation_errors"
    elif not review_complete:
        status = "pending"
        next_action = "complete_pending_ocr_teacher_decisions"
    elif missing_evidence_refs:
        status = "complete_without_evidence"
        next_action = "add_evidence_refs_to_ocr_decisions"
    else:
        status = "complete_with_evidence"
        next_action = "keep_ocr_decision_evidence_immutable"
    return {
        "status": status,
        "decision_file_present": bool(selected_reports),
        "report_valid": report_valid,
        "review_complete": review_complete,
        "candidate_count": len(rows),
        "decided_count": len(decided_rows),
        "pending_count": len(rows) - len(decided_rows),
        "rows_missing_evidence_refs": missing_evidence_refs,
        "stale_checksum_error_count": stale_checksum_errors,
        "validation_error_count": invalid_error_count,
        "next_action": next_action,
    }


def _quality_row(raw: dict[str, Any]) -> dict[str, Any]:
    candidate_pages = [
        int(page)
        for page in raw.get("ocr_candidate_pages", [])
        if isinstance(page, int) and page >= 1
    ]
    return {
        "queue_id": str(raw.get("queue_id", "")),
        "course_id": str(raw.get("course_id", "")),
        "document_id": str(raw.get("document_id", "")),
        "relative_path": str(raw.get("relative_path", "")),
        "file_name": str(raw.get("file_name", "")),
        "page_count": raw.get("page_count"),
        "parse_status": str(raw.get("parse_status", "unknown")),
        "quality_status": str(raw.get("quality_status", "unknown")),
        "index_status": str(raw.get("index_status", "unknown")),
        "ocr_required": bool(raw.get("ocr_required", False)),
        "ocr_status": str(raw.get("ocr_status", "unknown")),
        "ocr_candidate_pages": sorted(set(candidate_pages)),
        "candidate_page_count": len(set(candidate_pages)),
        "low_text_page_count": int(raw.get("low_text_page_count", 0) or 0),
        "page_coverage_ratio": raw.get("page_coverage_ratio"),
        "manual_review_required": bool(raw.get("manual_review_required", False)),
        "warnings": [str(item) for item in raw.get("warnings", [])],
        "priority": str(raw.get("priority", "unknown")),
        "review_action": str(raw.get("review_action", "unknown")),
        "review_decision": str(raw.get("review_decision", "pending")),
    }


def build_ocr_quality_summary(
    queue: dict[str, Any], course_id: str | None = None
) -> dict[str, Any]:
    """Summarize observed PDF text-layer evidence without executing OCR."""
    normalized_course = course_id.strip().upper() if course_id else None
    raw_rows = [
        item
        for item in queue.get("rows", [])
        if isinstance(item, dict)
        and (
            normalized_course is None
            or str(item.get("course_id", "")).upper() == normalized_course
        )
    ]
    rows = [_quality_row(item) for item in raw_rows]
    rows.sort(key=lambda item: (item["course_id"], item["relative_path"]))
    page_coverage_values = [
        float(item["page_coverage_ratio"])
        for item in rows
        if isinstance(item["page_coverage_ratio"], (int, float))
    ]
    known_page_counts = [
        int(item["page_count"])
        for item in rows
        if isinstance(item["page_count"], int) and item["page_count"] >= 0
    ]
    summary = {
        "candidate_document_count": len(rows),
        "documents_with_ocr_candidates": sum(
            bool(item["ocr_candidate_pages"]) for item in rows
        ),
        "candidate_page_count": sum(item["candidate_page_count"] for item in rows),
        "documents_with_unknown_page_count": len(rows) - len(known_page_counts),
        "total_known_page_count": sum(known_page_counts),
        "documents_with_page_coverage": len(page_coverage_values),
        "average_page_coverage_ratio": (
            round(sum(page_coverage_values) / len(page_coverage_values), 4)
            if page_coverage_values
            else None
        ),
        "ocr_required_document_count": sum(item["ocr_required"] for item in rows),
        "manual_review_document_count": sum(
            item["manual_review_required"] for item in rows
        ),
        "parse_status_counts": dict(
            Counter(item["parse_status"] for item in rows)
        ),
        "quality_status_counts": dict(
            Counter(item["quality_status"] for item in rows)
        ),
        "ocr_status_counts": dict(Counter(item["ocr_status"] for item in rows)),
        "scope": "read_only_ocr_review_candidates",
    }
    audit_status = (
        "available"
        if rows and known_page_counts
        else "partial"
        if rows
        else "unavailable"
    )
    return {
        "schema_version": OCR_QUALITY_SUMMARY_SCHEMA,
        "course_id": normalized_course or "ALL",
        "mode": "read_only_text_layer_audit",
        "runtime_loaded": False,
        "ocr_execution_performed": False,
        "audit_status": audit_status,
        "decision_evidence": _decision_evidence_summary(queue, normalized_course),
        "summary": summary,
        "rows": rows,
        "cache_status": str(queue.get("cache_status", "unknown")),
        "cache_backend": str(queue.get("cache_backend", "none")),
        "source_fingerprint": str(queue.get("source_fingerprint", "")),
        "snapshot_age_seconds": float(queue.get("snapshot_age_seconds", 0.0)),
    }
