from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from app.services.course_asset_review import (
    build_error_pool_review_document,
    build_teacher_review_queue,
    write_error_pool_review_document,
)
from app.services.error_pool import ErrorPoolRegistry
from app.services.error_pool_promotion import (
    build_error_pool_promotion_plan,
    execute_error_pool_promotion,
    rollback_error_pool_promotion,
)

from scripts.audit_course_assets import build_report


def _copy_config(tmp_path: Path) -> Path:
    project_root = Path(__file__).resolve().parents[3]
    shutil.copytree(project_root / "config", tmp_path / "config")
    return tmp_path


def test_pending_ct_promotion_is_read_only_and_blocked() -> None:
    root = Path(__file__).resolve().parents[3]
    runtime_path = root / "config" / "error_pool" / "CT.yaml"
    before = runtime_path.read_bytes()

    report = build_error_pool_promotion_plan(root, "CT")

    assert report["status"] == "blocked"
    assert report["ready"] is False
    assert any(item["code"] == "review_pending" for item in report["blockers"])
    assert report["review_evidence_ready_count"] == 0
    assert len(report["review_evidence_not_ready_proposal_ids"]) == 4
    assert all(
        item["evidence_present"] is False for item in report["review_evidence_summary"]
    )
    assert all(
        item["deterministic_evidence_scope"] == "structured_fields_only"
        for item in report["review_evidence_summary"]
    )
    assert all(
        item["deterministic_validator_id"] == "ct_deterministic_v1"
        for item in report["review_evidence_summary"]
    )
    assert runtime_path.read_bytes() == before
    assert not (root / "config" / "error_pool" / "releases" / "CT.yaml").exists()


def test_approved_ct_promotion_is_atomic_audited_and_rollback_safe(
    tmp_path: Path,
) -> None:
    root = _copy_config(tmp_path)
    queue = build_teacher_review_queue(root, "CT")
    review_document = build_error_pool_review_document(
        queue,
        "CT",
        [
            {
                "proposal_id": item["proposal_id"],
                "decision": "approved",
                "evidence_refs": [f"teacher-material/CT/{item['proposal_id']}.md#1"],
                "notes": "Checked against the course material and problem type.",
            }
            for item in queue["items"]
        ],
        source_fingerprint=queue["source_fingerprint"],
        reviewer="teacher-test",
        reviewed_at="2026-08-04T00:00:00+00:00",
    )
    write_error_pool_review_document(
        root / "config" / "error_pool" / "reviews" / "CT.yaml",
        review_document,
    )

    plan = build_error_pool_promotion_plan(root, "CT")
    assert plan["status"] == "ready"
    assert plan["candidate_count"] == 4
    assert plan["review_evidence_ready_count"] == 4
    assert plan["review_evidence_not_ready_proposal_ids"] == []
    assert all(item["ready_for_promotion"] for item in plan["review_evidence_summary"])
    assert all(
        item["evidence_quality"] == "traceable"
        for item in plan["review_evidence_summary"]
    )
    assert not (root / "config" / "error_pool" / "releases" / "CT.yaml").exists()

    before = (root / "config" / "error_pool" / "CT.yaml").read_bytes()
    applied = execute_error_pool_promotion(
        root,
        "CT",
        expected_source_fingerprint=plan["source_fingerprint"],
    )
    assert applied["status"] == "applied"
    backup_path = root / applied["backup_path"]
    assert backup_path.is_file()
    assert (root / "config" / "error_pool" / "releases" / "CT.yaml").is_file()
    repeat_plan = build_error_pool_promotion_plan(root, "CT")
    assert repeat_plan["status"] == "already_current"
    repeat_execute = execute_error_pool_promotion(root, "CT")
    assert repeat_execute["status"] == "already_current"

    registry = ErrorPoolRegistry(root / "config" / "error_pool")
    for item in queue["items"]:
        result = registry.lookup(
            course_id="CT",
            problem_type=item["problem_types"][0],
            skill_ids=item["skill_ids"],
            error_signature=item["error_signature"],
        )
        assert result.status == "matched"

    after = (root / "config" / "error_pool" / "CT.yaml").read_bytes()
    current_fingerprint = hashlib.sha256(after).hexdigest()
    queue_after = build_teacher_review_queue(root, "CT")
    assert queue_after["item_count"] == 0
    assert queue_after["proposal_schema_errors"] == []
    audit = build_report(root, ["CT"])["courses"]["CT"]
    assert audit["teacher_review_record_schema_errors"] == []
    assert audit["teacher_review_queue"]["item_count"] == 0
    assert audit["error_signature_coverage_ratio"] == 1.0

    rolled_back = rollback_error_pool_promotion(
        root,
        "CT",
        backup_path,
        expected_current_fingerprint=current_fingerprint,
    )
    assert rolled_back["status"] == "rolled_back"
    assert (root / "config" / "error_pool" / "CT.yaml").read_bytes() == before
    restored_queue = build_teacher_review_queue(root, "CT")
    assert restored_queue["item_count"] == 4


def test_promotion_blocks_manually_written_untraceable_evidence(tmp_path: Path) -> None:
    root = _copy_config(tmp_path)
    queue = build_teacher_review_queue(root, "CT")
    decisions = [
        {
            "proposal_id": item["proposal_id"],
            "decision": "approved",
            "reviewer": "teacher-test",
            "reviewed_at": "2026-08-04T00:00:00+00:00",
            "evidence_refs": ["teacher-review"],
            "notes": "Manually written invalid reference for boundary testing.",
        }
        for item in queue["items"]
    ]
    write_error_pool_review_document(
        root / "config" / "error_pool" / "reviews" / "CT.yaml",
        {
            "schema_version": "error_pool_review.v1",
            "course_id": "CT",
            "source_fingerprint": queue["source_fingerprint"],
            "runtime_loaded": False,
            "review_status": "teacher_review_complete",
            "reviewer": "teacher-test",
            "reviewed_at": "2026-08-04T00:00:00+00:00",
            "decisions": decisions,
        },
    )

    plan = build_error_pool_promotion_plan(root, "CT")

    assert plan["status"] == "blocked"
    assert any(item["code"] == "review_record_invalid" for item in plan["blockers"])
    assert all(
        item["evidence_quality"] == "untraceable"
        for item in plan["review_evidence_summary"]
    )
