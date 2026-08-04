from __future__ import annotations

import pytest
from app.capabilities import default_capability_registry
from app.contracts.solver import AcademicProblem, AcademicSolutionResult
from app.courses import default_course_registry
from app.orchestrator.graphs import AcademicProblemSolverGraph
from app.services.academic_solver_service import AcademicProblemSolverService
from app.services.ct_validator import CTValidator
from app.tools import default_tool_registry


def _result() -> AcademicSolutionResult:
    return AcademicSolutionResult(
        status="success",
        course="CT",
        problem_summary="structured CT validation",
        final_answer="已完成结构化校验",
        confidence=0.8,
    )


@pytest.mark.parametrize(
    ("relation", "conflict_type"),
    [
        (
            {
                "rule": "kcl_kvl_consistency",
                "law": "KCL",
                "candidate_lhs": 2.0,
                "candidate_rhs": 1.0,
            },
            "kcl_kvl_consistency",
        ),
        (
            {
                "rule": "power_energy_balance",
                "supplied_power": 10.0,
                "absorbed_power": 8.0,
            },
            "power_energy_balance",
        ),
    ],
)
def test_structured_ct_balance_conflicts_are_deterministic(
    relation: dict[str, object], conflict_type: str
) -> None:
    validation = CTValidator().validate(
        AcademicProblem(
            course="CT",
            problem_type="kcl_kvl" if "candidate_lhs" in relation else "power",
            problem_text="structured CT relation",
            relations=[relation],
        ),
        _result(),
    )

    assert not validation.valid
    assert conflict_type in {item.conflict_type for item in validation.conflicts}
    assert validation.affected_steps == ["structured_relation"]
    assert validation.requires_regeneration is False


@pytest.mark.parametrize(
    "relation",
    [
        {
            "rule": "equivalent_resistance_error",
            "candidate_resistance": 8.0,
            "reference_resistance": 10.0,
        },
        {
            "rule": "kcl_sign_error",
            "candidate_lhs": 2.0,
            "candidate_rhs": 1.0,
        },
        {
            "rule": "phase_sign_error",
            "candidate_phase_degrees": -30.0,
            "reference_phase_degrees": 30.0,
        },
        {"rule": "power_factor_error", "power_factor": 1.2},
    ],
)
def test_structured_ct_candidate_signatures_have_finite_checks(
    relation: dict[str, object],
) -> None:
    validation = CTValidator().validate(
        AcademicProblem(
            course="CT",
            problem_text="structured candidate error",
            relations=[relation],
        ),
        _result(),
    )

    assert validation.valid is False
    assert validation.conflicts[0].conflict_type == str(relation["rule"])


def test_structured_ct_candidate_signatures_accept_consistent_values() -> None:
    validation = CTValidator().validate(
        AcademicProblem(
            course="CT",
            problem_text="structured candidate values",
            relations=[
                {
                    "rule": "equivalent_resistance_error",
                    "candidate_resistance": 10.0,
                    "reference_resistance": 10.0,
                },
                {
                    "rule": "kcl_sign_error",
                    "candidate_lhs": 1.0,
                    "candidate_rhs": 1.0,
                },
                {
                    "rule": "phase_sign_error",
                    "candidate_phase_degrees": 390.0,
                    "reference_phase_degrees": 30.0,
                },
                {"rule": "power_factor_error", "power_factor": -1.0},
            ],
        ),
        _result(),
    )

    assert validation.valid
    assert validation.conflicts == []


def test_structured_ct_balances_accept_tolerance_and_generated_power() -> None:
    validation = CTValidator().validate(
        AcademicProblem(
            course="CT",
            problem_type="power",
            problem_text="structured CT balance",
            relations=[
                {
                    "rule": "kcl_kvl_consistency",
                    "law": "KVL",
                    "candidate_lhs": 5.0,
                    "candidate_rhs": 5.0000001,
                    "tolerance": 1e-6,
                },
                {
                    "rule": "power_energy_balance",
                    "supplied_power": 8.0,
                    "generated_power": 2.0,
                    "absorbed_power": 10.0,
                },
            ],
        ),
        _result(),
    )

    assert validation.valid
    assert validation.conflicts == []


def test_ct_validator_skips_unstructured_or_non_ct_input() -> None:
    validator = CTValidator()
    missing_fields = validator.validate(
        AcademicProblem(
            course="CT",
            problem_text="自然语言中提到 KCL，但没有结构化数值",
            relations=[{"rule": "kcl_kvl_consistency", "law": "KCL"}],
        ),
        _result(),
    )
    non_ct = validator.validate(
        AcademicProblem(
            course="AE",
            problem_text="same relation",
            relations=[
                {
                    "rule": "power_energy_balance",
                    "supplied_power": 10.0,
                    "absorbed_power": 8.0,
                }
            ],
        ),
        _result(),
    )

    assert missing_fields.valid
    assert missing_fields.conflicts == []
    assert non_ct.valid
    assert non_ct.conflicts == []


def test_academic_solver_service_mounts_ct_validator() -> None:
    service = AcademicProblemSolverService(
        AcademicProblemSolverGraph(
            default_course_registry(),
            default_capability_registry(),
            default_tool_registry(),
        )
    )
    validation = service._professional_validation(
        AcademicProblem(
            course="CT",
            problem_type="power",
            problem_text="structured CT balance",
            relations=[
                {
                    "rule": "power_energy_balance",
                    "supplied_power": 10.0,
                    "absorbed_power": 9.0,
                }
            ],
        ),
        _result(),
    )

    assert validation.validator == "ct_deterministic_v1"
    assert validation.valid is False
