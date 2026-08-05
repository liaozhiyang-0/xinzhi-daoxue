from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

DEFAULT_COURSES = ("CT", "AE")
REPORT_SCHEMA_VERSION = "course_asset_audit.v1"
VERIFICATION_EVIDENCE_SCHEMA_VERSION = "verification_rule_evidence.v1"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.courses import default_course_registry  # noqa: E402


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _case_count(root: Path, courses: set[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    cases_root = root / "evaluation" / "cases"
    for path in sorted(cases_root.rglob("*.yaml")):
        value = _load_yaml(path)
        items = value if isinstance(value, list) else value.get("cases", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and str(item.get("course", "")) in courses:
                counts[str(item["course"])] += 1
    for path in sorted(cases_root.rglob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        items = value if isinstance(value, list) else value.get("cases", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and str(item.get("course", "")) in courses:
                counts[str(item["course"])] += 1
    return {course: counts[course] for course in sorted(courses)}


def _knowledge_inventory(root: Path, courses: set[str]) -> dict[str, Any]:
    manifest_path = root / "knowledge_indexes" / "knowledge_base_manifest.jsonl"
    counts: Counter[str] = Counter()
    parse_statuses: dict[str, Counter[str]] = defaultdict(Counter)
    quality_statuses: dict[str, Counter[str]] = defaultdict(Counter)
    ocr_rows: Counter[str] = Counter()
    ocr_confidence_rows: Counter[str] = Counter()
    ocr_manual_review_rows: Counter[str] = Counter()
    manifest_rows: list[dict[str, Any]] = []
    if manifest_path.is_file():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            manifest_rows.append(row)
            course = str(row.get("course_id", ""))
            if course in courses:
                counts[course] += 1
                parse_statuses[course][str(row.get("parse_status", "unknown"))] += 1
                quality_statuses[course][str(row.get("quality_status", "unknown"))] += 1
                if any(
                    key in row
                    for key in ("ocr_required", "ocr_status", "ocr_confidence")
                ):
                    ocr_rows[course] += 1
                if row.get("ocr_confidence") is not None:
                    ocr_confidence_rows[course] += 1
                if row.get("manual_review_required") is True:
                    ocr_manual_review_rows[course] += 1
    issue_path = root / "knowledge_indexes" / "knowledge_base_quality_issues.json"
    issues: list[dict[str, Any]] = []
    if issue_path.is_file():
        raw = json.loads(issue_path.read_text(encoding="utf-8"))
        issues = [item for item in raw.get("issues", []) if isinstance(item, dict)]
    issues_by_course = {
        course: dict(
            Counter(
                str(item.get("issue_type", "unknown"))
                for item in issues
                if str(item.get("course_id", "")) == course
            )
        )
        for course in sorted(courses)
    }
    known_courses = {"CT", "AE", "DE", "SS", "DSP", "COMM"}
    missing_course_id = 0
    unknown_course_id = 0
    source_relative_mismatches: Counter[str] = Counter()
    source_roots: dict[str, Counter[str]] = {
        course: Counter() for course in sorted(courses)
    }
    for row in manifest_rows:
        course = str(row.get("course_id", "")).upper()
        if not course:
            missing_course_id += 1
        elif course not in known_courses:
            unknown_course_id += 1
        if course not in source_roots:
            continue
        source_path = str(row.get("source_path", "")).replace("\\", "/")
        root_segment = source_path.split("/", 1)[0] if source_path else ""
        if root_segment:
            source_roots[course][root_segment] += 1
        if str(row.get("source_relative_path", row.get("relative_path", ""))) != str(
            row.get("relative_path", "")
        ):
            source_relative_mismatches[course] += 1

    dominant_root_by_course: dict[str, str | None] = {}
    root_mismatch_counts: dict[str, int] = {}
    for course in sorted(courses):
        ranked = source_roots[course].most_common()
        dominant_root_by_course[course] = ranked[0][0] if ranked else None
        root_mismatch_counts[course] = (
            sum(count for _, count in ranked[1:]) if ranked else 0
        )
    cross_course_issue_counts = {
        course: issues_by_course[course].get("possible_cross_course_placement", 0)
        for course in sorted(courses)
    }
    boundary_issue_count = (
        missing_course_id
        + unknown_course_id
        + sum(source_relative_mismatches.values())
        + sum(root_mismatch_counts.values())
        + sum(cross_course_issue_counts.values())
    )
    ocr_quality = {}
    for course in sorted(courses):
        row_count = counts[course]
        metadata_count = ocr_rows[course]
        ocr_quality[course] = {
            "manifest_row_count": row_count,
            "parse_status_counts": dict(parse_statuses[course]),
            "quality_status_counts": dict(quality_statuses[course]),
            "rows_with_ocr_metadata": metadata_count,
            "ocr_metadata_coverage_ratio": (
                round(metadata_count / row_count, 4) if row_count else None
            ),
            "rows_with_ocr_confidence": ocr_confidence_rows[course],
            "rows_with_manual_review_flag": ocr_manual_review_rows[course],
            "status": (
                "available"
                if metadata_count == row_count and row_count
                else "partial"
                if metadata_count
                else "unavailable"
            ),
        }
    return {
        "manifest_present": manifest_path.is_file(),
        "document_count_by_course": {
            course: counts[course] for course in sorted(courses)
        },
        "quality_issue_report_present": issue_path.is_file(),
        "quality_issue_count_by_course": {
            course: sum(issues_by_course[course].values()) for course in sorted(courses)
        },
        "quality_issue_types_by_course": issues_by_course,
        "ocr_quality_by_course": ocr_quality,
        "course_boundary": {
            "status": "clean" if boundary_issue_count == 0 else "review",
            "manifest_rows_missing_course_id": missing_course_id,
            "manifest_rows_unknown_course_id": unknown_course_id,
            "source_relative_path_mismatch_count_by_course": {
                course: source_relative_mismatches[course] for course in sorted(courses)
            },
            "source_root_segments_by_course": {
                course: sorted(source_roots[course]) for course in sorted(courses)
            },
            "dominant_source_root_by_course": dominant_root_by_course,
            "source_root_mismatch_count_by_course": root_mismatch_counts,
            "possible_cross_course_placement_count_by_course": (
                cross_course_issue_counts
            ),
        },
    }


def _contest_package_report(root: Path) -> dict[str, Any]:
    package_root = root / "submission" / "contest_package"
    manifest_path = package_root / "package_manifest.yaml"
    result: dict[str, Any] = {
        "package_manifest_present": manifest_path.is_file(),
        "package_manifest_schema_errors": [],
        "package_status": "missing_manifest",
        "official_rules_verified": False,
        "official_score_claims_allowed": False,
        "demo_cases_included": False,
        "real_user_outcomes_included": False,
        "real_provider_results_included": False,
        "evidence_matrix_present": (package_root / "09_evidence_matrix.md").is_file(),
        "evidence_matrix_nonempty": False,
        "artifact_count": 0,
        "artifact_status_counts": {},
        "artifact_ids_missing_files": [],
        "pending_artifact_ids": [],
        "pending_artifact_statuses": {},
    }
    if not manifest_path.is_file():
        return result

    raw = _load_yaml(manifest_path)
    errors: list[str] = []
    if raw.get("schema_version") != "contest_package_manifest.v1":
        errors.append("schema_version_invalid")
    if raw.get("official_rules_verified") is not False:
        errors.append("official_rules_must_remain_unverified")
    if raw.get("demo_cases_included") is not False:
        errors.append("demo_cases_must_remain_excluded")
    for boundary_key in (
        "official_score_claims_allowed",
        "real_user_outcomes_included",
        "real_provider_results_included",
    ):
        if raw.get(boundary_key) is not False:
            errors.append(f"{boundary_key}_must_remain_false")
    artifacts = raw.get("artifacts", [])
    if not isinstance(artifacts, list):
        errors.append("artifacts_must_be_list")
        artifacts = []
    status_counts: Counter[str] = Counter()
    missing_artifacts: list[str] = []
    pending_statuses: dict[str, str] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            errors.append("artifact_must_be_object")
            continue
        artifact_id = str(item.get("id", ""))
        artifact_path = package_root / str(item.get("path", ""))
        if not artifact_id or not item.get("path"):
            errors.append("artifact_id_and_path_required")
            continue
        status = str(item.get("status", "unknown"))
        status_counts[status] += 1
        if not artifact_path.is_file():
            errors.append(f"{artifact_id}:file_missing")
            missing_artifacts.append(artifact_id)
        if status.startswith("pending"):
            result["pending_artifact_ids"].append(artifact_id)
            pending_statuses[artifact_id] = status

    evidence_matrix_path = package_root / "09_evidence_matrix.md"
    result["evidence_matrix_nonempty"] = bool(
        evidence_matrix_path.is_file()
        and evidence_matrix_path.read_text(encoding="utf-8").strip()
    )

    result.update(
        {
            "package_manifest_schema_errors": sorted(errors),
            "package_status": str(raw.get("package_status", "unknown")),
            "official_rules_verified": bool(raw.get("official_rules_verified", False)),
            "official_score_claims_allowed": bool(
                raw.get("official_score_claims_allowed", False)
            ),
            "demo_cases_included": bool(raw.get("demo_cases_included", False)),
            "real_user_outcomes_included": bool(
                raw.get("real_user_outcomes_included", False)
            ),
            "real_provider_results_included": bool(
                raw.get("real_provider_results_included", False)
            ),
            "artifact_count": len(artifacts),
            "artifact_status_counts": dict(sorted(status_counts.items())),
            "artifact_ids_missing_files": sorted(missing_artifacts),
            "pending_artifact_statuses": dict(sorted(pending_statuses.items())),
        }
    )
    return result


def _course_asset_manifest(root: Path, course: str) -> dict[str, Any]:
    path = root / "config" / "course_assets" / f"{course}.yaml"
    result: dict[str, Any] = {
        "course_asset_manifest_present": path.is_file(),
        "course_asset_manifest_schema_errors": [],
        "course_asset_manifest_runtime_loaded": False,
        "course_asset_manifest_status": "missing_manifest",
        "course_asset_manifest_runtime_source": None,
    }
    if not path.is_file():
        return result

    raw = _load_yaml(path)
    errors: list[str] = []
    if raw.get("schema_version") != "course_asset_manifest.v1":
        errors.append("schema_version_invalid")
    if str(raw.get("course_id", "")).upper() != course:
        errors.append("course_id_mismatch")
    if raw.get("runtime_loaded") is not False:
        errors.append("runtime_loaded_must_be_false")
    if raw.get("runtime_source") != "apps/api/app/courses/registry.py":
        errors.append("runtime_source_must_reference_course_registry")
    sources = raw.get("sources", {})
    if not isinstance(sources, dict):
        errors.append("sources_must_be_object")
        sources = {}
    for source_id, source_path in sources.items():
        if source_path is None:
            continue
        if not isinstance(source_path, str) or Path(source_path).is_absolute():
            errors.append(f"{source_id}:source_path_invalid")
            continue
        if not (root / source_path).exists():
            errors.append(f"{source_id}:source_missing")

    result.update(
        {
            "course_asset_manifest_schema_errors": sorted(errors),
            "course_asset_manifest_runtime_loaded": raw.get("runtime_loaded") is True,
            "course_asset_manifest_status": str(
                raw.get("runtime_course_pack_status", "unknown")
            ),
            "course_asset_manifest_runtime_source": str(raw.get("runtime_source")),
        }
    )
    return result


def _verification_rule_coverage(root: Path, course: str) -> dict[str, Any]:
    """Verify repository evidence for the runtime CoursePack rules."""
    pack = default_course_registry().get(course)
    runtime_rules = list(pack.verification_rules)
    manifest_path = root / "config" / "course_assets" / f"{course}.yaml"
    if not manifest_path.is_file():
        return {
            "schema_version": VERIFICATION_EVIDENCE_SCHEMA_VERSION,
            "status": "missing_manifest",
            "runtime_rule_count": len(runtime_rules),
            "declared_evidence_rule_count": 0,
            "covered_rule_count": 0,
            "coverage_ratio": 0.0 if runtime_rules else 1.0,
            "rules": [],
            "schema_errors": ["course_asset_manifest_missing"],
        }

    raw = _load_yaml(manifest_path)
    evidence = raw.get("verification_rule_evidence") if isinstance(raw, dict) else None
    if not isinstance(evidence, dict):
        return {
            "schema_version": VERIFICATION_EVIDENCE_SCHEMA_VERSION,
            "status": "not_declared",
            "runtime_rule_count": len(runtime_rules),
            "declared_evidence_rule_count": 0,
            "covered_rule_count": 0,
            "coverage_ratio": 0.0 if runtime_rules else 1.0,
            "rules": [],
            "schema_errors": ["verification_rule_evidence_missing"],
        }

    schema_errors: list[str] = []
    if evidence.get("schema_version") != VERIFICATION_EVIDENCE_SCHEMA_VERSION:
        schema_errors.append("schema_version_invalid")
    validator_id = str(evidence.get("validator_id", ""))
    validator_path_value = evidence.get("validator_path")
    if not validator_id:
        schema_errors.append("validator_id_missing")
    if (
        not isinstance(validator_path_value, str)
        or Path(validator_path_value).is_absolute()
    ):
        schema_errors.append("validator_path_invalid")
        validator_path_value = ""
    validator_path = root / str(validator_path_value)
    if validator_path_value and not validator_path.is_file():
        schema_errors.append("validator_file_missing")

    rules = evidence.get("rules", {})
    if not isinstance(rules, dict):
        schema_errors.append("rules_must_be_object")
        rules = {}

    rule_reports: list[dict[str, Any]] = []
    covered_count = 0
    for rule in runtime_rules:
        item = rules.get(rule)
        errors: list[str] = []
        if not isinstance(item, dict):
            errors.append("evidence_missing")
            item = {}
        rule_validator_id = str(item.get("validator_id") or validator_id)
        rule_validator_path_value = item.get(
            "validator_path", validator_path_value
        )
        rule_validator_source = ""
        if not rule_validator_id:
            errors.append(f"{rule}:validator_id_missing")
        if (
            not isinstance(rule_validator_path_value, str)
            or Path(rule_validator_path_value).is_absolute()
        ):
            errors.append(f"{rule}:validator_path_invalid")
            rule_validator_path_value = ""
        rule_validator_path = root / str(rule_validator_path_value)
        if rule_validator_path_value and not rule_validator_path.is_file():
            errors.append(
                f"{rule}:validator_file_missing:{rule_validator_path_value}"
            )
        elif rule_validator_path_value:
            rule_validator_source = rule_validator_path.read_text(encoding="utf-8")
        conflict_types = item.get("conflict_types", [])
        if not isinstance(conflict_types, list) or not conflict_types:
            errors.append("conflict_types_missing")
            conflict_types = []
        test_files = item.get("test_files", [])
        if not isinstance(test_files, list) or not test_files:
            errors.append("test_files_missing")
            test_files = []
        test_sources: list[str] = []
        for test_file in test_files:
            if not isinstance(test_file, str) or Path(test_file).is_absolute():
                errors.append(f"{rule}:test_file_path_invalid")
                continue
            path = root / test_file
            if not path.is_file():
                errors.append(f"{rule}:test_file_missing:{test_file}")
                continue
            test_sources.append(path.read_text(encoding="utf-8"))
        combined_tests = "\n".join(test_sources)
        for conflict_type in conflict_types:
            signature = str(conflict_type)
            if not signature:
                errors.append(f"{rule}:empty_conflict_type")
                continue
            if signature not in rule_validator_source:
                errors.append(f"{rule}:validator_conflict_type_missing:{signature}")
            if signature not in combined_tests:
                errors.append(f"{rule}:test_conflict_type_missing:{signature}")
        status = "covered" if not errors else "review"
        if status == "covered":
            covered_count += 1
        rule_reports.append(
            {
                "rule": rule,
                "status": status,
                "validator_id": rule_validator_id,
                "validator_path": str(rule_validator_path_value),
                "conflict_types": [str(value) for value in conflict_types],
                "test_files": [str(value) for value in test_files],
                "errors": sorted(errors),
            }
        )

    extra_rules = sorted(set(str(key) for key in rules) - set(runtime_rules))
    schema_errors.extend(f"rule_not_in_runtime:{rule}" for rule in extra_rules)
    status = (
        "covered"
        if runtime_rules and covered_count == len(runtime_rules) and not schema_errors
        else "review"
        if runtime_rules
        else "not_applicable"
    )
    return {
        "schema_version": VERIFICATION_EVIDENCE_SCHEMA_VERSION,
        "status": status,
        "runtime_rule_count": len(runtime_rules),
        "declared_evidence_rule_count": len(rules),
        "covered_rule_count": covered_count,
        "coverage_ratio": (
            covered_count / len(runtime_rules) if runtime_rules else 1.0
        ),
        "validator_id": validator_id,
        "validator_path": str(validator_path_value),
        "rules": rule_reports,
        "schema_errors": sorted(schema_errors),
    }


def _error_signature_evidence(
    root: Path,
    course: str,
    verification_report: dict[str, Any],
) -> dict[str, Any]:
    """Check deterministic evidence for disabled candidate error signatures."""
    proposal_path = root / "config" / "error_pool" / "proposals" / f"{course}.yaml"
    manifest_path = root / "config" / "course_assets" / f"{course}.yaml"
    proposals_raw = _load_yaml(proposal_path) if proposal_path.is_file() else {}
    manifest_raw = _load_yaml(manifest_path) if manifest_path.is_file() else {}
    evidence = (
        manifest_raw.get("error_signature_evidence")
        if isinstance(manifest_raw, dict)
        else None
    )
    proposals = proposals_raw.get("proposals", [])
    proposal_rows = [item for item in proposals if isinstance(item, dict)]
    proposal_by_signature = {
        str(item.get("error_signature")): item for item in proposal_rows
    }
    if not isinstance(evidence, dict):
        return {
            "schema_version": "error_signature_evidence.v1",
            "status": "not_declared",
            "proposal_count": len(proposal_by_signature),
            "mapped_signature_count": 0,
            "evidence_ready_count": 0,
            "coverage_ratio": 0.0 if proposal_by_signature else 1.0,
            "teacher_review_pending_count": len(proposal_by_signature),
            "items": [],
            "schema_errors": ["error_signature_evidence_missing"],
        }

    schema_errors: list[str] = []
    if evidence.get("schema_version") != "error_signature_evidence.v1":
        schema_errors.append("schema_version_invalid")
    mappings = evidence.get("mappings", {})
    if not isinstance(mappings, dict):
        schema_errors.append("mappings_must_be_object")
        mappings = {}
    test_files = evidence.get("test_files", [])
    if not isinstance(test_files, list) or not test_files:
        schema_errors.append("test_files_missing")
        test_files = []
    test_sources: list[str] = []
    for test_file in test_files:
        if not isinstance(test_file, str) or Path(test_file).is_absolute():
            schema_errors.append("test_file_path_invalid")
            continue
        path = root / test_file
        if not path.is_file():
            schema_errors.append(f"test_file_missing:{test_file}")
            continue
        test_sources.append(path.read_text(encoding="utf-8"))
    validator_path = root / str(verification_report.get("validator_path", ""))
    validator_source = (
        validator_path.read_text(encoding="utf-8") if validator_path.is_file() else ""
    )
    review_path = root / "config" / "error_pool" / "reviews" / f"{course}.yaml"
    review_raw = _load_yaml(review_path) if review_path.is_file() else {}
    decisions = review_raw.get("decisions", []) if isinstance(review_raw, dict) else []
    decision_by_proposal = {
        str(item.get("proposal_id")): str(item.get("decision", "pending"))
        for item in decisions
        if isinstance(item, dict) and item.get("proposal_id")
    }

    items: list[dict[str, Any]] = []
    ready_count = 0
    for signature, proposal in sorted(proposal_by_signature.items()):
        mapping = mappings.get(signature)
        errors: list[str] = []
        if not isinstance(mapping, dict):
            errors.append("mapping_missing")
            mapping = {}
        conflict_types = mapping.get("conflict_types", [])
        if not isinstance(conflict_types, list) or not conflict_types:
            errors.append("conflict_types_missing")
            conflict_types = []
        combined_tests = "\n".join(test_sources)
        for conflict_type in conflict_types:
            value = str(conflict_type)
            if value not in validator_source:
                errors.append(f"validator_conflict_type_missing:{value}")
            if value not in combined_tests:
                errors.append(f"test_conflict_type_missing:{value}")
        status = "evidence_ready" if not errors else "review"
        if status == "evidence_ready":
            ready_count += 1
        items.append(
            {
                "error_signature": signature,
                "proposal_id": str(proposal.get("proposal_id", "")),
                "conflict_types": [str(value) for value in conflict_types],
                "teacher_review_decision": decision_by_proposal.get(
                    str(proposal.get("proposal_id", "")), "not_recorded"
                ),
                "runtime_eligible": False,
                "status": status,
                "errors": sorted(errors),
            }
        )

    extra_mappings = sorted(
        set(str(key) for key in mappings) - set(proposal_by_signature)
    )
    schema_errors.extend(
        f"mapping_not_in_proposals:{signature}" for signature in extra_mappings
    )
    pending_count = sum(item["teacher_review_decision"] == "pending" for item in items)
    status = (
        "evidence_ready"
        if proposal_by_signature
        and ready_count == len(proposal_by_signature)
        and not schema_errors
        else "review"
        if proposal_by_signature
        else "not_applicable"
    )
    return {
        "schema_version": "error_signature_evidence.v1",
        "status": status,
        "proposal_count": len(proposal_by_signature),
        "mapped_signature_count": len(mappings),
        "evidence_ready_count": ready_count,
        "coverage_ratio": (
            ready_count / len(proposal_by_signature) if proposal_by_signature else 1.0
        ),
        "teacher_review_pending_count": pending_count,
        "items": items,
        "schema_errors": sorted(schema_errors),
    }


def _course_config(root: Path, course: str) -> dict[str, Any]:
    skill_path = root / "config" / "skills" / f"{course}.yaml"
    error_path = root / "config" / "error_pool" / f"{course}.yaml"
    pack_path = (
        root / "agent_configs" / "course_packs" / f"course_{course.casefold()}_v1.yaml"
    )
    skills = _load_yaml(skill_path).get("skills", []) if skill_path.is_file() else []
    errors = _load_yaml(error_path).get("errors", []) if error_path.is_file() else []
    skill_error_signatures = {
        str(signature)
        for skill in skills
        if isinstance(skill, dict)
        for signature in skill.get("common_error_signatures", [])
    }
    usable_error_signatures = {
        str(item.get("error_signature"))
        for item in errors
        if isinstance(item, dict)
        and item.get("enabled") is True
        and item.get("teacher_reviewed") is True
        and item.get("match_mode") == "exact_rule"
    }
    covered = skill_error_signatures.intersection(usable_error_signatures)
    missing_signatures = sorted(skill_error_signatures - usable_error_signatures)
    proposal_path = root / "config" / "error_pool" / "proposals" / f"{course}.yaml"
    release_path = root / "config" / "error_pool" / "releases" / f"{course}.yaml"
    release_raw = _load_yaml(release_path) if release_path.is_file() else {}
    active_release_ids = {
        str(item.get("proposal_id"))
        for item in release_raw.get("promoted_proposals", [])
        if isinstance(release_raw, dict)
        and release_raw.get("schema_version") == "error_pool_release.v1"
        and release_raw.get("status") == "active"
        and isinstance(item, dict)
        and item.get("proposal_id")
    }
    proposal_rows = (
        _load_yaml(proposal_path).get("proposals", [])
        if proposal_path.is_file()
        else []
    )
    promoted_signatures = {
        str(item.get("error_signature"))
        for item in proposal_rows
        if isinstance(item, dict)
        and str(item.get("proposal_id", "")) in active_release_ids
    }
    proposal_report = _proposal_config(
        proposal_path,
        course,
        set(missing_signatures),
        promoted_signatures,
    )
    review_path = root / "config" / "error_pool" / "reviews" / f"{course}.yaml"
    review_report = _review_record(
        review_path,
        course,
        set(proposal_report["proposed_error_proposal_ids"]),
    )
    teacher_review_queue = _teacher_review_queue(
        root,
        course,
        set(missing_signatures),
        proposal_report,
    )
    asset_manifest_report = _course_asset_manifest(root, course)
    verification_rule_report = _verification_rule_coverage(root, course)
    error_signature_report = _error_signature_evidence(
        root, course, verification_rule_report
    )
    return {
        "skill_config_present": skill_path.is_file(),
        "skill_count": len(skills),
        "error_pool_config_present": error_path.is_file(),
        "error_template_count": len(errors),
        "usable_error_template_count": len(usable_error_signatures),
        "error_signature_coverage_ratio": (
            len(covered) / len(skill_error_signatures)
            if skill_error_signatures
            else 1.0
        ),
        "uncovered_error_signatures": missing_signatures,
        "course_pack_compatibility_yaml_present": pack_path.is_file(),
        **proposal_report,
        **review_report,
        "teacher_review_queue": teacher_review_queue,
        **asset_manifest_report,
        "verification_rule_coverage": verification_rule_report,
        "error_signature_evidence": error_signature_report,
    }


def _proposal_config(
    path: Path,
    course: str,
    uncovered_signatures: set[str],
    allowed_covered_signatures: set[str] | None = None,
) -> dict[str, Any]:
    """Inspect disabled proposals without treating them as runtime templates."""
    empty = {
        "error_template_proposals_present": False,
        "proposed_error_template_count": 0,
        "proposed_error_signatures": [],
        "proposed_error_proposal_ids": [],
        "proposed_gap_coverage_ratio": 0.0 if uncovered_signatures else 1.0,
        "proposal_schema_errors": [],
        "proposals_runtime_loaded": False,
    }
    if not path.is_file():
        return empty

    raw = _load_yaml(path)
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
        errors.append("proposals_must_be_list")
        proposals = []
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

    proposed_gap = set(signatures).intersection(uncovered_signatures)
    return {
        "error_template_proposals_present": True,
        "proposed_error_template_count": len(proposals),
        "proposed_error_signatures": sorted(signatures),
        "proposed_error_proposal_ids": sorted(proposal_ids),
        "proposed_gap_coverage_ratio": (
            len(proposed_gap) / len(uncovered_signatures)
            if uncovered_signatures
            else 1.0
        ),
        "proposal_schema_errors": sorted(errors),
        "proposals_runtime_loaded": raw.get("runtime_loaded") is True,
    }


def _teacher_review_queue(
    root: Path,
    course: str,
    uncovered_signatures: set[str],
    proposal_report: dict[str, Any],
) -> dict[str, Any]:
    """Build a read-only queue for proposals that require teacher evidence."""
    proposal_path = root / "config" / "error_pool" / "proposals" / f"{course}.yaml"
    review_path = root / "config" / "error_pool" / "reviews" / f"{course}.yaml"
    result: dict[str, Any] = {
        "schema_version": "teacher_review_queue.v1",
        "status": "missing_proposals",
        "runtime_loaded": False,
        "item_count": 0,
        "items": [],
        "unresolved_signatures_without_proposal": sorted(uncovered_signatures),
        "all_items_require_teacher_evidence": True,
    }
    if not proposal_path.is_file():
        return result

    proposal_raw = _load_yaml(proposal_path)
    proposals = proposal_raw.get("proposals", [])
    if not isinstance(proposals, list):
        return result | {"status": "invalid_proposals"}

    def sorted_strings(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return sorted({str(item) for item in value if item is not None})

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

    items: list[dict[str, Any]] = []
    proposal_signatures: set[str] = set()
    release_path = root / "config" / "error_pool" / "releases" / f"{course}.yaml"
    release_raw = _load_yaml(release_path) if release_path.is_file() else {}
    active_release_ids = {
        str(item.get("proposal_id"))
        for item in release_raw.get("promoted_proposals", [])
        if isinstance(release_raw, dict)
        and release_raw.get("schema_version") == "error_pool_release.v1"
        and release_raw.get("status") == "active"
        and isinstance(item, dict)
        and item.get("proposal_id")
    }
    for item in proposals:
        if not isinstance(item, dict):
            continue
        proposal_id = str(item.get("proposal_id", ""))
        signature = str(item.get("error_signature", ""))
        if not proposal_id or not signature:
            continue
        if proposal_id in active_release_ids and signature not in uncovered_signatures:
            continue
        proposal_signatures.add(signature)
        skill_ids = sorted_strings(item.get("skill_ids", []))
        problem_types = sorted_strings(item.get("problem_types", []))
        decision = decisions.get(proposal_id, {})
        evidence_refs = decision.get("evidence_refs", [])
        if not isinstance(evidence_refs, list):
            evidence_refs = []
        priority = "P1" if len(skill_ids) > 1 else "P2"
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
                "covered_by_runtime": signature not in uncovered_signatures,
                "review_decision": str(decision.get("decision", "not_recorded")),
                "review_evidence_refs": [str(ref) for ref in evidence_refs],
                "evidence_required": True,
                "runtime_eligible": False,
                "next_action": "teacher_review_with_evidence",
            }
        )

    items.sort(key=lambda item: (item["priority"], item["proposal_id"]))
    result.update(
        {
            "status": (
                "schema_error"
                if proposal_report["proposal_schema_errors"]
                else str(review_status)
            ),
            "item_count": len(items),
            "items": items,
            "unresolved_signatures_without_proposal": sorted(
                uncovered_signatures - proposal_signatures
            ),
            "proposal_schema_errors": proposal_report["proposal_schema_errors"],
        }
    )
    return result


def _review_record(
    path: Path,
    course: str,
    proposal_ids: set[str],
) -> dict[str, Any]:
    empty = {
        "teacher_review_record_present": False,
        "teacher_review_record_schema_errors": [],
        "teacher_review_record_status": "missing_record",
        "teacher_review_record_runtime_loaded": False,
        "approved_error_proposal_count": 0,
    }
    if not path.is_file():
        return empty

    raw = _load_yaml(path)
    errors: list[str] = []
    if raw.get("schema_version") != "error_pool_review.v1":
        errors.append("schema_version_invalid")
    if str(raw.get("course_id", "")).upper() != course:
        errors.append("course_id_mismatch")
    if raw.get("runtime_loaded") is not False:
        errors.append("runtime_loaded_must_be_false")
    if raw.get("review_status") not in {
        "pending_teacher_review",
        "in_review",
        "completed",
        "teacher_review_in_progress",
        "teacher_review_complete",
    }:
        errors.append("review_status_invalid")

    decisions = raw.get("decisions", [])
    if not isinstance(decisions, list):
        errors.append("decisions_must_be_list")
        decisions = []
    recorded_ids: list[str] = []
    approved_count = 0
    for index, item in enumerate(decisions):
        if not isinstance(item, dict):
            errors.append(f"decision_{index}_must_be_object")
            continue
        proposal_id = str(item.get("proposal_id", ""))
        decision = str(item.get("decision", ""))
        if not proposal_id:
            errors.append(f"decision_{index}_missing_proposal_id")
            continue
        recorded_ids.append(proposal_id)
        if proposal_id not in proposal_ids:
            errors.append(f"{proposal_id}:proposal_not_found")
        if decision not in {"pending", "approved", "rejected"}:
            errors.append(f"{proposal_id}:decision_invalid")
        if decision == "approved":
            approved_count += 1
            if not item.get("evidence_refs"):
                errors.append(f"{proposal_id}:approved_requires_evidence_refs")
            if not raw.get("reviewer") or not raw.get("reviewed_at"):
                errors.append(f"{proposal_id}:approved_requires_reviewer_and_date")
        if decision == "rejected" and not raw.get("reviewer"):
            errors.append(f"{proposal_id}:rejected_requires_reviewer")
    if len(recorded_ids) != len(set(recorded_ids)):
        errors.append("duplicate_review_proposal_id")
    if set(recorded_ids) != proposal_ids:
        errors.append("review_record_must_cover_all_proposals")

    return {
        "teacher_review_record_present": True,
        "teacher_review_record_schema_errors": sorted(errors),
        "teacher_review_record_status": str(raw.get("review_status", "unknown")),
        "teacher_review_record_runtime_loaded": raw.get("runtime_loaded") is True,
        "approved_error_proposal_count": approved_count,
    }


def build_report(
    root: Path,
    courses: Sequence[str] = DEFAULT_COURSES,
) -> dict[str, Any]:
    selected = {course.upper() for course in courses}
    if not selected:
        raise ValueError("at least one course is required")
    course_reports = {
        course: _course_config(root, course) for course in sorted(selected)
    }
    contest_boundary = {
        "package_scaffold_present": (
            root / "submission" / "contest_package" / "README.md"
        ).is_file(),
        **_contest_package_report(root),
        "official_rules_verified": False,
        "official_score_claims_allowed": False,
        "demo_cases_included": False,
        "real_provider_calls": False,
        "real_user_outcomes": False,
        "notes": [
            "Candidate error templates remain disabled until teacher review.",
            "Three demonstration cases remain user-designed and excluded.",
            "This report is repository evidence, not a contest submission result.",
        ],
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "read_only": True,
        "courses": course_reports,
        "knowledge_inventory": _knowledge_inventory(root, selected),
        "evaluation_case_count_by_course": _case_count(root, selected),
        "contest_support_boundary": contest_boundary,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only CT/AE course asset and contest evidence audit"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="project root",
    )
    parser.add_argument(
        "--course",
        action="append",
        choices=sorted(DEFAULT_COURSES),
        help="course to include; repeat to include multiple courses",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON output path; stdout is used by default",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.root.resolve(), args.course or DEFAULT_COURSES)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"course asset audit written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
