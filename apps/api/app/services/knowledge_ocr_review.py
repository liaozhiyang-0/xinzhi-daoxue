from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from app.services.knowledge_audit import AuditResult, ManifestEntry, stable_id

OCR_REVIEW_QUEUE_SCHEMA = "ocr_review_queue.v1"
OCR_REVIEW_DECISION_SCHEMA = "ocr_review_decisions.v1"
OCR_REVIEW_DECISIONS = frozenset(
    {
        "pending",
        "approve_existing_text",
        "request_ocr",
        "split_pdf",
        "reject_source",
        "needs_manual_inspection",
    }
)


def _review_action(entry: ManifestEntry) -> str:
    if "pdf_file_exceeds_parse_limit" in entry.warnings:
        return "split_or_review_parse_limit"
    if entry.parse_status == "ocr_required":
        return "select_pages_for_ocr"
    if "low_text_pages_require_ocr_review" in entry.warnings:
        return "confirm_low_text_pages"
    if entry.parse_status != "parsed":
        return "inspect_pdf_parse_failure"
    return "teacher_confirm_before_index"


def _priority(entry: ManifestEntry) -> str:
    if entry.parse_status != "parsed":
        return "high"
    return "medium"


def _queue_row(entry: ManifestEntry) -> dict[str, Any]:
    return {
        "queue_id": stable_id(
            "OCR",
            entry.course_id,
            entry.relative_path.casefold(),
            entry.checksum,
        ),
        "review_status": "pending_teacher_review",
        "priority": _priority(entry),
        "review_action": _review_action(entry),
        "course_id": entry.course_id,
        "document_id": entry.document_id,
        "source_path": entry.source_path,
        "relative_path": entry.relative_path,
        "file_name": entry.file_name,
        "file_size": entry.file_size,
        "checksum": entry.checksum,
        "page_count": entry.page_count,
        "parse_status": entry.parse_status,
        "quality_status": entry.quality_status,
        "index_status": entry.index_status,
        "warnings": list(entry.warnings),
        "ocr_required": entry.ocr_required,
        "ocr_status": entry.ocr_status,
        "ocr_candidate_pages": list(entry.ocr_candidate_pages),
        "ocr_confidence": entry.ocr_confidence,
        "ocr_confidence_source": entry.ocr_confidence_source,
        "manual_review_required": entry.manual_review_required,
        "low_text_page_count": entry.low_text_page_count,
        "page_coverage_ratio": entry.page_coverage_ratio,
    }


def build_ocr_review_queue(audit: AuditResult) -> dict[str, Any]:
    """Build a deterministic draft queue from a read-only course audit."""

    rows = [
        _queue_row(entry)
        for entry in audit.manifest
        if entry.source_type == "pdf"
        and (entry.manual_review_required or entry.index_status != "direct")
    ]
    rows.sort(key=lambda item: (str(item["course_id"]), str(item["relative_path"])))
    by_course: Counter[str] = Counter(str(item["course_id"]) for item in rows)
    by_priority: Counter[str] = Counter(str(item["priority"]) for item in rows)
    by_action: Counter[str] = Counter(str(item["review_action"]) for item in rows)
    return {
        "schema_version": OCR_REVIEW_QUEUE_SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "read_only_draft",
        "runtime_loaded": False,
        "ocr_execution_performed": False,
        "summary": {
            "candidate_count": len(rows),
            "by_course": dict(sorted(by_course.items())),
            "by_priority": dict(sorted(by_priority.items())),
            "by_action": dict(sorted(by_action.items())),
            "rows_with_confidence": sum(
                item["ocr_confidence"] is not None for item in rows
            ),
        },
        "rows": rows,
    }


def build_ocr_decision_template(
    queue: dict[str, Any], course_id: str
) -> dict[str, Any]:
    """Create a pending-only decision document for one course."""

    rows = [
        item for item in queue.get("rows", []) if item.get("course_id") == course_id
    ]
    rows.sort(key=lambda item: str(item.get("relative_path", "")))
    return {
        "schema_version": OCR_REVIEW_DECISION_SCHEMA,
        "course_id": course_id,
        "runtime_loaded": False,
        "review_status": "pending_teacher_review",
        "reviewer": None,
        "reviewed_at": None,
        "decisions": [
            {
                "queue_id": item["queue_id"],
                "checksum": item["checksum"],
                "decision": "pending",
                "reviewer": None,
                "reviewed_at": None,
                "evidence_refs": [],
                "note": "",
            }
            for item in rows
        ],
    }


def build_ocr_decision_document(
    queue: dict[str, Any],
    course_id: str,
    decisions: list[dict[str, Any]],
    *,
    reviewer: str,
    reviewed_at: str,
) -> dict[str, Any]:
    """Build a server-owned decision document from a teacher save request."""

    normalized_reviewer = reviewer.strip()
    if not normalized_reviewer:
        raise ValueError("reviewer_required")
    current_rows = {
        str(item.get("queue_id")): item
        for item in queue.get("rows", [])
        if isinstance(item, dict) and item.get("queue_id")
    }
    normalized_rows: list[dict[str, Any]] = []
    has_decided_row = False
    for raw in decisions:
        queue_id = str(raw.get("queue_id", ""))
        decision = str(raw.get("decision", "pending"))
        evidence_refs = [
            str(reference).strip()
            for reference in raw.get("evidence_refs", [])
            if str(reference).strip()
        ]
        if decision != "pending" and not evidence_refs:
            raise ValueError(
                f"evidence_refs_required:{queue_id}"
            )
        has_decided_row = has_decided_row or decision != "pending"
        current = current_rows.get(queue_id, {})
        current_refs = [
            str(reference).strip()
            for reference in current.get("evidence_refs", [])
            if str(reference).strip()
        ]
        unchanged = (
            decision == str(current.get("review_decision", "pending"))
            and evidence_refs == current_refs
            and str(raw.get("note", "")).strip()
            == str(current.get("decision_note", "")).strip()
        )
        row_reviewer = (
            str(current.get("reviewer", "")).strip()
            if unchanged and current.get("reviewer")
            else normalized_reviewer
        )
        row_reviewed_at = (
            str(current.get("reviewed_at", "")).strip()
            if unchanged and current.get("reviewed_at")
            else reviewed_at
        )
        normalized_rows.append(
            {
                "queue_id": queue_id,
                "checksum": str(raw.get("checksum", "")),
                "decision": decision,
                "reviewer": row_reviewer if decision != "pending" else None,
                "reviewed_at": row_reviewed_at if decision != "pending" else None,
                "evidence_refs": list(dict.fromkeys(evidence_refs)),
                "note": str(raw.get("note", "")).strip(),
            }
        )
    return {
        "schema_version": OCR_REVIEW_DECISION_SCHEMA,
        "course_id": course_id,
        "runtime_loaded": False,
        "review_status": (
            "teacher_review_complete" if has_decided_row else "pending_teacher_review"
        ),
        "reviewer": normalized_reviewer if has_decided_row else None,
        "reviewed_at": reviewed_at if has_decided_row else None,
        "decisions": normalized_rows,
    }


def write_ocr_decision_document(path: Path, document: dict[str, Any]) -> None:
    """Persist a validated decision document with an atomic replace."""

    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            yaml.safe_dump(
                document,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            ),
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _decision_error(queue_row: dict[str, Any], decision: str) -> str | None:
    parse_status = str(queue_row.get("parse_status", ""))
    warnings = {str(item) for item in queue_row.get("warnings", [])}
    if decision == "approve_existing_text" and parse_status != "parsed":
        return "approve_existing_text_requires_parsed_pdf"
    if decision == "request_ocr" and not (
        bool(queue_row.get("ocr_required")) or parse_status == "ocr_required"
    ):
        return "request_ocr_requires_ocr_candidate"
    if decision == "split_pdf" and "pdf_file_exceeds_parse_limit" not in warnings:
        return "split_pdf_requires_parse_limit_warning"
    return None


def validate_ocr_decisions(
    queue: dict[str, Any], decision_document: dict[str, Any]
) -> dict[str, Any]:
    """Validate teacher decisions against the exact queue snapshot."""

    errors: list[str] = []
    if queue.get("schema_version") != OCR_REVIEW_QUEUE_SCHEMA:
        errors.append("queue_schema_version_invalid")
    if decision_document.get("schema_version") != OCR_REVIEW_DECISION_SCHEMA:
        errors.append("schema_version_invalid")
    if decision_document.get("runtime_loaded") is not False:
        errors.append("runtime_loaded_must_be_false")
    if decision_document.get("review_status") not in {
        "pending_teacher_review",
        "teacher_review_complete",
    }:
        errors.append("review_status_invalid")
    course_id = str(decision_document.get("course_id", ""))
    if not course_id:
        errors.append("course_id_required")
    queue_rows = {
        str(item.get("queue_id")): item
        for item in queue.get("rows", [])
        if item.get("course_id") == course_id
    }
    if course_id and not queue_rows and not any(
        item.get("course_id") == course_id for item in queue.get("rows", [])
    ):
        errors.append("course_id_not_in_queue")
    raw_decisions = decision_document.get("decisions", [])
    if not isinstance(raw_decisions, list):
        errors.append("decisions_must_be_list")
        raw_decisions = []

    seen: set[str] = set()
    valid_decisions: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_decisions):
        if not isinstance(raw, dict):
            errors.append(f"decision_{index}_must_be_object")
            continue
        queue_id = str(raw.get("queue_id", ""))
        if not queue_id:
            errors.append(f"decision_{index}_queue_id_required")
            continue
        if queue_id in seen:
            errors.append(f"duplicate_queue_id:{queue_id}")
            continue
        seen.add(queue_id)
        queue_row = queue_rows.get(queue_id)
        if queue_row is None:
            errors.append(f"unknown_queue_id:{queue_id}")
            continue
        if str(raw.get("checksum", "")) != str(queue_row["checksum"]):
            errors.append(f"stale_checksum:{queue_id}")
        decision = str(raw.get("decision", ""))
        if decision not in OCR_REVIEW_DECISIONS:
            errors.append(f"invalid_decision:{queue_id}")
            continue
        decision_error = _decision_error(queue_row, decision)
        if decision_error:
            errors.append(f"{decision_error}:{queue_id}")
        if decision != "pending" and not str(raw.get("reviewer", "")).strip():
            errors.append(f"reviewer_required:{queue_id}")
        if decision != "pending" and not str(raw.get("reviewed_at", "")).strip():
            errors.append(f"reviewed_at_required:{queue_id}")
        if decision != "pending":
            try:
                datetime.fromisoformat(str(raw.get("reviewed_at", "")))
            except ValueError:
                errors.append(f"reviewed_at_invalid:{queue_id}")
        if "ocr_confidence" in raw:
            errors.append(f"ocr_confidence_must_not_be_supplied:{queue_id}")
        if "evidence_refs" in raw and not isinstance(raw["evidence_refs"], list):
            errors.append(f"evidence_refs_must_be_list:{queue_id}")
        valid_decisions[queue_id] = raw

    missing = sorted(set(queue_rows) - seen)
    errors.extend(f"missing_queue_id:{queue_id}" for queue_id in missing)
    decided_count = sum(
        str(item.get("decision", "pending")) != "pending"
        for item in valid_decisions.values()
    )
    merged_rows = []
    decision_counts: Counter[str] = Counter()
    for queue_row in sorted(
        queue_rows.values(), key=lambda item: str(item.get("relative_path", ""))
    ):
        decision_row = valid_decisions.get(str(queue_row["queue_id"]), {})
        decision = str(decision_row.get("decision", "pending"))
        decision_counts[decision] += 1
        merged_rows.append(
            {
                **queue_row,
                "review_decision": decision,
                "reviewer": decision_row.get("reviewer"),
                "reviewed_at": decision_row.get("reviewed_at"),
                "evidence_refs": decision_row.get("evidence_refs", []),
                "decision_note": decision_row.get("note", ""),
            }
        )
    return {
        "schema_version": OCR_REVIEW_DECISION_SCHEMA,
        "valid": not errors,
        "course_id": course_id,
        "queue_candidate_count": len(queue_rows),
        "decision_count": len(valid_decisions),
        "decided_count": decided_count,
        "pending_count": len(queue_rows) - decided_count,
        "review_complete": not missing and decided_count == len(queue_rows),
        "decision_counts": dict(sorted(decision_counts.items())),
        "errors": errors,
        "runtime_loaded": False,
        "rows": merged_rows,
    }
