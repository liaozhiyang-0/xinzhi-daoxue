from app.contracts.solver import SolverResult
from app.courses import default_course_registry
from app.services.solver_quality_gate import SolverQualityGateService


def test_high_risk_result_without_verification_is_not_accepted_as_success() -> None:
    result = SolverResult(
        status="success",
        course="CT",
        problem_summary="含受控源的二阶电路",
        final_answer="v(t)=...",
        solution_steps=[{"stage": "solve"}],
        execution_path="HIGH_RISK",
        confidence=0.8,
    )
    checked = SolverQualityGateService().evaluate(
        result, default_course_registry().get("CT")
    )
    assert checked.status == "partial"
    assert checked.quality_gate and checked.quality_gate.status == "fail"
    assert "HIGH_RISK 未通过确定性校验" in checked.quality_gate.blocked_reasons


def test_course_specific_rules_are_visible_in_gate_result() -> None:
    result = SolverResult(
        status="partial",
        course="DE",
        problem_summary="状态机",
        final_answer="需要检查状态转移",
        solution_steps=[{"stage": "structure"}],
        confidence=0.5,
    )
    checked = SolverQualityGateService().evaluate(
        result, default_course_registry().get("DE")
    )
    assert checked.quality_gate
    assert "logic_equivalence" in checked.quality_gate.applied_course_rules
