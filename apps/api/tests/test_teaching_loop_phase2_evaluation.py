from __future__ import annotations

from pathlib import Path

from app.evaluation.loader import EvaluationCaseLoader

ROOT = Path(__file__).resolve().parents[3]


def test_phase2_case_set_is_complete_synthetic_and_non_official() -> None:
    cases = EvaluationCaseLoader(
        ROOT / "evaluation" / "cases" / "teaching_loop_phase2"
    ).load_all()

    assert [case.case_id for case in cases] == [
        f"TP2-{index:02d}" for index in range(1, 16)
    ]
    assert all(case.provenance.source_type == "synthetic" for case in cases)
    assert all(case.official_scoring is False for case in cases)
    assert all("teaching_loop_phase2" in case.tags for case in cases)


def test_phase2_cases_cover_modes_diagnosis_disclosure_and_state_boundaries() -> None:
    cases = EvaluationCaseLoader(
        ROOT / "evaluation" / "cases" / "teaching_loop_phase2"
    ).load_all()
    by_id = {case.case_id: case for case in cases}

    assert by_id["TP2-01"].no_additional_model_calls is True
    assert by_id["TP2-02"].expected_disclosure_mode == "next_step_only"
    assert by_id["TP2-03"].expected_error_type == "unit_missing"
    assert by_id["TP2-04"].expected_error_type == "numeric_error"
    assert by_id["TP2-09"].requires_manual_review is True
    assert by_id["TP2-10"].expected_hint_level == "H2"
    assert by_id["TP2-11"].solution_packet_reused is True
    assert by_id["TP2-13"].full_solution_disclosed is False
    assert by_id["TP2-15"].cross_user_isolated is True
