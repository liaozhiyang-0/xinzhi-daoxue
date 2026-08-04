from __future__ import annotations

from app.capabilities import default_capability_registry
from app.contracts import (
    AgentResult,
    AgentResultStatus,
    SolutionPacketV1,
    SolutionStepV1,
    StudentAttempt,
    TeachingMode,
)
from app.courses import default_course_registry
from app.services.answer_disclosure import (
    INTERNAL_TEACHING_KEY,
    AnswerDisclosureService,
    public_teaching_result,
)
from app.services.error_pool import ErrorPoolRegistry
from app.services.hint_policy import HintPolicyService
from app.services.next_check_question import NextCheckQuestionService
from app.services.skill_registry import SkillRegistry
from app.services.student_verification import StudentVerificationService
from app.services.teaching_execution_planner import TeachingExecutionPlanner


def packet(
    *,
    course: str = "CT",
    problem_type: str = "power",
    answer: str = "20 W",
    unit: str = "W",
    skills: list[str] | None = None,
) -> SolutionPacketV1:
    return SolutionPacketV1(
        course_id=course,
        problem_type=problem_type,
        skill_ids=skills or ["CT.AC_POWER"],
        steps=[
            SolutionStepV1(
                step_id="S1",
                title="建立功率关系",
                content="使用 P=UI",
                skill_ids=skills or ["CT.AC_POWER"],
                step_source="solver_execution",
            )
        ],
        final_answer=answer,
        units=[unit] if unit else [],
        mapping_status="mapped",
    )


def hint_service() -> HintPolicyService:
    skills = SkillRegistry(
        default_course_registry(),
        default_capability_registry(),
    )
    return HintPolicyService(ErrorPoolRegistry(), skills)


def test_execution_planner_keeps_direct_and_bounds_guided_check() -> None:
    planner = TeachingExecutionPlanner()
    direct, _ = planner.plan(
        mode=TeachingMode.DIRECT_ANSWER,
        course_id="CT",
        attempt=None,
        reusable_solution_packet=False,
    )
    guided, _ = planner.plan(
        mode=TeachingMode.GUIDED_LEARNING,
        course_id="CT",
        attempt=None,
        reusable_solution_packet=False,
    )
    check, _ = planner.plan(
        mode=TeachingMode.CHECK_MY_WORK,
        course_id="CT",
        attempt=StudentAttempt(raw_text="P=20"),
        reusable_solution_packet=True,
    )
    assert direct.path.value == "direct"
    assert direct.require_student_verification is False
    assert direct.maximum_disclosure_level == "H5"
    assert guided.path.value == "guided"
    assert guided.maximum_disclosure_level == "H2"
    assert guided.model_call_budget == 0
    assert check.path.value == "check"
    assert check.reuse_solution_packet is True
    assert check.require_solver is False


def test_finite_verification_unit_numeric_and_manual_review() -> None:
    verifier = StudentVerificationService()
    unit_report, _ = verifier.verify(
        StudentAttempt(raw_text="P=20"),
        packet(),
    )
    numeric_report, _ = verifier.verify(
        StudentAttempt(raw_text="P=18 W"),
        packet(),
    )
    manual, _ = verifier.verify(
        StudentAttempt(raw_text="我使用了另一种很长的推导。"),
        packet(answer="无法形成确定性数值", unit=""),
    )
    assert unit_report.first_confirmed_error_step == "student-final"
    assert unit_report.step_results[0].error_type.value == "unit_missing"
    assert numeric_report.step_results[0].error_type.value == "numeric_error"
    assert manual.overall_status == "manual_review"
    assert manual.first_confirmed_error_step is None
    assert manual.manual_review_required is True


def test_finite_ct_rule_evidence_covers_direction_units_and_initial_condition() -> None:
    verifier = StudentVerificationService()

    direction_report, _ = verifier.verify(
        StudentAttempt(raw_text="P=-20 W"),
        packet(),
    )
    incompatible_report, _ = verifier.verify(
        StudentAttempt(raw_text="P=20 V"),
        packet(),
    )
    initial_condition_report, _ = verifier.verify(
        StudentAttempt(raw_text="电容电压可以突变"),
        packet(
            problem_type="first_order",
            answer="v_C(0+)=v_C(0-)",
            unit="",
            skills=["CT.FIRST_ORDER_INITIAL"],
        ),
    )

    assert direction_report.step_results[0].repair_hint_key == (
        "reference_direction_error"
    )
    assert incompatible_report.step_results[0].error_type.value == "unit_incompatible"
    assert initial_condition_report.step_results[0].repair_hint_key == (
        "capacitor_voltage_continuity"
    )


def test_finite_course_rules_cover_ae_and_de_without_fuzzy_first_error() -> None:
    verifier = StudentVerificationService()
    ae_report, _ = verifier.verify(
        StudentAttempt(raw_text="由虚短和虚断可得输出"),
        packet(
            course="AE",
            problem_type="op_amp",
            answer="在线性负反馈理想运放条件下求解",
            unit="",
            skills=["AE.IDEAL_OP_AMP"],
        ),
    )
    de_report, _ = verifier.verify(
        StudentAttempt(raw_text="两个输入不同时，异或输出为1"),
        packet(
            course="DE",
            problem_type="logic_simplification",
            answer="同或在两个输入相同时输出为1",
            unit="",
            skills=["DE.BOOLEAN"],
        ),
    )
    assert ae_report.step_results[0].repair_hint_key == "op_amp_assumption_missing"
    assert de_report.step_results[0].repair_hint_key == "xnor_xor_confusion"


def test_hint_policy_uses_reviewed_template_and_stops_at_h2() -> None:
    verifier = StudentVerificationService()
    report, _ = verifier.verify(StudentAttempt(raw_text="P=20"), packet())
    hints = hint_service()
    first, _ = hints.decide(
        mode=TeachingMode.CHECK_MY_WORK,
        packet=packet(),
        report=report,
        hint_request_count=0,
    )
    more, _ = hints.decide(
        mode=TeachingMode.CHECK_MY_WORK,
        packet=packet(),
        report=report,
        hint_request_count=1,
    )
    assert first.hint_level == "H1"
    assert first.source == "CT.unit_missing.H1"
    assert more.hint_level == "H2"
    assert more.source == "CT.unit_missing.H2"


def test_disclosure_filters_answer_packet_and_internal_key_from_public_api() -> None:
    disclosure = AnswerDisclosureService()
    full_packet = packet()
    result = AgentResult(
        status=AgentResultStatus.COMPLETED,
        agent_id="ACADEMIC_PROBLEM_SOLVER",
        provider="local",
        answer="最终答案是 20 W",
        structured_result={
            "final_answer": "20 W",
            "solution_steps": [{"content": "P=UI=20 W"}],
            "solution_packet": full_packet.model_dump(mode="json"),
        },
    )
    hint, _ = hint_service().decide(
        mode=TeachingMode.GUIDED_LEARNING,
        packet=full_packet,
        report=None,
        hint_request_count=0,
    )
    question = NextCheckQuestionService().generate(
        task_id="task",
        packet=full_packet,
        hint=hint,
    )
    filtered, _ = disclosure.apply(
        result,
        policy=disclosure.policy(TeachingMode.GUIDED_LEARNING),
        hint=hint,
        next_check=question,
        verification=None,
    )
    assert "20 W" not in filtered.answer
    assert filtered.structured_result["solution_packet"]["final_answer"] is None
    assert "final_answer" not in filtered.structured_result
    assert INTERNAL_TEACHING_KEY in filtered.structured_result
    public = public_teaching_result(
        {"structured_result": filtered.structured_result}
    )
    assert public is not None
    assert INTERNAL_TEACHING_KEY not in public["structured_result"]
