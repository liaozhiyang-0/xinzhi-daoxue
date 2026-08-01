from __future__ import annotations

from pathlib import Path

from app.evaluation.loader import EvaluationCaseLoader

ROOT = Path(__file__).resolve().parents[3]


def test_phase3_cases_are_synthetic_non_official_and_cover_dimensions() -> None:
    cases = EvaluationCaseLoader(
        ROOT / "evaluation" / "cases" / "teaching_loop_phase3"
    ).load_all()
    assert [case.case_id for case in cases] == [
        f"TP3-{index:02d}" for index in range(1, 8)
    ]
    assert all(case.provenance.source_type == "synthetic" for case in cases)
    assert all(case.official_scoring is False for case in cases)
    dimensions = {
        case.evidence_requirements["evaluation_dimension"] for case in cases
    }
    assert dimensions == {
        "attempt_version_integrity",
        "feedback_uptake_capture",
        "mastery_evidence_consistency",
        "full_solution_dependency_handling",
        "retest_plan_correctness",
        "manual_review_safety",
        "cross_user_isolation",
    }
