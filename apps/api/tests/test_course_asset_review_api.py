from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from app.evaluation.contracts import (
    EvaluationResult,
    EvaluationRunMetadata,
    SuiteReport,
)
from app.services.course_asset_review import (
    attach_evaluation_provenance_readiness,
    attach_ocr_decision_readiness,
    build_error_pool_review_document,
    build_teacher_review_queue,
    summarize_teacher_review_evidence,
)
from app.services.evaluation_provenance import build_evaluation_provenance
from pypdf import PdfWriter


@pytest.mark.parametrize(("course_id", "expected_count"), [("CT", 4), ("AE", 6)])
def test_course_asset_review_queue_is_read_only(
    client, course_id: str, expected_count: int
) -> None:
    response = client.get(
        "/api/v1/knowledge/course-asset-review-queue",
        params={"course_id": course_id},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["schema_version"] == "teacher_review_queue.v1"
    assert payload["course_id"] == course_id
    assert payload["status"] == "pending_teacher_review"
    assert payload["item_count"] == expected_count
    assert payload["runtime_loaded"] is False
    assert payload["all_items_require_teacher_evidence"] is True
    assert payload["unresolved_signatures_without_proposal"] == []
    assert all(item["runtime_eligible"] is False for item in payload["items"])
    assert all(item["review_decision"] == "pending" for item in payload["items"])
    assert all(
        item["review_evidence_quality"] == "missing" for item in payload["items"]
    )
    if course_id == "AE":
        assert all(
            item["deterministic_evidence_status"] == "evidence_ready"
            for item in payload["items"]
        )
        assert all(item["deterministic_conflict_types"] for item in payload["items"])
        assert all(
            item["deterministic_evidence_scope"] == "finite_deterministic"
            for item in payload["items"]
        )
    if course_id == "CT":
        assert all(
            item["deterministic_evidence_scope"] == "structured_fields_only"
            for item in payload["items"]
        )
        assert all(
            item["deterministic_validator_id"] == "ct_deterministic_v1"
            for item in payload["items"]
        )


def test_course_asset_review_queue_rejects_non_ct_ae_course(client) -> None:
    response = client.get(
        "/api/v1/knowledge/course-asset-review-queue",
        params={"course_id": "DE"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported course_id"


def test_error_pool_review_document_requires_evidence_and_keeps_runtime_disabled() -> (
    None
):
    root = Path(__file__).resolve().parents[3]
    queue = build_teacher_review_queue(root, "CT")
    proposal_id = queue["items"][0]["proposal_id"]
    with pytest.raises(ValueError, match="evidence_refs_required"):
        build_error_pool_review_document(
            queue,
            "CT",
            [{"proposal_id": proposal_id, "decision": "approved"}],
            source_fingerprint=queue["source_fingerprint"],
            reviewer="teacher-test",
            reviewed_at="2026-08-04T00:00:00+00:00",
        )

    document = build_error_pool_review_document(
        queue,
        "CT",
        [
            {
                "proposal_id": item["proposal_id"],
                "decision": "pending",
                "evidence_refs": [],
                "notes": "",
            }
            for item in queue["items"]
        ],
        source_fingerprint=queue["source_fingerprint"],
        reviewer="teacher-test",
        reviewed_at="2026-08-04T00:00:00+00:00",
    )
    assert document["runtime_loaded"] is False
    assert document["review_status"] == "pending_teacher_review"


def test_error_pool_review_rejects_untraceable_evidence_reference() -> None:
    root = Path(__file__).resolve().parents[3]
    queue = build_teacher_review_queue(root, "CT")
    proposal_id = queue["items"][0]["proposal_id"]

    with pytest.raises(ValueError, match="evidence_refs_untraceable"):
        build_error_pool_review_document(
            queue,
            "CT",
            [
                {
                    "proposal_id": proposal_id,
                    "decision": "approved",
                    "evidence_refs": ["teacher-review"],
                }
            ],
            source_fingerprint=queue["source_fingerprint"],
            reviewer="teacher-test",
            reviewed_at="2026-08-04T00:00:00+00:00",
        )


def test_save_error_pool_review_decisions_is_atomic_and_refreshes_queue(
    client, settings, tmp_path
) -> None:
    project_root = Path(__file__).resolve().parents[3]
    shutil.copytree(project_root / "config", tmp_path / "config")
    settings.knowledge_config_path = tmp_path / "knowledge_config"

    queue_response = client.get(
        "/api/v1/knowledge/course-asset-review-queue", params={"course_id": "AE"}
    )
    assert queue_response.status_code == 200, queue_response.text
    queue = queue_response.json()
    response = client.put(
        "/api/v1/knowledge/course-asset-review-decisions/AE",
        json={
            "source_fingerprint": queue["source_fingerprint"],
            "reviewer": "teacher-test",
            "decisions": [
                {
                    "proposal_id": item["proposal_id"],
                    "decision": "approved",
                    "evidence_refs": ["teacher-notes/AE-review.md#1"],
                    "notes": "Verified against the course material.",
                }
                for item in queue["items"]
            ],
        },
    )

    assert response.status_code == 200, response.text
    refreshed = response.json()
    assert refreshed["status"] == "teacher_review_complete"
    assert all(item["review_decision"] == "approved" for item in refreshed["items"])
    assert all(item["runtime_eligible"] is False for item in refreshed["items"])
    assert (tmp_path / "config/error_pool/reviews/AE.yaml").is_file()

    stale_response = client.put(
        "/api/v1/knowledge/course-asset-review-decisions/AE",
        json={
            "source_fingerprint": queue["source_fingerprint"],
            "reviewer": "teacher-test",
            "decisions": [],
        },
    )
    assert stale_response.status_code == 409


@pytest.mark.parametrize(("course_id", "expected_queue"), [("CT", 4), ("AE", 6)])
def test_course_asset_readiness_reports_evidence_blockers(
    client, course_id: str, expected_queue: int
) -> None:
    response = client.get(
        "/api/v1/knowledge/course-asset-readiness",
        params={"course_id": course_id},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["schema_version"] == "course_asset_readiness.v1"
    assert payload["course_id"] == course_id
    assert payload["status"] == "evidence_pending"
    assert payload["runtime_loaded"] is False
    assert payload["teacher_review_queue"]["item_count"] == expected_queue
    assert payload["teacher_review_evidence"]["status"] == "missing"
    assert payload["teacher_review_evidence"]["missing_count"] == expected_queue
    assert (
        payload["teacher_review_evidence"]["deterministic_evidence_status"]
        == "ready"
    )
    assert (
        payload["teacher_review_evidence"]["deterministic_evidence_ready_count"]
        == expected_queue
    )
    assert (
        payload["teacher_review_evidence"]["deterministic_evidence_not_ready_count"]
        == 0
    )
    inventory = payload["knowledge_inventory"]
    assert inventory["manifest_present"] is True
    assert inventory["document_count"] > 0
    assert inventory["quality_issue_count"] >= 0
    assert inventory["ocr_status"] in {"available", "partial", "unavailable"}
    assert (
        inventory["ocr_metadata_coverage_ratio"] is None
        or 0 <= inventory["ocr_metadata_coverage_ratio"] <= 1
    )
    provenance = payload["evaluation_provenance"]
    assert provenance["schema_version"] == "course_evaluation_provenance.v1"
    assert provenance["report_present"] is True
    assert provenance["report_valid"] is True
    assert provenance["course_case_count"] >= 0
    assert provenance["raw_results_included"] is False
    checks = {item["key"]: item for item in payload["evidence_checks"]}
    assert checks["material_lifecycle"]["declared_status"] == "implemented"
    assert checks["material_lifecycle"]["observed_status"] == "implemented"
    assert checks["material_lifecycle"]["evidence_status"] == "present"
    assert checks["runtime_error_template_coverage"]["observed_status"] == "partial"
    assert checks["official_rules"]["evidence_status"] == "boundary_declared"
    assert checks["official_rules"]["observed_status"] == "not_verified"
    assert not any(
        item["code"].startswith("readiness_evidence_mismatch_")
        for item in payload["blockers"]
    )
    assert payload["contest_boundary"]["official_rules_verified"] is False
    assert payload["contest_boundary"]["official_score_claims_allowed"] is False
    assert payload["contest_boundary"]["real_provider_results_included"] is False
    assert payload["boundaries"]["modifies_frozen_baseline"] is False
    blocker_codes = {item["code"] for item in payload["blockers"]}
    assert "teacher_review_required" in blocker_codes
    assert "readiness_official_rules" in blocker_codes
    assert "readiness_demonstration_cases" in blocker_codes
    assert "readiness_real_user_outcomes" in blocker_codes
    assert "knowledge_quality_issues_present" in blocker_codes
    assert "knowledge_ocr_metadata_unavailable" in blocker_codes


def test_teacher_review_evidence_summary_reports_untraceable_decisions() -> None:
    summary = summarize_teacher_review_evidence(
        {
            "items": [
                {"proposal_id": "A", "review_evidence_quality": "traceable"},
                {"proposal_id": "B", "review_evidence_quality": "untraceable"},
            ]
        }
    )

    assert summary["status"] == "untraceable"
    assert summary["traceable_count"] == 1
    assert summary["untraceable_count"] == 1
    assert summary["untraceable_proposal_ids"] == ["B"]


def test_teacher_review_evidence_summary_reports_validator_gaps() -> None:
    summary = summarize_teacher_review_evidence(
        {
            "items": [
                {
                    "proposal_id": "A",
                    "review_evidence_quality": "missing",
                    "deterministic_evidence_status": "evidence_ready",
                    "deterministic_evidence_scope": "structured_fields_only",
                    "deterministic_validator_id": "ct_deterministic_v1",
                },
                {
                    "proposal_id": "B",
                    "review_evidence_quality": "missing",
                    "deterministic_evidence_status": "not_declared",
                    "deterministic_evidence_scope": "not_declared",
                },
            ]
        }
    )

    assert summary["deterministic_evidence_status"] == "partial"
    assert summary["deterministic_evidence_ready_count"] == 1
    assert summary["deterministic_evidence_not_ready_count"] == 1
    assert summary["deterministic_evidence_not_ready_proposal_ids"] == ["B"]
    assert summary["deterministic_evidence_scope_counts"] == {
        "not_declared": 1,
        "structured_fields_only": 1,
    }
    assert summary["deterministic_validator_ids"] == ["ct_deterministic_v1"]


def test_course_asset_readiness_rejects_non_ct_ae_course(client) -> None:
    response = client.get(
        "/api/v1/knowledge/course-asset-readiness",
        params={"course_id": "DE"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported course_id"


def test_course_asset_readiness_includes_ocr_decision_gate(
    client, settings, tmp_path
) -> None:
    settings.knowledge_ocr_decisions_path = tmp_path / "ocr-decisions"
    settings.knowledge_ct_path.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with (settings.knowledge_ct_path / "scan.pdf").open("wb") as handle:
        writer.write(handle)

    response = client.get(
        "/api/v1/knowledge/course-asset-readiness",
        params={"course_id": "CT"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    ocr_evidence = payload["ocr_decision_evidence"]
    assert ocr_evidence["status"] == "decision_file_missing"
    assert ocr_evidence["candidate_count"] == 1
    blocker_codes = {item["code"] for item in payload["blockers"]}
    assert "knowledge_ocr_decision_file_missing" in blocker_codes
    assert "create_pending_ocr_decision_file" in payload["next_actions"]


def test_attach_ocr_decision_readiness_maps_pending_evidence_to_blocker() -> None:
    result = attach_ocr_decision_readiness(
        {"status": "ready", "blockers": [], "next_actions": []},
        {
            "status": "complete_without_evidence",
            "candidate_count": 2,
            "rows_missing_evidence_refs": 1,
            "next_action": "add_evidence_refs_to_ocr_decisions",
        },
    )

    assert result["status"] == "evidence_pending"
    assert result["ocr_decision_evidence"]["status"] == ("complete_without_evidence")
    assert result["blockers"] == [
        {
            "code": "knowledge_ocr_decisions_missing_evidence",
            "severity": "high",
            "message": (
                "OCR decisions are complete but one or more rows lack "
                "evidence references."
            ),
        }
    ]
    assert result["next_actions"] == ["add_evidence_refs_to_ocr_decisions"]


def test_evaluation_provenance_is_bounded_and_preserves_missing_metadata(
    tmp_path,
) -> None:
    report_path = tmp_path / "latest.json"
    results = [
        EvaluationResult(
            case_id="CASE_001",
            status="passed",
            route_passed=True,
            course_passed=True,
            agent_passed=True,
            structure_passed=True,
            execution_path_passed=True,
            tools_passed=True,
            answer_passed=True,
            citations_passed=True,
            safety_passed=True,
            total_score=100,
            expected={"course": "CT"},
        ).model_dump(mode="json"),
        EvaluationResult(
            case_id="CASE_002",
            status="failed",
            route_passed=True,
            course_passed=True,
            agent_passed=True,
            structure_passed=True,
            execution_path_passed=True,
            tools_passed=True,
            answer_passed=False,
            citations_passed=True,
            safety_passed=True,
            total_score=0,
            expected={"course": "CT"},
        ).model_dump(mode="json"),
    ]
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "mode": "offline",
                "started_at": "2026-08-03T00:00:00+00:00",
                "completed_at": "2026-08-03T00:01:00+00:00",
                "filters": {},
                "summary": {
                    "total": 2,
                    "passed": 1,
                    "failed": 1,
                    "errors": 0,
                    "timeouts": 0,
                    "cached": 0,
                },
                "statistics": {
                    "by_course": {"CT": {"total": 2, "passed": 1, "pass_rate": 0.5}}
                },
                "results": results,
                "estimated_cost": None,
            }
        ),
        encoding="utf-8",
    )

    provenance = build_evaluation_provenance(report_path, "ct")

    assert provenance["status"] == "available"
    assert provenance["course_case_count"] == 2
    assert provenance["course_passed_count"] == 1
    assert provenance["course_pass_rate"] == 0.5
    assert provenance["run_metadata_present"] is False
    assert provenance["run_id"] is None
    assert provenance["raw_results_included"] is False
    assert provenance["consistency"]["status"] == "partial"
    assert provenance["consistency"]["summary_result_count_match"] is True
    assert provenance["consistency"]["course_statistics_match"] is True
    assert "answer" not in provenance
    assert "results" not in provenance


@pytest.mark.parametrize(
    ("contents", "expected_status"),
    [("{not-json", "report_invalid"), (None, "report_missing")],
)
def test_evaluation_provenance_reports_missing_or_invalid_snapshot(
    tmp_path, contents: str | None, expected_status: str
) -> None:
    report_path = tmp_path / "latest.json"
    if contents is not None:
        report_path.write_text(contents, encoding="utf-8")

    provenance = build_evaluation_provenance(report_path, "CT")

    assert provenance["status"] == expected_status
    assert provenance["course_case_count"] == 0
    assert provenance["raw_results_included"] is False


def test_evaluation_provenance_marks_course_not_covered(tmp_path) -> None:
    report_path = tmp_path / "latest.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "mode": "offline",
                "started_at": "2026-08-03T00:00:00+00:00",
                "completed_at": "2026-08-03T00:01:00+00:00",
                "filters": {},
                "summary": {"total": 1},
                "statistics": {"by_course": {"AE": {"total": 1, "passed": 1}}},
                "results": [],
                "estimated_cost": None,
            }
        ),
        encoding="utf-8",
    )

    provenance = build_evaluation_provenance(report_path, "CT")

    assert provenance["status"] == "course_not_covered"
    assert provenance["consistency"]["status"] == "inconsistent"
    assert "summary_total_mismatch" in provenance["consistency"]["issues"]


def test_evaluation_provenance_checks_filter_hash_and_catalog_scope(
    tmp_path,
) -> None:
    result = EvaluationResult(
        case_id="CASE_001",
        status="passed",
        route_passed=True,
        course_passed=True,
        agent_passed=True,
        structure_passed=True,
        execution_path_passed=True,
        tools_passed=True,
        answer_passed=True,
        citations_passed=True,
        safety_passed=True,
        total_score=100,
        expected={"course": "CT"},
    )
    report = SuiteReport(
        mode="offline",
        started_at="2026-08-03T00:00:00+00:00",
        completed_at="2026-08-03T00:01:00+00:00",
        filters={"mode": "offline"},
        summary={
            "total": 1,
            "passed": 1,
            "failed": 0,
            "errors": 0,
            "timeouts": 0,
            "cached": 0,
        },
        statistics={"by_course": {"CT": {"total": 1, "passed": 1, "pass_rate": 1.0}}},
        results=[result],
        run_metadata=EvaluationRunMetadata(
            run_id="eval_run_test",
            case_count=1,
            case_ids_sha256="wrong-case-hash",
            case_catalog_sha256="catalog-test",
            case_catalog_content_sha256="content-test",
            case_catalog_content_version="canonical_evaluation_case_payloads.v1",
            case_source_files_sha256="source-test",
            case_source_files_version="evaluation_case_source_files.v1",
            case_attachment_manifest_sha256="attachment-test",
            case_attachment_manifest_version="evaluation_case_attachments.v1",
            case_attachment_count=0,
            filters_sha256="wrong-filter-hash",
            implementation_fingerprint="fingerprint-test",
        ),
    )
    report_path = tmp_path / "latest.json"
    report_path.write_text(report.model_dump_json(), encoding="utf-8")

    provenance = build_evaluation_provenance(report_path, "CT")

    assert provenance["status"] == "available"
    assert provenance["case_catalog_sha256"] == "catalog-test"
    assert provenance["consistency"]["status"] == "inconsistent"
    assert provenance["consistency"]["metadata_filters_match"] is False
    assert provenance["consistency"]["case_catalog_present"] is True
    assert provenance["consistency"]["case_catalog_content_present"] is True
    assert provenance["consistency"]["case_source_files_present"] is True
    assert provenance["consistency"]["case_attachment_manifest_present"] is True
    assert "metadata_filters_hash_mismatch" in provenance["consistency"]["issues"]


def test_attach_evaluation_provenance_maps_evidence_gaps() -> None:
    result = attach_evaluation_provenance_readiness(
        {"status": "ready", "blockers": [], "next_actions": []},
        {"status": "report_missing", "run_metadata_present": False},
    )

    assert result["status"] == "evidence_pending"
    assert result["blockers"] == [
        {
            "code": "evaluation_provenance_report_missing",
            "severity": "medium",
            "message": (
                "No validated offline evaluation report is available for this "
                "readiness snapshot."
            ),
        }
    ]
    assert result["next_actions"] == ["restore_or_generate_offline_evaluation_report"]


def test_attach_evaluation_provenance_maps_inconsistent_report() -> None:
    result = attach_evaluation_provenance_readiness(
        {"status": "ready", "blockers": [], "next_actions": []},
        {
            "status": "available",
            "run_metadata_present": True,
            "consistency": {"status": "inconsistent"},
        },
    )

    assert result["status"] == "evidence_pending"
    assert result["blockers"] == [
        {
            "code": "evaluation_provenance_inconsistent",
            "severity": "high",
            "message": (
                "Evaluation report summary, course statistics, or run metadata "
                "are internally inconsistent."
            ),
        }
    ]
    assert result["next_actions"] == [
        "inspect_and_regenerate_inconsistent_evaluation_report"
    ]


def test_attach_evaluation_provenance_maps_missing_attachment_manifest() -> None:
    result = attach_evaluation_provenance_readiness(
        {"status": "ready", "blockers": [], "next_actions": []},
        {
            "status": "available",
            "run_metadata_present": True,
            "consistency": {
                "status": "partial",
                "case_attachment_manifest_present": False,
            },
        },
    )

    assert result["status"] == "evidence_pending"
    assert result["blockers"][0]["code"] == "evaluation_provenance_scope_incomplete"
    assert result["next_actions"] == [
        "regenerate_evaluation_report_with_attachment_manifest"
    ]


@pytest.mark.parametrize("course_id", ["CT", "AE"])
def test_ocr_quality_summary_is_read_only_and_page_aware(
    client, course_id: str
) -> None:
    response = client.get(
        "/api/v1/knowledge/ocr-quality-summary",
        params={"course_id": course_id},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["schema_version"] == "ocr_quality_summary.v1"
    assert payload["course_id"] == course_id
    assert payload["mode"] == "read_only_text_layer_audit"
    assert payload["runtime_loaded"] is False
    assert payload["ocr_execution_performed"] is False
    assert payload["decision_evidence"]["status"] == "decision_file_missing"
    assert payload["decision_evidence"]["pending_count"] == len(payload["rows"])
    assert payload["summary"]["candidate_document_count"] == len(payload["rows"])
    assert payload["summary"]["candidate_page_count"] >= 0
    assert all("ocr_candidate_pages" in row for row in payload["rows"])


def test_ocr_quality_summary_rejects_non_knowledge_course(client) -> None:
    response = client.get(
        "/api/v1/knowledge/ocr-quality-summary",
        params={"course_id": "UNKNOWN"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported course_id"
