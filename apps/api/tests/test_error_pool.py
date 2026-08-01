from __future__ import annotations

from app.services.error_pool import ErrorPoolRegistry


def test_reviewed_exact_error_matches_hint_template() -> None:
    result = ErrorPoolRegistry().lookup(
        course_id="CT",
        problem_type="node_voltage",
        skill_ids=["CT.NODAL"],
        error_signature="unit_missing",
    )
    assert result.status == "matched"
    assert result.hint_templates["H1"].startswith("检查")
    assert result.hint_template_ids["H1"] == "CT.unit_missing.H1"


def test_unknown_or_wrong_skill_error_does_not_fuzzy_match() -> None:
    registry = ErrorPoolRegistry()
    assert (
        registry.lookup(
            course_id="CT",
            problem_type="node_voltage",
            skill_ids=["CT.NODAL"],
            error_signature="ambiguous_method",
        ).status
        == "no_match"
    )
    assert (
        registry.lookup(
            course_id="AE",
            problem_type="op_amp",
            skill_ids=["AE.Q_POINT"],
            error_signature="op_amp_assumption_missing",
        ).status
        == "no_match"
    )
