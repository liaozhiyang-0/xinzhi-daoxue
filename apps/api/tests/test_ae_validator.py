from __future__ import annotations

import pytest
from app.contracts.solver import (
    AcademicProblem,
    AcademicSolutionResult,
    SolverFinalAnswer,
)
from app.services.ae_validator import AEValidator


def _result(answer: str) -> AcademicSolutionResult:
    return AcademicSolutionResult(
        status="success",
        course="AE",
        problem_summary="structured AE validation",
        final_answer=answer,
        confidence=0.8,
    )


@pytest.mark.parametrize(
    ("problem", "answer", "conflict_type"),
    [
        (
            AcademicProblem(
                course="AE",
                problem_type="diode_circuit",
                problem_text="Check diode operating region.",
                known_conditions=[{"name": "v_d", "value": -0.2}],
            ),
            "The diode is forward conducting.",
            "diode_operating_region",
        ),
        (
            AcademicProblem(
                course="AE",
                problem_type="bjt_bias",
                problem_text="Check the BJT Q point.",
                known_conditions=[
                    {"name": "v_be", "value": 0.7},
                    {"name": "v_ce", "value": -1.0},
                ],
            ),
            "The BJT operates in the active region.",
            "q_point_region_mismatch",
        ),
        (
            AcademicProblem(
                course="AE",
                problem_type="feedback",
                problem_text="Classify the feedback polarity.",
                known_conditions=[{"name": "feedback", "value": "negative"}],
            ),
            "This is positive feedback.",
            "feedback_polarity",
        ),
    ],
)
def test_structured_ae_conditions_report_local_conflicts(
    problem: AcademicProblem,
    answer: str,
    conflict_type: str,
) -> None:
    validation = AEValidator().validate(problem, _result(answer))

    assert not validation.valid
    assert conflict_type in {item.conflict_type for item in validation.conflicts}
    assert validation.affected_steps == ["final_answer"]
    assert not validation.requires_regeneration


def test_structured_ae_conditions_allow_consistent_answers() -> None:
    problem = AcademicProblem(
        course="AE",
        problem_type="diode_circuit",
        problem_text="Check diode operating region.",
        known_conditions=[{"name": "v_d", "value": 0.7}],
    )

    validation = AEValidator().validate(
        problem,
        _result("The diode is forward conducting."),
    )

    assert validation.valid
    assert validation.conflicts == []


@pytest.mark.parametrize("problem_type", ["diode_circuit", "bjt_bias", "mos_bias"])
def test_ae_problem_types_have_explicit_analysis_modes(problem_type: str) -> None:
    problem = AcademicProblem(
        course="AE",
        problem_type=problem_type,
        problem_text="structured problem",
    )

    assert AEValidator.analysis_mode(problem) == problem_type


def test_small_signal_requires_verified_bias_when_status_is_explicit() -> None:
    problem = AcademicProblem(
        course="AE",
        problem_type="small_signal_amplifier",
        problem_text="Derive the small-signal voltage gain.",
        known_conditions=[{"name": "q_point_status", "value": "pending"}],
    )

    validation = AEValidator().validate(
        problem,
        _result("Use the small-signal model to obtain the gain."),
    )

    assert not validation.valid
    assert {item.conflict_type for item in validation.conflicts} == {
        "small_signal_prerequisite_missing"
    }


def test_small_signal_allows_verified_bias_and_checks_structured_units() -> None:
    problem = AcademicProblem(
        course="AE",
        problem_type="small_signal_amplifier",
        problem_text="Derive the voltage gain.",
        known_conditions=[{"name": "q_point_status", "value": "verified"}],
        target_quantities=[{"name": "A_v", "unit": "V/V"}],
    )
    result = _result("The small-signal voltage gain is 2 V.").model_copy(
        update={"final_answer_detail": SolverFinalAnswer(value="2", unit="V")}
    )

    validation = AEValidator().validate(problem, result)

    assert not validation.valid
    assert {item.conflict_type for item in validation.conflicts} == {"unit_consistency"}


def test_frequency_response_normalizes_units_and_rejects_invalid_passband_claim() -> (
    None
):
    problem = AcademicProblem(
        course="AE",
        problem_type="frequency_response",
        problem_text="Is the 20 kHz signal in the midband?",
        known_conditions=[
            {"name": "f_l", "value": 100, "unit": "Hz"},
            {"name": "f_h", "value": 10, "unit": "kHz"},
            {"name": "frequency", "value": 20, "unit": "kHz"},
        ],
    )

    validation = AEValidator().validate(
        problem,
        _result("The signal is in the midband."),
    )

    assert not validation.valid
    assert {item.conflict_type for item in validation.conflicts} == {"frequency_region"}


def test_frequency_response_rejects_reversed_cutoffs_without_units_assumption():
    problem = AcademicProblem(
        course="AE",
        problem_type="frequency_response",
        problem_text="Find the bandwidth.",
        known_conditions=[
            {"name": "f_l", "value": 10, "unit": "kHz"},
            {"name": "f_h", "value": 100, "unit": "Hz"},
        ],
    )

    validation = AEValidator().validate(
        problem,
        _result("The bandwidth is not determined."),
    )

    assert not validation.valid
    assert {item.conflict_type for item in validation.conflicts} == {"frequency_range"}


def test_small_signal_without_structured_prerequisite_is_not_rejected() -> None:
    problem = AcademicProblem(
        course="AE",
        problem_type="small_signal_amplifier",
        problem_text="Derive the small-signal gain from the supplied circuit.",
    )

    validation = AEValidator().validate(
        problem,
        _result("The small-signal gain is 2."),
    )

    assert validation.valid


def test_frequency_response_does_not_assume_missing_frequency_units() -> None:
    problem = AcademicProblem(
        course="AE",
        problem_type="frequency_response",
        problem_text="Find the bandwidth from the supplied cutoff values.",
        known_conditions=[
            {"name": "f_l", "value": 100},
            {"name": "f_h", "value": 10},
        ],
    )

    validation = AEValidator().validate(
        problem,
        _result("The bandwidth requires an explicit frequency unit."),
    )

    assert validation.valid


def test_structured_gain_polarity_rejects_positive_common_emitter_gain() -> None:
    problem = AcademicProblem(
        course="AE",
        problem_type="small_signal_amplifier",
        problem_text="Find the common-emitter voltage gain.",
        known_conditions=[{"name": "gain_polarity", "value": "negative"}],
    )

    validation = AEValidator().validate(problem, _result("A_v = 25 V/V."))

    assert not validation.valid
    assert {item.conflict_type for item in validation.conflicts} == {"gain_sign"}


def test_structured_gain_polarity_accepts_negative_gain() -> None:
    problem = AcademicProblem(
        course="AE",
        problem_type="bjt_small_signal",
        problem_text="Find the voltage gain.",
        known_conditions=[{"name": "expected_gain_sign", "value": "negative"}],
    )

    validation = AEValidator().validate(problem, _result("A_v = -25 V/V."))

    assert validation.valid


def test_structured_resistance_targets_require_a_unit_when_answer_is_structured() -> (
    None
):
    problem = AcademicProblem(
        course="AE",
        problem_type="small_signal_amplifier",
        problem_text="Find the input and output resistance.",
        target_quantities=[
            {"name": "R_in", "unit": "ohm"},
            {"name": "R_out", "unit": "ohm"},
        ],
    )
    result = _result("R_in=1, R_out=2").model_copy(
        update={"final_answer_detail": SolverFinalAnswer(value="1, 2")}
    )

    validation = AEValidator().validate(problem, result)

    assert not validation.valid
    assert {item.conflict_type for item in validation.conflicts} == {"unit_missing"}


def test_structured_resistance_targets_accept_ohm_dimension() -> None:
    problem = AcademicProblem(
        course="AE",
        problem_type="small_signal_amplifier",
        problem_text="Find the input resistance.",
        target_quantities=[{"name": "R_in", "unit": "ohm"}],
    )
    result = _result("R_in=1 kΩ").model_copy(
        update={"final_answer_detail": SolverFinalAnswer(value="1", unit="kΩ")}
    )

    validation = AEValidator().validate(problem, result)

    assert validation.valid
