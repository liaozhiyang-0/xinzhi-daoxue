from __future__ import annotations

from pathlib import Path

from scripts.audit_readiness_consistency import (
    _boundary_report,
    build_consistency_report,
)

ROOT = Path(__file__).resolve().parents[3]


def test_readiness_consistency_audit_matches_static_and_runtime_views() -> None:
    report = build_consistency_report(ROOT)

    assert report["schema_version"] == "course_asset_readiness_consistency.v1"
    assert report["read_only"] is True
    assert report["status"] == "consistent"
    assert report["errors"] == []
    assert report["contest_boundary"]["status"] == "consistent"
    for course in ("CT", "AE"):
        details = report["courses"][course]
        assert details["status"] == "consistent"
        assert details["errors"] == []
        assert details["runtime_eligible_candidate_count"] == 0


def test_readiness_consistency_audit_detects_boundary_drift() -> None:
    static_boundary = {
        "package_status": "draft_evidence_only",
        "official_rules_verified": False,
        "official_score_claims_allowed": False,
        "demo_cases_included": False,
        "real_user_outcomes_included": False,
        "real_provider_results_included": False,
    }
    runtime_boundary = dict(static_boundary)
    runtime_boundary["demo_cases_included"] = True

    report = _boundary_report(static_boundary, runtime_boundary)

    assert report["status"] == "review"
    assert report["errors"] == [
        "demo_cases_included:static=False:runtime=True"
    ]
