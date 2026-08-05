from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from app.services.evidence_references import analyze_evidence_references

TEACHER_REVIEW_QUEUE_SCHEMA = "teacher_review_queue.v1"
COURSE_ASSET_READINESS_SCHEMA = "course_asset_readiness.v1"
ERROR_POOL_REVIEW_SCHEMA = "error_pool_review.v1"
ERROR_POOL_REVIEW_DECISIONS = frozenset({"pending", "approved", "rejected"})


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _course_matches(raw: dict[str, Any], course: str) -> bool:
    value = raw.get("course_id", raw.get("course", ""))
    return str(value).strip().upper() == course


def _ocr_metadata_present(raw: dict[str, Any]) -> bool:
    return any(
        key in raw
        for key in (
            "ocr",
            "ocr_metadata",
            "ocr_confidence",
            "ocr_status",
            "ocr_review_required",
            "manual_review_required",
        )
    )


def _ocr_confidence_present(raw: dict[str, Any]) -> bool:
    if raw.get("ocr_confidence") is not None:
        return True
    for key in ("ocr", "ocr_metadata"):
        metadata = raw.get(key)
        if isinstance(metadata, dict) and metadata.get("confidence") is not None:
            return True
    return False


def _build_knowledge_inventory(root: Path, course: str) -> dict[str, Any]:
    """Read manifest quality signals without running parsing or OCR."""
    manifest_path = root / "knowledge_indexes" / "knowledge_base_manifest.jsonl"
    issues_path = root / "knowledge_indexes" / "knowledge_base_quality_issues.json"
    rows: list[dict[str, Any]] = []
    malformed_manifest_rows = 0
    if manifest_path.is_file():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                malformed_manifest_rows += 1
                continue
            if isinstance(raw, dict) and _course_matches(raw, course):
                rows.append(raw)
            elif not isinstance(raw, dict):
                malformed_manifest_rows += 1

    quality_issues_file_present = issues_path.is_file()
    quality_issues_file_parseable = False
    issues: list[dict[str, Any]] = []
    if quality_issues_file_present:
        try:
            raw_issues = json.loads(issues_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw_issues = None
        if isinstance(raw_issues, dict) and isinstance(raw_issues.get("issues"), list):
            quality_issues_file_parseable = True
            issues = [
                item
                for item in raw_issues["issues"]
                if isinstance(item, dict) and _course_matches(item, course)
            ]

    parse_status_counts = dict(
        Counter(str(row.get("parse_status", "unknown")) for row in rows)
    )
    quality_status_counts = dict(
        Counter(str(row.get("quality_status", "unknown")) for row in rows)
    )
    issue_type_counts = dict(
        Counter(str(item.get("issue_type", "unknown")) for item in issues)
    )
    rows_with_ocr_metadata = sum(_ocr_metadata_present(row) for row in rows)
    rows_with_ocr_confidence = sum(_ocr_confidence_present(row) for row in rows)
    rows_with_manual_review_flag = sum(
        row.get("manual_review_required") is True for row in rows
    )
    document_count = len(rows)
    ocr_metadata_coverage_ratio = (
        round(rows_with_ocr_metadata / document_count, 4) if document_count else None
    )
    if not manifest_path.is_file() or not document_count:
        ocr_status = "unavailable"
        status = "unavailable"
    elif not rows_with_ocr_metadata:
        ocr_status = "unavailable"
        status = "partial"
    elif rows_with_ocr_metadata < document_count:
        ocr_status = "partial"
        status = "partial"
    else:
        ocr_status = "available"
        status = "available"
    if malformed_manifest_rows or issues or not quality_issues_file_parseable:
        status = "partial" if document_count else "unavailable"
    return {
        "status": status,
        "manifest_present": manifest_path.is_file(),
        "manifest_path": "knowledge_indexes/knowledge_base_manifest.jsonl",
        "document_count": document_count,
        "malformed_manifest_rows": malformed_manifest_rows,
        "quality_issues_file_present": quality_issues_file_present,
        "quality_issues_file_parseable": quality_issues_file_parseable,
        "quality_issue_count": len(issues),
        "quality_issue_type_counts": issue_type_counts,
        "quality_status_counts": quality_status_counts,
        "parse_status_counts": parse_status_counts,
        "rows_with_ocr_metadata": rows_with_ocr_metadata,
        "rows_with_ocr_confidence": rows_with_ocr_confidence,
        "rows_with_manual_review_flag": rows_with_manual_review_flag,
        "ocr_metadata_coverage_ratio": ocr_metadata_coverage_ratio,
        "ocr_status": ocr_status,
    }


def _runtime_uncovered_signatures(root: Path, course: str) -> set[str]:
    referenced, usable = _runtime_error_signature_sets(root, course)
    return referenced - usable


def _runtime_error_signature_sets(root: Path, course: str) -> tuple[set[str], set[str]]:
    skill_path = root / "config" / "skills" / f"{course}.yaml"
    error_path = root / "config" / "error_pool" / f"{course}.yaml"
    skills = _load_yaml(skill_path).get("skills", []) if skill_path.is_file() else []
    errors = _load_yaml(error_path).get("errors", []) if error_path.is_file() else []
    referenced = {
        str(signature)
        for skill in skills
        if isinstance(skill, dict)
        for signature in skill.get("common_error_signatures", [])
    }
    usable = {
        str(item.get("error_signature"))
        for item in errors
        if isinstance(item, dict)
        and item.get("enabled") is True
        and item.get("teacher_reviewed") is True
        and item.get("match_mode") == "exact_rule"
    }
    return referenced, usable


def _error_pool_review_paths(root: Path, course: str) -> tuple[Path, ...]:
    return (
        root / "config" / "skills" / f"{course}.yaml",
        root / "config" / "error_pool" / f"{course}.yaml",
        root / "config" / "error_pool" / "proposals" / f"{course}.yaml",
        root / "config" / "error_pool" / "reviews" / f"{course}.yaml",
        root / "config" / "error_pool" / "releases" / f"{course}.yaml",
        root / "config" / "course_assets" / f"{course}.yaml",
    )


def _deterministic_error_evidence(
    root: Path, course: str, signature: str
) -> dict[str, Any]:
    """Read audit-declared validator evidence for one candidate signature."""

    unavailable: dict[str, Any] = {
        "status": "not_declared",
        "conflict_types": [],
        "scope": "not_declared",
        "validator_id": None,
        "validator_path": None,
        "note": "No deterministic evidence mapping is declared.",
    }
    manifest_path = root / "config" / "course_assets" / f"{course}.yaml"
    if not manifest_path.is_file():
        return unavailable
    raw = _load_yaml(manifest_path)
    evidence = raw.get("error_signature_evidence", {})
    if not isinstance(evidence, dict):
        return unavailable
    mappings = evidence.get("mappings", {})
    if not isinstance(mappings, dict):
        return {
            **unavailable,
            "status": "review",
            "note": "Deterministic evidence mappings are invalid.",
        }
    mapping = mappings.get(signature)
    if not isinstance(mapping, dict):
        return unavailable
    conflict_types = mapping.get("conflict_types", [])
    if not isinstance(conflict_types, list) or not conflict_types:
        return {
            **unavailable,
            "status": "review",
            "note": "The evidence mapping has no conflict types.",
        }
    return {
        "status": "evidence_ready",
        "conflict_types": sorted({str(value) for value in conflict_types}),
        "scope": str(
            mapping.get("evidence_scope")
            or evidence.get("evidence_scope")
            or "finite_deterministic"
        ),
        "validator_id": (
            str(mapping.get("validator_id") or evidence.get("validator_id"))
            if mapping.get("validator_id") or evidence.get("validator_id")
            else None
        ),
        "validator_path": (
            str(mapping.get("validator_path") or evidence.get("validator_path"))
            if mapping.get("validator_path") or evidence.get("validator_path")
            else None
        ),
        "note": str(
            mapping.get("evidence_note")
            or evidence.get("evidence_note")
            or (
                "Finite deterministic evidence; applicability depends on structured "
                "input."
            )
        ),
    }


def error_pool_review_source_fingerprint(root: Path, course: str) -> str:
    """Fingerprint the CT/AE review inputs for optimistic concurrency checks."""

    normalized_course = course.strip().upper()
    digest = hashlib.sha256()
    for path in _error_pool_review_paths(root, normalized_course):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def attach_ocr_decision_readiness(
    result: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    """Attach OCR decision evidence without executing or approving OCR."""

    enriched = dict(result)
    enriched["ocr_decision_evidence"] = dict(evidence)
    candidate_count = int(evidence.get("candidate_count", 0) or 0)
    status = str(evidence.get("status", "invalid_or_stale"))
    if candidate_count <= 0 or status == "complete_with_evidence":
        return enriched

    blocker_by_status = {
        "decision_file_missing": (
            "knowledge_ocr_decision_file_missing",
            "OCR candidates exist but no teacher decision file has been recorded.",
            "create_pending_ocr_decision_file",
        ),
        "pending": (
            "knowledge_ocr_decisions_pending",
            "OCR candidates still have pending teacher decisions.",
            "complete_pending_ocr_teacher_decisions",
        ),
        "complete_without_evidence": (
            "knowledge_ocr_decisions_missing_evidence",
            "OCR decisions are complete but one or more rows lack evidence references.",
            "add_evidence_refs_to_ocr_decisions",
        ),
        "invalid_or_stale": (
            "knowledge_ocr_decisions_invalid_or_stale",
            "OCR decision evidence is invalid or no longer matches the source queue.",
            "regenerate_queue_and_reconcile_stale_decisions",
        ),
    }
    code, message, default_action = blocker_by_status.get(
        status,
        (
            "knowledge_ocr_decision_status_unknown",
            "OCR decision evidence status is not recognized.",
            "inspect_ocr_decision_evidence_status",
        ),
    )
    blockers = [
        item
        for item in result.get("blockers", [])
        if isinstance(item, dict) and item.get("code") != code
    ]
    blockers.append({"code": code, "severity": "high", "message": message})
    next_actions = [
        str(item) for item in result.get("next_actions", []) if str(item).strip()
    ]
    next_actions.append(str(evidence.get("next_action") or default_action))
    enriched["status"] = (
        "evidence_pending"
        if enriched.get("status") == "ready"
        else enriched.get("status", "evidence_pending")
    )
    enriched["blockers"] = blockers
    enriched["next_actions"] = sorted(set(next_actions))
    return enriched


def attach_evaluation_provenance_readiness(
    result: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    """Expose offline evaluation provenance without claiming learning outcomes."""

    enriched = dict(result)
    enriched["evaluation_provenance"] = dict(evidence)
    status = str(evidence.get("status", "report_invalid"))
    blocker_by_status = {
        "report_missing": (
            "evaluation_provenance_report_missing",
            (
                "No validated offline evaluation report is available for this "
                "readiness snapshot."
            ),
            "restore_or_generate_offline_evaluation_report",
            "medium",
        ),
        "report_invalid": (
            "evaluation_provenance_report_invalid",
            "The latest offline evaluation report cannot be validated.",
            "repair_or_replace_offline_evaluation_report",
            "high",
        ),
        "course_not_covered": (
            "evaluation_provenance_course_not_covered",
            "The latest offline evaluation report does not cover this course.",
            "run_offline_evaluation_for_course",
            "medium",
        ),
    }
    if status in blocker_by_status:
        code, message, action, severity = blocker_by_status[status]
        blockers = [
            item
            for item in result.get("blockers", [])
            if isinstance(item, dict) and item.get("code") != code
        ]
        blockers.append({"code": code, "severity": severity, "message": message})
        next_actions = [
            str(item) for item in result.get("next_actions", []) if str(item).strip()
        ]
        next_actions.append(action)
        enriched["status"] = (
            "evidence_pending"
            if enriched.get("status") == "ready"
            else enriched.get("status", "evidence_pending")
        )
        enriched["blockers"] = blockers
        enriched["next_actions"] = sorted(set(next_actions))

    if status == "available" and evidence.get("run_metadata_present") is False:
        code = "evaluation_provenance_metadata_incomplete"
        blockers = [
            item
            for item in enriched.get("blockers", [])
            if isinstance(item, dict) and item.get("code") != code
        ]
        blockers.append(
            {
                "code": code,
                "severity": "medium",
                "message": (
                    "The report is valid, but reproducibility metadata is absent; "
                    "evaluation provenance is partial."
                ),
            }
        )
        next_actions = [
            str(item) for item in enriched.get("next_actions", []) if str(item).strip()
        ]
        next_actions.append("regenerate_evaluation_report_with_run_metadata")
        enriched["status"] = (
            "evidence_pending"
            if enriched.get("status") == "ready"
            else enriched.get("status", "evidence_pending")
        )
        enriched["blockers"] = blockers
        enriched["next_actions"] = sorted(set(next_actions))

    consistency = evidence.get("consistency")
    consistency_status = (
        str(consistency.get("status"))
        if isinstance(consistency, dict)
        else "not_checkable"
    )
    if status == "available" and consistency_status == "inconsistent":
        code = "evaluation_provenance_inconsistent"
        blockers = [
            item
            for item in enriched.get("blockers", [])
            if isinstance(item, dict) and item.get("code") != code
        ]
        blockers.append(
            {
                "code": code,
                "severity": "high",
                "message": (
                    "Evaluation report summary, course statistics, or run metadata "
                    "are internally inconsistent."
                ),
            }
        )
        next_actions = [
            str(item) for item in enriched.get("next_actions", []) if str(item).strip()
        ]
        next_actions.append("inspect_and_regenerate_inconsistent_evaluation_report")
        enriched["status"] = (
            "evidence_pending"
            if enriched.get("status") == "ready"
            else enriched.get("status", "evidence_pending")
        )
        enriched["blockers"] = blockers
        enriched["next_actions"] = sorted(set(next_actions))
    elif (
        status == "available"
        and consistency_status == "partial"
        and evidence.get("run_metadata_present") is True
    ):
        code = "evaluation_provenance_scope_incomplete"
        blockers = [
            item
            for item in enriched.get("blockers", [])
            if isinstance(item, dict) and item.get("code") != code
        ]
        blockers.append(
            {
                "code": code,
                "severity": "medium",
                "message": (
                    "Evaluation metadata is present but the case catalog, content "
                    "fingerprint, source-file, or attachment manifest association "
                    "is incomplete."
                ),
            }
        )
        next_actions = [
            str(item) for item in enriched.get("next_actions", []) if str(item).strip()
        ]
        if (
            isinstance(consistency, dict)
            and consistency.get("case_attachment_manifest_present") is False
        ):
            next_actions.append("regenerate_evaluation_report_with_attachment_manifest")
        else:
            next_actions.append("regenerate_evaluation_report_with_catalog_metadata")
        enriched["status"] = (
            "evidence_pending"
            if enriched.get("status") == "ready"
            else enriched.get("status", "evidence_pending")
        )
        enriched["blockers"] = blockers
        enriched["next_actions"] = sorted(set(next_actions))
    return enriched


def _sorted_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if item is not None})


def _proposal_schema_errors(
    raw: dict[str, Any],
    course: str,
    uncovered_signatures: set[str],
    *,
    allowed_covered_signatures: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    allowed_covered = allowed_covered_signatures or set()
    if raw.get("schema_version") != "error_pool_proposal.v1":
        errors.append("schema_version_invalid")
    if str(raw.get("course_id", "")).upper() != course:
        errors.append("course_id_mismatch")
    if raw.get("runtime_loaded") is not False:
        errors.append("runtime_loaded_must_be_false")
    if raw.get("review_status") != "pending_teacher_review":
        errors.append("review_status_must_be_pending_teacher_review")

    proposals = raw.get("proposals", [])
    if not isinstance(proposals, list):
        return [*errors, "proposals_must_be_list"]
    signatures: list[str] = []
    proposal_ids: list[str] = []
    for index, item in enumerate(proposals):
        if not isinstance(item, dict):
            errors.append(f"proposal_{index}_must_be_object")
            continue
        signature = str(item.get("error_signature", ""))
        if not signature:
            errors.append(f"proposal_{index}_missing_error_signature")
            continue
        signatures.append(signature)
        proposal_id = str(item.get("proposal_id", ""))
        if not proposal_id:
            errors.append(f"{signature}:missing_proposal_id")
        else:
            proposal_ids.append(proposal_id)
        if item.get("enabled") is not False:
            errors.append(f"{signature}:enabled_must_be_false")
        review = item.get("teacher_review")
        if not isinstance(review, dict) or review.get("status") != "pending":
            errors.append(f"{signature}:teacher_review_must_be_pending")
        if signature not in uncovered_signatures and signature not in allowed_covered:
            errors.append(f"{signature}:not_currently_uncovered")
    if len(signatures) != len(set(signatures)):
        errors.append("duplicate_error_signature")
    if len(proposal_ids) != len(set(proposal_ids)):
        errors.append("duplicate_proposal_id")
    return sorted(errors)


def build_teacher_review_queue(root: Path, course: str) -> dict[str, Any]:
    """Return an evidence-gated, read-only queue for one course."""
    normalized_course = course.strip().upper()
    uncovered = _runtime_uncovered_signatures(root, normalized_course)
    source_fingerprint = error_pool_review_source_fingerprint(root, normalized_course)
    proposal_path = (
        root / "config" / "error_pool" / "proposals" / f"{normalized_course}.yaml"
    )
    review_path = (
        root / "config" / "error_pool" / "reviews" / f"{normalized_course}.yaml"
    )
    result: dict[str, Any] = {
        "schema_version": TEACHER_REVIEW_QUEUE_SCHEMA,
        "course_id": normalized_course,
        "status": "missing_proposals",
        "source_fingerprint": source_fingerprint,
        "runtime_loaded": False,
        "item_count": 0,
        "items": [],
        "unresolved_signatures_without_proposal": sorted(uncovered),
        "all_items_require_teacher_evidence": True,
        "proposal_schema_errors": [],
    }
    if not proposal_path.is_file():
        return result

    proposal_raw = _load_yaml(proposal_path)
    if not isinstance(proposal_raw, dict):
        return result | {
            "status": "invalid_proposals",
            "proposal_schema_errors": ["proposal_document_must_be_object"],
        }
    proposals = proposal_raw.get("proposals", [])
    if not isinstance(proposals, list):
        proposal_errors = _proposal_schema_errors(
            proposal_raw,
            normalized_course,
            uncovered,
        )
        return result | {
            "status": "schema_error",
            "proposal_schema_errors": proposal_errors,
        }

    decisions: dict[str, dict[str, Any]] = {}
    review_status = "pending_teacher_review"
    if review_path.is_file():
        review_raw = _load_yaml(review_path)
        if isinstance(review_raw, dict):
            review_status = str(
                review_raw.get("review_status", "pending_teacher_review")
            )
            raw_decisions = review_raw.get("decisions", [])
            if isinstance(raw_decisions, list):
                decisions = {
                    str(item.get("proposal_id")): item
                    for item in raw_decisions
                    if isinstance(item, dict) and item.get("proposal_id")
                }

    release_path = (
        root / "config" / "error_pool" / "releases" / f"{normalized_course}.yaml"
    )
    release_raw = _load_yaml(release_path) if release_path.is_file() else {}
    if not isinstance(release_raw, dict):
        release_raw = {}
    active_release_ids = {
        str(item.get("proposal_id"))
        for item in release_raw.get("promoted_proposals", [])
        if isinstance(item, dict)
        and item.get("proposal_id")
        and release_raw.get("schema_version") == "error_pool_release.v1"
        and release_raw.get("status") == "active"
    }
    promoted_signatures = {
        str(item.get("error_signature"))
        for item in proposals
        if isinstance(item, dict)
        and str(item.get("proposal_id", "")) in active_release_ids
    }
    proposal_errors = _proposal_schema_errors(
        proposal_raw,
        normalized_course,
        uncovered,
        allowed_covered_signatures=promoted_signatures,
    )

    items: list[dict[str, Any]] = []
    proposal_signatures: set[str] = set()
    for item in proposals:
        if not isinstance(item, dict):
            continue
        proposal_id = str(item.get("proposal_id", ""))
        signature = str(item.get("error_signature", ""))
        if not proposal_id or not signature:
            continue
        if proposal_id in active_release_ids and signature not in uncovered:
            continue
        proposal_signatures.add(signature)
        skill_ids = _sorted_strings(item.get("skill_ids", []))
        problem_types = _sorted_strings(item.get("problem_types", []))
        decision = decisions.get(proposal_id, {})
        evidence_refs = decision.get("evidence_refs", [])
        if not isinstance(evidence_refs, list):
            evidence_refs = []
        evidence_quality = analyze_evidence_references(evidence_refs)
        priority = "P1" if len(skill_ids) > 1 else "P2"
        deterministic_evidence = _deterministic_error_evidence(
            root, normalized_course, signature
        )
        items.append(
            {
                "proposal_id": proposal_id,
                "error_signature": signature,
                "priority": priority,
                "priority_reason": (
                    "referenced_by_multiple_skills"
                    if priority == "P1"
                    else "referenced_by_one_skill"
                ),
                "skill_ids": skill_ids,
                "problem_types": problem_types,
                "covered_by_runtime": signature not in uncovered,
                "review_decision": str(decision.get("decision", "not_recorded")),
                "review_evidence_refs": [str(ref) for ref in evidence_refs],
                "review_notes": str(
                    decision.get("notes", decision.get("note", ""))
                ).strip(),
                "reviewer": (
                    str(decision.get("reviewer")).strip()
                    if decision.get("reviewer")
                    else None
                ),
                "reviewed_at": (
                    str(decision.get("reviewed_at")).strip()
                    if decision.get("reviewed_at")
                    else None
                ),
                "review_evidence_quality": evidence_quality["status"],
                "review_evidence_reference_kinds": evidence_quality["reference_kinds"],
                "evidence_required": True,
                "runtime_eligible": False,
                "deterministic_evidence_status": deterministic_evidence["status"],
                "deterministic_conflict_types": deterministic_evidence[
                    "conflict_types"
                ],
                "deterministic_evidence_scope": deterministic_evidence["scope"],
                "deterministic_validator_id": deterministic_evidence["validator_id"],
                "deterministic_validator_path": deterministic_evidence[
                    "validator_path"
                ],
                "deterministic_evidence_note": deterministic_evidence["note"],
                "next_action": "teacher_review_with_evidence",
            }
        )

    items.sort(key=lambda item: (item["priority"], item["proposal_id"]))
    result.update(
        {
            "status": "schema_error" if proposal_errors else review_status,
            "item_count": len(items),
            "items": items,
            "unresolved_signatures_without_proposal": sorted(
                uncovered - proposal_signatures
            ),
            "proposal_schema_errors": proposal_errors,
        }
    )
    return result


def summarize_teacher_review_evidence(queue: dict[str, Any]) -> dict[str, Any]:
    """Summarize evidence quality for readiness without changing queue state."""
    items = [
        item for item in queue.get("items", []) if isinstance(item, dict)
    ]
    counts = Counter(
        str(item.get("review_evidence_quality", "missing")) for item in items
    )
    untraceable_ids = sorted(
        str(item.get("proposal_id"))
        for item in items
        if item.get("review_evidence_quality") == "untraceable"
    )
    deterministic_status_counts = Counter(
        str(item.get("deterministic_evidence_status", "not_declared"))
        for item in items
    )
    deterministic_not_ready_ids = sorted(
        str(item.get("proposal_id"))
        for item in items
        if item.get("deterministic_evidence_status") != "evidence_ready"
    )
    deterministic_scope_counts = Counter(
        str(item.get("deterministic_evidence_scope", "not_declared"))
        for item in items
    )
    deterministic_validator_ids = sorted(
        {
            str(item.get("deterministic_validator_id"))
            for item in items
            if item.get("deterministic_validator_id")
        }
    )
    deterministic_evidence_status = (
        "unavailable"
        if not items
        else "ready"
        if not deterministic_not_ready_ids
        else "partial"
    )
    status = (
        "unavailable"
        if not items
        else "untraceable"
        if untraceable_ids
        else "missing"
        if counts.get("missing", 0)
        else "traceable"
    )
    return {
        "status": status,
        "item_count": len(items),
        "traceable_count": counts.get("traceable", 0),
        "missing_count": counts.get("missing", 0),
        "untraceable_count": counts.get("untraceable", 0),
        "untraceable_proposal_ids": untraceable_ids,
        "deterministic_evidence_status": deterministic_evidence_status,
        "deterministic_evidence_ready_count": deterministic_status_counts.get(
            "evidence_ready", 0
        ),
        "deterministic_evidence_not_ready_count": len(deterministic_not_ready_ids),
        "deterministic_evidence_not_ready_proposal_ids": deterministic_not_ready_ids,
        "deterministic_evidence_scope_counts": dict(
            sorted(deterministic_scope_counts.items())
        ),
        "deterministic_validator_ids": deterministic_validator_ids,
    }


def build_error_pool_review_document(
    queue: dict[str, Any],
    course: str,
    decisions: list[dict[str, Any]],
    *,
    source_fingerprint: str,
    reviewer: str,
    reviewed_at: str,
) -> dict[str, Any]:
    """Build a server-owned CT/AE error-template review document."""

    normalized_reviewer = reviewer.strip()
    if not normalized_reviewer:
        raise ValueError("reviewer_required")
    normalized_course = course.strip().upper()
    if queue.get("course_id") != normalized_course:
        raise ValueError("course_id_mismatch")
    current_ids = {
        str(item.get("proposal_id"))
        for item in queue.get("items", [])
        if isinstance(item, dict) and item.get("proposal_id")
    }
    normalized_rows: list[dict[str, Any]] = []
    for raw in decisions:
        proposal_id = str(raw.get("proposal_id", "")).strip()
        decision = str(raw.get("decision", "pending"))
        evidence_refs = [
            str(reference).strip()
            for reference in raw.get("evidence_refs", [])
            if str(reference).strip()
        ]
        if proposal_id not in current_ids:
            raise ValueError(f"unknown_proposal_id:{proposal_id}")
        if decision not in ERROR_POOL_REVIEW_DECISIONS:
            raise ValueError(f"invalid_decision:{proposal_id}")
        if decision != "pending" and not evidence_refs:
            raise ValueError(f"evidence_refs_required:{proposal_id}")
        evidence_quality = analyze_evidence_references(evidence_refs)
        if decision != "pending" and evidence_quality["status"] != "traceable":
            raise ValueError(f"evidence_refs_untraceable:{proposal_id}")
        normalized_rows.append(
            {
                "proposal_id": proposal_id,
                "decision": decision,
                "reviewer": normalized_reviewer if decision != "pending" else None,
                "reviewed_at": reviewed_at if decision != "pending" else None,
                "evidence_refs": list(dict.fromkeys(evidence_refs)),
                "notes": str(raw.get("notes", "")).strip(),
            }
        )
    decided_count = sum(
        str(item.get("decision")) != "pending" for item in normalized_rows
    )
    item_count = len(current_ids)
    review_status = (
        "teacher_review_complete"
        if item_count and decided_count == item_count
        else "teacher_review_in_progress"
        if decided_count
        else "pending_teacher_review"
    )
    return {
        "schema_version": ERROR_POOL_REVIEW_SCHEMA,
        "course_id": normalized_course,
        "source_fingerprint": source_fingerprint,
        "runtime_loaded": False,
        "review_status": review_status,
        "reviewer": normalized_reviewer if decided_count else None,
        "reviewed_at": reviewed_at if decided_count else None,
        "decisions": normalized_rows,
    }


def validate_error_pool_review_document(
    queue: dict[str, Any],
    document: dict[str, Any],
    *,
    check_source_fingerprint: bool = True,
) -> dict[str, Any]:
    """Validate review decisions against the exact CT/AE queue snapshot."""

    errors: list[str] = []
    if queue.get("schema_version") != TEACHER_REVIEW_QUEUE_SCHEMA:
        errors.append("queue_schema_version_invalid")
    if document.get("schema_version") != ERROR_POOL_REVIEW_SCHEMA:
        errors.append("schema_version_invalid")
    if document.get("runtime_loaded") is not False:
        errors.append("runtime_loaded_must_be_false")
    course_id = str(document.get("course_id", "")).strip().upper()
    if course_id != str(queue.get("course_id", "")).strip().upper():
        errors.append("course_id_mismatch")
    if check_source_fingerprint and str(document.get("source_fingerprint", "")) != str(
        queue.get("source_fingerprint", "")
    ):
        errors.append("stale_source_fingerprint")
    queue_ids = {
        str(item.get("proposal_id"))
        for item in queue.get("items", [])
        if isinstance(item, dict) and item.get("proposal_id")
    }
    if queue.get("proposal_schema_errors"):
        errors.append("proposal_schema_invalid")
    raw_decisions = document.get("decisions", [])
    if not isinstance(raw_decisions, list):
        errors.append("decisions_must_be_list")
        raw_decisions = []
    seen: set[str] = set()
    valid_rows: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_decisions):
        if not isinstance(raw, dict):
            errors.append(f"decision_{index}_must_be_object")
            continue
        proposal_id = str(raw.get("proposal_id", "")).strip()
        if not proposal_id:
            errors.append(f"decision_{index}_proposal_id_required")
            continue
        if proposal_id in seen:
            errors.append(f"duplicate_proposal_id:{proposal_id}")
            continue
        seen.add(proposal_id)
        if proposal_id not in queue_ids:
            errors.append(f"unknown_proposal_id:{proposal_id}")
            continue
        decision = str(raw.get("decision", ""))
        if decision not in ERROR_POOL_REVIEW_DECISIONS:
            errors.append(f"invalid_decision:{proposal_id}")
        evidence_refs = raw.get("evidence_refs", [])
        if not isinstance(evidence_refs, list):
            errors.append(f"evidence_refs_must_be_list:{proposal_id}")
            evidence_refs = []
        if decision != "pending" and not [
            ref for ref in evidence_refs if str(ref).strip()
        ]:
            errors.append(f"evidence_refs_required:{proposal_id}")
        elif decision != "pending":
            evidence_quality = analyze_evidence_references(evidence_refs)
            if evidence_quality["status"] != "traceable":
                errors.append(f"evidence_refs_untraceable:{proposal_id}")
        if decision != "pending" and not str(raw.get("reviewer", "")).strip():
            errors.append(f"reviewer_required:{proposal_id}")
        if decision != "pending" and not str(raw.get("reviewed_at", "")).strip():
            errors.append(f"reviewed_at_required:{proposal_id}")
        valid_rows.append(raw)

    missing = sorted(queue_ids - seen)
    errors.extend(f"missing_proposal_id:{proposal_id}" for proposal_id in missing)
    decided_count = sum(
        str(item.get("decision", "pending")) != "pending" for item in valid_rows
    )
    expected_status = (
        "teacher_review_complete"
        if queue_ids and decided_count == len(queue_ids) and not missing
        else "teacher_review_in_progress"
        if decided_count
        else "pending_teacher_review"
    )
    if document.get("review_status") != expected_status:
        errors.append("review_status_mismatch")
    return {
        "schema_version": ERROR_POOL_REVIEW_SCHEMA,
        "valid": not errors,
        "course_id": course_id,
        "decision_count": len(valid_rows),
        "decided_count": decided_count,
        "pending_count": max(len(queue_ids) - decided_count, 0),
        "review_complete": not missing and decided_count == len(queue_ids),
        "errors": errors,
        "runtime_loaded": False,
    }


def write_error_pool_review_document(path: Path, document: dict[str, Any]) -> None:
    """Persist a validated CT/AE review document with atomic replacement."""

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


def _source_statuses(root: Path, sources: Any) -> dict[str, str]:
    if not isinstance(sources, dict):
        return {}
    return {
        str(source_id): (
            "not_declared"
            if source_path is None
            else "available"
            if isinstance(source_path, str)
            and not Path(source_path).is_absolute()
            and (root / source_path).exists()
            else "missing"
        )
        for source_id, source_path in sorted(sources.items())
    }


def _evidence_check(
    root: Path,
    *,
    key: str,
    declared_status: str,
    observed_status: str,
    evidence_status: str,
    evidence_paths: list[str],
) -> dict[str, Any]:
    return {
        "key": key,
        "declared_status": declared_status,
        "observed_status": observed_status,
        "evidence_status": evidence_status,
        "evidence_paths": evidence_paths,
        "evidence_present": all((root / path).is_file() for path in evidence_paths),
    }


def _build_evidence_checks(
    root: Path,
    course: str,
    readiness: dict[str, Any],
    contest_boundary: dict[str, Any],
) -> list[dict[str, Any]]:
    referenced, usable = _runtime_error_signature_sets(root, course)
    coverage_status = (
        "implemented" if referenced and referenced.issubset(usable) else "partial"
    )
    checks: list[dict[str, Any]] = []
    definitions = {
        "material_lifecycle": (
            "implemented",
            "present",
            [
                "apps/api/alembic/versions/20260803_0011_course_material_lifecycle.py",
                "apps/api/app/api/v1/knowledge.py",
                "apps/api/tests/test_document_ingestion.py",
            ],
        ),
        "teacher_review_gate": (
            "implemented",
            "present",
            [
                "apps/api/alembic/versions/20260804_0012_course_material_review.py",
                "apps/api/app/api/v1/knowledge.py",
                "apps/api/tests/test_document_ingestion.py",
            ],
        ),
        "user_feedback_metrics": (
            "implemented",
            "present",
            [
                "apps/api/alembic/versions/20260804_0013_task_feedback.py",
                "apps/api/app/api/v1/feedback.py",
                "apps/api/tests/test_feedback_api.py",
            ],
        ),
        "runtime_error_template_coverage": (
            coverage_status,
            "present",
            [
                f"config/error_pool/{course}.yaml",
                "apps/api/app/services/error_pool.py",
                "apps/api/app/services/course_asset_review.py",
            ],
        ),
        "official_rules": (
            "not_verified",
            "boundary_declared",
            [
                "submission/contest_package/package_manifest.yaml",
                "submission/contest_package/01_participation_info.md",
            ],
        ),
        "demonstration_cases": (
            "owner_input_required",
            "boundary_declared",
            [
                "submission/contest_package/package_manifest.yaml",
                "submission/contest_package/03_demo_user_guide.md",
            ],
        ),
        "real_user_outcomes": (
            "authorization_required",
            "boundary_declared",
            [
                "submission/contest_package/package_manifest.yaml",
                "submission/contest_package/08_user_pilot_log.md",
            ],
        ),
    }
    for key, (observed_status, evidence_status, evidence_paths) in definitions.items():
        declared_status = str(readiness.get(key, "not_declared"))
        if key == "official_rules" and contest_boundary["official_rules_verified"]:
            observed_status = "verified"
        if key == "demonstration_cases" and contest_boundary["demo_cases_included"]:
            observed_status = "included"
        if (
            key == "real_user_outcomes"
            and contest_boundary["real_user_outcomes_included"]
        ):
            observed_status = "available"
        checks.append(
            _evidence_check(
                root,
                key=key,
                declared_status=declared_status,
                observed_status=observed_status,
                evidence_status=evidence_status,
                evidence_paths=evidence_paths,
            )
        )
    return checks


def build_course_asset_readiness(root: Path, course: str) -> dict[str, Any]:
    """Summarize evidence readiness without promoting or publishing assets."""
    normalized_course = course.strip().upper()
    manifest_path = root / "config" / "course_assets" / f"{normalized_course}.yaml"
    knowledge_inventory = _build_knowledge_inventory(root, normalized_course)
    result: dict[str, Any] = {
        "schema_version": COURSE_ASSET_READINESS_SCHEMA,
        "course_id": normalized_course,
        "status": "unavailable",
        "runtime_course_pack_status": "unknown",
        "runtime_loaded": False,
        "runtime_source": None,
        "frozen_fallback_reference": None,
        "boundaries": {},
        "readiness_items": [],
        "evidence_checks": [],
        "knowledge_inventory": knowledge_inventory,
        "ocr_decision_evidence": None,
        "evaluation_provenance": None,
        "source_statuses": {},
        "blockers": [],
        "next_actions": [],
        "teacher_review_queue": {
            "item_count": 0,
            "unresolved_signatures_without_proposal": [],
        },
        "contest_boundary": {
            "package_status": "missing_manifest",
            "official_rules_verified": False,
            "demo_cases_included": False,
            "real_user_outcomes_included": False,
            "real_provider_results_included": False,
            "official_score_claims_allowed": False,
        },
    }
    if not manifest_path.is_file():
        result["blockers"] = [
            {
                "code": "course_asset_manifest_missing",
                "severity": "high",
                "message": "Course asset manifest is missing.",
            }
        ]
        result["next_actions"] = ["create_course_asset_manifest_after_audit"]
        return result

    raw = _load_yaml(manifest_path)
    if not isinstance(raw, dict):
        result["blockers"] = [
            {
                "code": "course_asset_manifest_invalid",
                "severity": "high",
                "message": "Course asset manifest must be an object.",
            }
        ]
        return result

    readiness = raw.get("readiness", {})
    readiness_items = (
        [
            {
                "key": str(key),
                "status": str(value),
                "source_ref": f"config/course_assets/{normalized_course}.yaml",
            }
            for key, value in sorted(readiness.items())
        ]
        if isinstance(readiness, dict)
        else []
    )
    queue = build_teacher_review_queue(root, normalized_course)
    teacher_review_evidence = summarize_teacher_review_evidence(queue)
    blockers: list[dict[str, str]] = []
    next_actions: list[str] = []
    if not knowledge_inventory["manifest_present"]:
        blockers.append(
            {
                "code": "knowledge_manifest_missing",
                "severity": "high",
                "message": "Knowledge manifest is missing for the readiness audit.",
            }
        )
        next_actions.append("restore_knowledge_manifest")
    elif knowledge_inventory["malformed_manifest_rows"]:
        blockers.append(
            {
                "code": "knowledge_manifest_malformed_rows",
                "severity": "high",
                "message": (
                    f"{knowledge_inventory['malformed_manifest_rows']} manifest "
                    "rows cannot be parsed."
                ),
            }
        )
        next_actions.append("repair_knowledge_manifest_rows")
    if not knowledge_inventory["quality_issues_file_parseable"]:
        blockers.append(
            {
                "code": "knowledge_quality_issues_unavailable",
                "severity": "medium",
                "message": "Knowledge quality issue inventory is unavailable.",
            }
        )
        next_actions.append("regenerate_knowledge_quality_issue_inventory")
    elif knowledge_inventory["quality_issue_count"]:
        blockers.append(
            {
                "code": "knowledge_quality_issues_present",
                "severity": "medium",
                "message": (
                    f"{knowledge_inventory['quality_issue_count']} knowledge quality "
                    "issues require review."
                ),
            }
        )
        next_actions.append("review_knowledge_quality_issues")
    if knowledge_inventory["ocr_status"] == "unavailable":
        blockers.append(
            {
                "code": "knowledge_ocr_metadata_unavailable",
                "severity": "medium",
                "message": (
                    "No OCR metadata is present in the manifest; determine the "
                    "applicable OCR scope before execution."
                ),
            }
        )
        next_actions.append("define_ocr_scope_and_metadata_contract")
    elif knowledge_inventory["ocr_status"] == "partial":
        blockers.append(
            {
                "code": "knowledge_ocr_metadata_partial",
                "severity": "medium",
                "message": "OCR metadata coverage is incomplete in the manifest.",
            }
        )
        next_actions.append("complete_ocr_metadata_coverage")
    if knowledge_inventory["rows_with_manual_review_flag"]:
        blockers.append(
            {
                "code": "knowledge_manual_review_pending",
                "severity": "medium",
                "message": (
                    f"{knowledge_inventory['rows_with_manual_review_flag']} documents "
                    "are marked for manual review."
                ),
            }
        )
        next_actions.append("complete_knowledge_manual_review")
    if queue["item_count"]:
        blockers.append(
            {
                "code": "teacher_review_required",
                "severity": "high",
                "message": (
                    f"{queue['item_count']} candidate error templates require "
                    "teacher evidence."
                ),
            }
        )
        next_actions.append("complete_teacher_error_template_review")
    if teacher_review_evidence["untraceable_count"]:
        blockers.append(
            {
                "code": "teacher_review_evidence_untraceable",
                "severity": "high",
                "message": (
                    f"{teacher_review_evidence['untraceable_count']} teacher decisions "
                    "contain evidence references that cannot be traced."
                ),
            }
        )
        next_actions.append("replace_untraceable_teacher_evidence_refs")
    if queue["unresolved_signatures_without_proposal"]:
        blockers.append(
            {
                "code": "error_proposal_gap",
                "severity": "high",
                "message": "Some uncovered error signatures have no proposal.",
            }
        )
        next_actions.append("design_reviewed_error_template_proposals")
    for item in readiness_items:
        if item["status"] in {"pending", "owner_designed_pending"}:
            blockers.append(
                {
                    "code": f"readiness_{item['key']}",
                    "severity": "high",
                    "message": f"{item['key']} remains {item['status']}.",
                }
            )
            next_actions.append(f"resolve_{item['key']}")

    package_path = root / "submission" / "contest_package" / "package_manifest.yaml"
    if package_path.is_file():
        package_raw = _load_yaml(package_path)
        if isinstance(package_raw, dict):
            result["contest_boundary"] = {
                "package_status": str(package_raw.get("package_status", "unknown")),
                "official_rules_verified": bool(
                    package_raw.get("official_rules_verified", False)
                ),
                "demo_cases_included": bool(
                    package_raw.get("demo_cases_included", False)
                ),
                "real_user_outcomes_included": bool(
                    package_raw.get("real_user_outcomes_included", False)
                ),
                "real_provider_results_included": bool(
                    package_raw.get("real_provider_results_included", False)
                ),
                "official_score_claims_allowed": bool(
                    package_raw.get("official_score_claims_allowed", False)
                ),
            }

    evidence_checks = _build_evidence_checks(
        root,
        normalized_course,
        readiness if isinstance(readiness, dict) else {},
        result["contest_boundary"],
    )
    for check in evidence_checks:
        if not check["evidence_present"]:
            blockers.append(
                {
                    "code": f"evidence_missing_{check['key']}",
                    "severity": "high",
                    "message": f"Evidence files for {check['key']} are missing.",
                }
            )
            next_actions.append(f"restore_{check['key']}_evidence")
        if (
            check["declared_status"] == "implemented"
            and check["observed_status"] != "implemented"
        ):
            blockers.append(
                {
                    "code": f"readiness_evidence_mismatch_{check['key']}",
                    "severity": "high",
                    "message": (
                        f"{check['key']} is declared implemented but observed "
                        f"as {check['observed_status']}."
                    ),
                }
            )
            next_actions.append(f"reconcile_{check['key']}_readiness")

    status = "evidence_pending" if blockers else "ready"
    result.update(
        {
            "status": status,
            "runtime_course_pack_status": str(
                raw.get("runtime_course_pack_status", "unknown")
            ),
            "runtime_loaded": raw.get("runtime_loaded") is True,
            "runtime_source": raw.get("runtime_source"),
            "frozen_fallback_reference": raw.get("frozen_fallback_reference"),
            "boundaries": raw.get("boundaries", {})
            if isinstance(raw.get("boundaries", {}), dict)
            else {},
            "readiness_items": readiness_items,
            "evidence_checks": evidence_checks,
            "source_statuses": _source_statuses(root, raw.get("sources", {})),
            "blockers": blockers,
            "next_actions": sorted(set(next_actions)),
        "teacher_review_queue": {
                "item_count": queue["item_count"],
                "unresolved_signatures_without_proposal": queue[
                    "unresolved_signatures_without_proposal"
                ],
            },
            "teacher_review_evidence": teacher_review_evidence,
        }
    )
    return result
