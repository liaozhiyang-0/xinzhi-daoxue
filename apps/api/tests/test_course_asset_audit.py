from __future__ import annotations

from pathlib import Path

from scripts.audit_course_assets import _contest_package_report, build_report

ROOT = Path(__file__).resolve().parents[3]


def test_course_asset_audit_is_read_only_and_excludes_demo_cases() -> None:
    report = build_report(ROOT)

    assert report["schema_version"] == "course_asset_audit.v1"
    assert report["read_only"] is True
    assert set(report["courses"]) == {"CT", "AE"}
    assert report["courses"]["CT"]["skill_count"] == 10
    # AE now includes the domain-scoped Planner/Skill entries used by the
    # six-case pilot; the audit must include them while remaining read-only.
    assert report["courses"]["AE"]["skill_count"] == 17
    assert report["contest_support_boundary"]["demo_cases_included"] is False
    assert report["contest_support_boundary"]["package_scaffold_present"] is True
    assert report["contest_support_boundary"]["real_provider_calls"] is False
    assert report["contest_support_boundary"]["package_manifest_present"] is True
    assert report["contest_support_boundary"]["package_manifest_schema_errors"] == []
    assert report["contest_support_boundary"]["package_status"] == "draft_evidence_only"
    assert report["contest_support_boundary"]["evidence_matrix_present"] is True
    assert report["contest_support_boundary"]["evidence_matrix_nonempty"] is True
    assert report["contest_support_boundary"]["artifact_count"] == 10
    assert report["contest_support_boundary"]["artifact_ids_missing_files"] == []
    assert report["contest_support_boundary"]["pending_artifact_statuses"] == {
        "deployment_and_operations": "pending_docker_and_policy_records",
        "demo_user_guide": "pending_owner_designed_demos",
        "participation_info": "pending_official_rules",
        "source_and_model_notes": "pending_release_inventory",
        "user_pilot_log": "pending_authorized_pilot",
    }


def test_course_asset_audit_reports_knowledge_and_template_gaps() -> None:
    report = build_report(ROOT)

    knowledge = report["knowledge_inventory"]
    assert knowledge["manifest_present"] is True
    assert knowledge["document_count_by_course"]["CT"] > 0
    assert knowledge["document_count_by_course"]["AE"] > 0
    assert knowledge["quality_issue_count_by_course"]["CT"] > 0
    boundary = knowledge["course_boundary"]
    assert boundary["status"] == "clean"
    assert boundary["manifest_rows_missing_course_id"] == 0
    assert boundary["manifest_rows_unknown_course_id"] == 0
    assert all(
        count == 0
        for count in boundary[
            "possible_cross_course_placement_count_by_course"
        ].values()
    )
    ocr_quality = knowledge["ocr_quality_by_course"]
    for course in ("CT", "AE"):
        assert ocr_quality[course]["manifest_row_count"] > 0
        assert ocr_quality[course]["status"] in {
            "unavailable",
            "partial",
            "available",
        }
        assert (
            ocr_quality[course]["rows_with_ocr_confidence"]
            <= ocr_quality[course]["manifest_row_count"]
        )

    assert report["courses"]["AE"]["error_signature_coverage_ratio"] < 1
    assert "bjt_region_error" in report["courses"]["AE"]["uncovered_error_signatures"]


def test_course_asset_audit_reports_ae_verification_rule_evidence() -> None:
    report = build_report(ROOT)

    evidence = report["courses"]["AE"]["verification_rule_coverage"]

    assert evidence["schema_version"] == "verification_rule_evidence.v1"
    assert evidence["status"] == "covered"
    assert evidence["runtime_rule_count"] == 4
    assert evidence["covered_rule_count"] == 4
    assert evidence["coverage_ratio"] == 1.0
    assert evidence["schema_errors"] == []
    assert all(item["status"] == "covered" for item in evidence["rules"])


def test_course_asset_audit_reports_ct_rule_evidence_from_multiple_validators() -> None:
    report = build_report(ROOT)

    evidence = report["courses"]["CT"]["verification_rule_coverage"]

    assert evidence["schema_version"] == "verification_rule_evidence.v1"
    assert evidence["status"] == "covered"
    assert evidence["runtime_rule_count"] == 5
    assert evidence["declared_evidence_rule_count"] == 5
    assert evidence["covered_rule_count"] == 5
    assert evidence["coverage_ratio"] == 1.0
    assert all(
        item["status"] == "covered"
        for item in evidence["rules"]
    )
    assert evidence["schema_errors"] == []
    rule_by_name = {item["rule"]: item for item in evidence["rules"]}
    assert rule_by_name["kcl_kvl_consistency"]["validator_id"] == (
        "ct_deterministic_v1"
    )
    assert rule_by_name["power_energy_balance"]["validator_path"] == (
        "apps/api/app/services/ct_validator.py"
    )


def test_course_asset_audit_maps_ae_candidates_to_deterministic_evidence() -> None:
    report = build_report(ROOT)

    evidence = report["courses"]["AE"]["error_signature_evidence"]

    assert evidence["schema_version"] == "error_signature_evidence.v1"
    assert evidence["status"] == "evidence_ready"
    assert evidence["proposal_count"] == 6
    assert evidence["evidence_ready_count"] == 6
    assert evidence["coverage_ratio"] == 1.0
    assert evidence["teacher_review_pending_count"] == 6
    assert evidence["schema_errors"] == []
    assert all(item["runtime_eligible"] is False for item in evidence["items"])
    assert all(
        item["teacher_review_decision"] == "pending" for item in evidence["items"]
    )


def test_course_asset_audit_maps_ct_candidates_to_finite_evidence() -> None:
    report = build_report(ROOT)

    evidence = report["courses"]["CT"]["error_signature_evidence"]

    assert evidence["schema_version"] == "error_signature_evidence.v1"
    assert evidence["status"] == "evidence_ready"
    assert evidence["proposal_count"] == 4
    assert evidence["evidence_ready_count"] == 4
    assert evidence["coverage_ratio"] == 1.0
    assert evidence["teacher_review_pending_count"] == 4
    assert evidence["schema_errors"] == []
    assert all(item["runtime_eligible"] is False for item in evidence["items"])


def test_course_asset_audit_keeps_candidate_templates_out_of_runtime() -> None:
    report = build_report(ROOT)

    for course in ("CT", "AE"):
        details = report["courses"][course]
        assert details["error_template_proposals_present"] is True
        assert details["proposal_schema_errors"] == []
        assert details["proposals_runtime_loaded"] is False
        assert details["teacher_review_record_present"] is True
        assert details["teacher_review_record_schema_errors"] == []
        assert details["teacher_review_record_status"] == "pending_teacher_review"
        assert details["teacher_review_record_runtime_loaded"] is False
        assert details["approved_error_proposal_count"] == 0
        assert details["course_asset_manifest_present"] is True
        assert details["course_asset_manifest_schema_errors"] == []
        assert details["course_asset_manifest_runtime_loaded"] is False
        assert details["course_asset_manifest_runtime_source"] == (
            "apps/api/app/courses/registry.py"
        )
        assert details["proposed_gap_coverage_ratio"] == 1.0
        assert set(details["proposed_error_signatures"]) == set(
            details["uncovered_error_signatures"]
        )


def test_course_asset_audit_builds_evidence_gated_teacher_review_queue() -> None:
    report = build_report(ROOT)

    for course in ("CT", "AE"):
        details = report["courses"][course]
        queue = details["teacher_review_queue"]
        assert queue["schema_version"] == "teacher_review_queue.v1"
        assert queue["status"] == "pending_teacher_review"
        assert queue["runtime_loaded"] is False
        assert queue["item_count"] == details["proposed_error_template_count"]
        assert queue["unresolved_signatures_without_proposal"] == []
        assert queue["all_items_require_teacher_evidence"] is True
        assert all(item["evidence_required"] for item in queue["items"])
        assert all(item["runtime_eligible"] is False for item in queue["items"])
        assert all(item["review_decision"] == "pending" for item in queue["items"])
        assert all(item["covered_by_runtime"] is False for item in queue["items"])

    ct_items = report["courses"]["CT"]["teacher_review_queue"]["items"]
    kcl_item = next(
        item for item in ct_items if item["error_signature"] == "kcl_sign_error"
    )
    assert kcl_item["priority"] == "P1"
    assert kcl_item["priority_reason"] == "referenced_by_multiple_skills"
    assert kcl_item["skill_ids"] == ["CT.KCL", "CT.NODAL"]


def test_contest_package_audit_rejects_claim_boundary_flags(tmp_path: Path) -> None:
    package_root = tmp_path / "submission" / "contest_package"
    package_root.mkdir(parents=True)
    (package_root / "09_evidence_matrix.md").write_text("matrix", encoding="utf-8")
    manifest = """
schema_version: contest_package_manifest.v1
package_status: draft_evidence_only
official_rules_verified: true
official_score_claims_allowed: true
demo_cases_included: true
real_user_outcomes_included: true
real_provider_results_included: true
artifacts: []
"""
    (package_root / "package_manifest.yaml").write_text(
        manifest, encoding="utf-8"
    )

    report = _contest_package_report(tmp_path)

    assert report["evidence_matrix_nonempty"] is True
    assert report["artifact_count"] == 0
    assert set(report["package_manifest_schema_errors"]) == {
        "demo_cases_must_remain_excluded",
        "official_rules_must_remain_unverified",
        "official_score_claims_allowed_must_remain_false",
        "real_provider_results_included_must_remain_false",
        "real_user_outcomes_included_must_remain_false",
    }
