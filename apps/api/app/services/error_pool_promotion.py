from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from app.services.course_asset_review import (
    build_teacher_review_queue,
    validate_error_pool_review_document,
)
from app.services.error_pool import ErrorPoolCatalog, ErrorTemplateDefinition
from app.services.evidence_references import analyze_evidence_references

ERROR_POOL_PROMOTION_PLAN_SCHEMA = "error_pool_promotion_plan.v1"
ERROR_POOL_RELEASE_SCHEMA = "error_pool_release.v1"
PROMOTABLE_COURSES = frozenset({"CT", "AE"})


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes() if path.is_file() else b""


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(content)
        temporary.replace(path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _dump_yaml(value: dict[str, Any]) -> bytes:
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).encode("utf-8")


def _paths(root: Path, course: str) -> dict[str, Path]:
    return {
        "runtime": root / "config" / "error_pool" / f"{course}.yaml",
        "proposals": (root / "config" / "error_pool" / "proposals" / f"{course}.yaml"),
        "reviews": root / "config" / "error_pool" / "reviews" / f"{course}.yaml",
        "release": (root / "config" / "error_pool" / "releases" / f"{course}.yaml"),
    }


def _blocker(code: str, message: str, proposal_id: str = "") -> dict[str, str]:
    result = {"code": code, "message": message}
    if proposal_id:
        result["proposal_id"] = proposal_id
    return result


@dataclass(frozen=True)
class _PromotionBuild:
    report: dict[str, Any]
    target_bytes: bytes
    release_document: dict[str, Any]
    current_bytes: bytes


def _active_release(raw: Any, course: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    if (
        raw.get("schema_version") != ERROR_POOL_RELEASE_SCHEMA
        or str(raw.get("course_id", "")).upper() != course
        or raw.get("status") != "active"
    ):
        return None
    return raw


def _build_plan(root: Path, course: str) -> _PromotionBuild:
    normalized_course = course.strip().upper()
    if normalized_course not in PROMOTABLE_COURSES:
        raise ValueError("unsupported promotion course")

    paths = _paths(root, normalized_course)
    queue = build_teacher_review_queue(root, normalized_course)
    current_bytes = _read_bytes(paths["runtime"])
    source_fingerprint = str(queue.get("source_fingerprint", ""))
    runtime_fingerprint = _sha256(current_bytes)
    blockers: list[dict[str, str]] = []
    proposals_raw = (
        _load_yaml(paths["proposals"]) if paths["proposals"].is_file() else {}
    )
    reviews_raw = _load_yaml(paths["reviews"]) if paths["reviews"].is_file() else {}
    release_raw = _load_yaml(paths["release"]) if paths["release"].is_file() else {}
    if not isinstance(proposals_raw, dict):
        proposals_raw = {}
    if not isinstance(reviews_raw, dict):
        reviews_raw = {}
    if not isinstance(release_raw, dict):
        release_raw = {}
    active_release = _active_release(release_raw, normalized_course)

    if queue.get("proposal_schema_errors"):
        blockers.append(
            _blocker(
                "proposal_schema_invalid",
                "Proposal schema errors must be resolved before promotion.",
            )
        )
    if not paths["reviews"].is_file():
        blockers.append(
            _blocker(
                "review_record_missing",
                "A teacher review record is required before promotion.",
            )
        )
    release_proposal_ids = {
        str(item.get("proposal_id"))
        for item in (active_release or {}).get("promoted_proposals", [])
        if isinstance(item, dict) and item.get("proposal_id")
    }
    proposal_ids_in_source = {
        str(item.get("proposal_id"))
        for item in proposals_raw.get("proposals", [])
        if isinstance(item, dict) and item.get("proposal_id")
    }
    release_is_current = bool(
        active_release
        and release_proposal_ids == proposal_ids_in_source
        and active_release.get("runtime_catalog_sha256") == runtime_fingerprint
    )
    review_report = (
        {"valid": True}
        if release_is_current
        else validate_error_pool_review_document(
            queue,
            reviews_raw,
            check_source_fingerprint=False,
        )
    )
    if not review_report.get("valid"):
        blockers.append(
            _blocker(
                "review_record_invalid",
                "Teacher review decisions are incomplete, stale, or invalid.",
            )
        )
    if not paths["runtime"].is_file():
        blockers.append(
            _blocker(
                "runtime_catalog_missing", "Runtime error-pool catalog is missing."
            )
        )
        runtime_raw: dict[str, Any] = {}
        runtime_errors: list[Any] = []
    else:
        try:
            runtime_raw = _load_yaml(paths["runtime"])
            ErrorPoolCatalog.model_validate(runtime_raw)
            runtime_errors = runtime_raw.get("errors", [])
            if not isinstance(runtime_errors, list):
                raise ValueError("errors_must_be_list")
        except (OSError, TypeError, ValueError) as exc:
            blockers.append(
                _blocker(
                    "runtime_catalog_invalid",
                    f"Runtime error-pool catalog is invalid: {type(exc).__name__}.",
                )
            )
            runtime_raw = {}
            runtime_errors = []

    proposals = proposals_raw.get("proposals", [])
    if not isinstance(proposals, list):
        proposals = []
        blockers.append(
            _blocker("proposals_missing", "No promotion proposals are available.")
        )
    decisions = {
        str(item.get("proposal_id")): item
        for item in reviews_raw.get("decisions", [])
        if isinstance(item, dict) and item.get("proposal_id")
    }
    review_evidence_summary: list[dict[str, Any]] = []
    queue_items_by_id = {
        str(item.get("proposal_id")): item
        for item in queue.get("items", [])
        if isinstance(item, dict) and item.get("proposal_id")
    }
    for proposal in proposals_raw.get("proposals", []):
        if not isinstance(proposal, dict):
            continue
        proposal_id = str(proposal.get("proposal_id", ""))
        if not proposal_id:
            continue
        decision = decisions.get(proposal_id, {})
        evidence_refs = decision.get("evidence_refs", [])
        if not isinstance(evidence_refs, list):
            evidence_refs = []
        evidence_ref_count = len(
            {
                str(reference).strip()
                for reference in evidence_refs
                if str(reference).strip()
            }
        )
        evidence_quality = analyze_evidence_references(evidence_refs)
        reviewer_present = bool(
            str(decision.get("reviewer") or reviews_raw.get("reviewer") or "").strip()
        )
        reviewed_at_present = bool(
            str(
                decision.get("reviewed_at") or reviews_raw.get("reviewed_at") or ""
            ).strip()
        )
        decision_value = str(decision.get("decision", "pending"))
        queue_item = queue_items_by_id.get(proposal_id, {})
        ready_for_promotion = bool(
            decision_value == "approved"
            and evidence_quality["status"] == "traceable"
            and reviewer_present
            and reviewed_at_present
        )
        review_evidence_summary.append(
            {
                "proposal_id": proposal_id,
                "decision": decision_value,
                "evidence_ref_count": evidence_ref_count,
                "evidence_present": evidence_ref_count > 0,
                "evidence_quality": evidence_quality["status"],
                "evidence_reference_kinds": evidence_quality["reference_kinds"],
                "reviewer_present": reviewer_present,
                "reviewed_at_present": reviewed_at_present,
                "ready_for_promotion": ready_for_promotion,
                "deterministic_evidence_status": str(
                    queue_item.get("deterministic_evidence_status", "not_declared")
                ),
                "deterministic_evidence_scope": str(
                    queue_item.get("deterministic_evidence_scope", "not_declared")
                ),
                "deterministic_validator_id": queue_item.get(
                    "deterministic_validator_id"
                ),
                "deterministic_validator_path": queue_item.get(
                    "deterministic_validator_path"
                ),
            }
        )
    review_evidence_summary.sort(key=lambda item: item["proposal_id"])
    review_evidence_ready_count = sum(
        item["ready_for_promotion"] for item in review_evidence_summary
    )
    existing_by_signature = {
        str(item.get("error_signature")): item
        for item in runtime_errors
        if isinstance(item, dict) and item.get("error_signature")
    }
    active_release_ids = {
        str(item.get("proposal_id"))
        for item in (active_release or {}).get("promoted_proposals", [])
        if isinstance(item, dict) and item.get("proposal_id")
    }
    candidates: list[dict[str, Any]] = []
    already_promoted: list[str] = []
    all_proposal_ids: set[str] = set()
    for proposal in proposals:
        if not isinstance(proposal, dict):
            blockers.append(
                _blocker("proposal_row_invalid", "Proposal row must be an object.")
            )
            continue
        proposal_id = str(proposal.get("proposal_id", ""))
        signature = str(proposal.get("error_signature", ""))
        if not proposal_id or not signature:
            blockers.append(
                _blocker(
                    "proposal_identity_missing",
                    "Proposal id and signature are required.",
                )
            )
            continue
        all_proposal_ids.add(proposal_id)
        decision = decisions.get(proposal_id, {})
        decision_value = str(decision.get("decision", "pending"))
        evidence_refs = decision.get("evidence_refs", [])
        if not isinstance(evidence_refs, list):
            evidence_refs = []
        if signature in existing_by_signature:
            if proposal_id in active_release_ids:
                already_promoted.append(proposal_id)
            else:
                blockers.append(
                    _blocker(
                        "runtime_signature_conflict",
                        (
                            "Proposal signature already exists in the runtime catalog "
                            "without an active release record."
                        ),
                        proposal_id,
                    )
                )
            continue
        if decision_value != "approved":
            blockers.append(
                _blocker(
                    f"review_{decision_value}",
                    (
                        "Every candidate must have an approved teacher decision "
                        "before course-level promotion."
                    ),
                    proposal_id,
                )
            )
            continue
        if not [str(ref).strip() for ref in evidence_refs if str(ref).strip()]:
            blockers.append(
                _blocker(
                    "approved_review_missing_evidence",
                    "Approved proposals must include evidence references.",
                    proposal_id,
                )
            )
            continue
        evidence_quality = analyze_evidence_references(evidence_refs)
        if evidence_quality["status"] != "traceable":
            blockers.append(
                _blocker(
                    "approved_review_evidence_untraceable",
                    (
                        "Approved proposals must use traceable path, URI, or typed "
                        "evidence references."
                    ),
                    proposal_id,
                )
            )
            continue
        if proposal.get("enabled") is not False:
            blockers.append(
                _blocker(
                    "proposal_runtime_flag_invalid",
                    (
                        "Source proposals must remain disabled and are never loaded "
                        "directly."
                    ),
                    proposal_id,
                )
            )
            continue
        candidate = {
            "error_signature": signature,
            "problem_types": proposal.get("problem_types", []),
            "skill_ids": proposal.get("skill_ids", []),
            "error_type": str(proposal.get("error_type", "")),
            "match_mode": "exact_rule",
            "description": str(proposal.get("description", "")),
            "hint_templates": proposal.get("hint_templates", {}),
            "teacher_reviewed": True,
            "enabled": True,
        }
        try:
            validated = ErrorTemplateDefinition.model_validate(candidate)
        except ValueError:
            blockers.append(
                _blocker(
                    "promoted_template_invalid",
                    "Proposal fields cannot form a valid runtime template.",
                    proposal_id,
                )
            )
            continue
        candidates.append(
            {
                "proposal_id": proposal_id,
                "template": validated.model_dump(mode="json"),
                "evidence_refs": [
                    str(ref).strip() for ref in evidence_refs if str(ref).strip()
                ],
                "reviewer": str(
                    decision.get("reviewer") or reviews_raw.get("reviewer") or ""
                ),
                "reviewed_at": str(
                    decision.get("reviewed_at") or reviews_raw.get("reviewed_at") or ""
                ),
            }
        )

    if all_proposal_ids and set(decisions) != all_proposal_ids:
        blockers.append(
            _blocker(
                "review_record_must_cover_all_proposals",
                (
                    "The review record must include exactly one decision for every "
                    "proposal."
                ),
            )
        )
    if proposals and len(candidates) + len(already_promoted) != len(proposals):
        blockers.append(
            _blocker(
                "course_review_incomplete",
                (
                    "Not all CT/AE proposals are approved for an atomic course-level "
                    "promotion."
                ),
            )
        )

    target_errors = [item for item in runtime_errors if isinstance(item, dict)] + [
        item["template"]
        for item in sorted(candidates, key=lambda value: value["proposal_id"])
    ]
    target_catalog = {
        "version": str(runtime_raw.get("version", "1.0")),
        "course_id": normalized_course,
        "errors": target_errors,
    }
    target_bytes = _dump_yaml(target_catalog)
    target_fingerprint = _sha256(target_bytes)
    status = "blocked" if blockers else "ready" if candidates else "already_current"
    report: dict[str, Any] = {
        "schema_version": ERROR_POOL_PROMOTION_PLAN_SCHEMA,
        "mode": "dry_run",
        "course_id": normalized_course,
        "status": status,
        "ready": status == "ready",
        "source_fingerprint": source_fingerprint,
        "runtime_catalog_sha256_before": runtime_fingerprint,
        "runtime_catalog_sha256_after": target_fingerprint,
        "target_path": _relative_path(root, paths["runtime"]),
        "release_path": _relative_path(root, paths["release"]),
        "candidate_count": len(candidates),
        "already_promoted_count": len(already_promoted),
        "promoted_proposal_ids": [item["proposal_id"] for item in candidates],
        "already_promoted_proposal_ids": sorted(already_promoted),
        "review_evidence_summary": review_evidence_summary,
        "review_evidence_ready_count": review_evidence_ready_count,
        "review_evidence_not_ready_proposal_ids": [
            item["proposal_id"]
            for item in review_evidence_summary
            if not item["ready_for_promotion"]
        ],
        "blockers": blockers,
        "runtime_loaded": False,
    }
    release_document = {
        "schema_version": ERROR_POOL_RELEASE_SCHEMA,
        "course_id": normalized_course,
        "status": "active",
        "runtime_loaded": False,
        "runtime_catalog_path": _relative_path(root, paths["runtime"]),
        "runtime_catalog_sha256": target_fingerprint,
        "source_fingerprint": source_fingerprint,
        "promoted_at": datetime.now(UTC).isoformat(),
        "promoted_proposals": candidates,
    }
    return _PromotionBuild(
        report=report,
        target_bytes=target_bytes,
        release_document=release_document,
        current_bytes=current_bytes,
    )


def build_error_pool_promotion_plan(root: Path, course: str) -> dict[str, Any]:
    """Build a read-only promotion plan; this function never writes files."""

    return dict(_build_plan(root, course).report)


def execute_error_pool_promotion(
    root: Path,
    course: str,
    *,
    expected_source_fingerprint: str = "",
) -> dict[str, Any]:
    """Apply a ready plan with an explicit caller action and preserve a backup."""

    build = _build_plan(root, course)
    report = dict(build.report)
    report["mode"] = "execute"
    if (
        expected_source_fingerprint
        and expected_source_fingerprint != report["source_fingerprint"]
    ):
        report["status"] = "blocked"
        report["ready"] = False
        report["blockers"] = [
            *report["blockers"],
            _blocker(
                "stale_source_fingerprint",
                (
                    "Promotion inputs changed; regenerate the dry-run plan before "
                    "execution."
                ),
            ),
        ]
        return report
    if report["status"] != "ready":
        return report

    paths = _paths(root, str(report["course_id"]))
    backup_dir = (
        root
        / ".local_outputs"
        / "error_pool_promotion_backups"
        / str(report["course_id"])
    )
    backup_path = backup_dir / (
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-"
        f"{report['runtime_catalog_sha256_before'][:12]}.yaml"
    )
    _atomic_write_bytes(backup_path, build.current_bytes)
    try:
        _atomic_write_bytes(paths["runtime"], build.target_bytes)
        _atomic_write_bytes(paths["release"], _dump_yaml(build.release_document))
    except OSError:
        _atomic_write_bytes(paths["runtime"], build.current_bytes)
        raise
    report["status"] = "applied"
    report["ready"] = True
    report["backup_path"] = _relative_path(root, backup_path)
    report["runtime_loaded"] = False
    return report


def rollback_error_pool_promotion(
    root: Path,
    course: str,
    backup_path: Path,
    *,
    expected_current_fingerprint: str = "",
) -> dict[str, Any]:
    """Restore a promotion backup only from the controlled local backup root."""

    normalized_course = course.strip().upper()
    if normalized_course not in PROMOTABLE_COURSES:
        raise ValueError("unsupported promotion course")
    paths = _paths(root, normalized_course)
    allowed_root = (
        root / ".local_outputs" / "error_pool_promotion_backups" / normalized_course
    ).resolve()
    resolved_backup = backup_path.resolve()
    try:
        resolved_backup.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError("backup_path_outside_controlled_root") from exc
    backup_bytes = resolved_backup.read_bytes()
    current_bytes = _read_bytes(paths["runtime"])
    current_fingerprint = _sha256(current_bytes)
    if (
        expected_current_fingerprint
        and expected_current_fingerprint != current_fingerprint
    ):
        raise ValueError("runtime_catalog_changed_since_promotion")
    ErrorPoolCatalog.model_validate(yaml.safe_load(backup_bytes) or {})
    _atomic_write_bytes(paths["runtime"], backup_bytes)
    release_raw = _load_yaml(paths["release"]) if paths["release"].is_file() else {}
    if isinstance(release_raw, dict) and release_raw.get("status") == "active":
        release_raw["status"] = "rolled_back"
        release_raw["rolled_back_at"] = datetime.now(UTC).isoformat()
        release_raw["rollback_backup_path"] = _relative_path(root, resolved_backup)
        _atomic_write_bytes(paths["release"], _dump_yaml(release_raw))
    return {
        "schema_version": ERROR_POOL_PROMOTION_PLAN_SCHEMA,
        "mode": "rollback",
        "course_id": normalized_course,
        "status": "rolled_back",
        "runtime_catalog_sha256_before": current_fingerprint,
        "runtime_catalog_sha256_after": _sha256(backup_bytes),
        "backup_path": _relative_path(root, resolved_backup),
        "runtime_loaded": False,
    }
