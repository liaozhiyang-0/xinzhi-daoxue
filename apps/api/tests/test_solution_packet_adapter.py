from __future__ import annotations

from app.capabilities import default_capability_registry
from app.contracts import StudentAttempt
from app.courses import default_course_registry
from app.services.skill_registry import SkillRegistry
from app.services.solution_packet_adapter import SolutionPacketAdapterService
from app.services.student_verification import StudentVerificationService


def adapter() -> SolutionPacketAdapterService:
    return SolutionPacketAdapterService(
        SkillRegistry(default_course_registry(), default_capability_registry())
    )


def test_old_solver_result_adapts_without_changing_execution_step_semantics() -> None:
    packet, mapping = adapter().from_structured_result(
        {
            "status": "success",
            "course": "CT",
            "problem_type": "node_voltage",
            "problem_summary": "使用节点电压法",
            "known_conditions": [{"name": "R", "value": 5, "unit": "Ω"}],
            "target_quantities": [{"name": "U", "unit": "V"}],
            "solution_steps": [
                {"stage": "structure", "status": "ready"},
                {
                    "stage": "capability_selection",
                    "items": ["circuit_analysis"],
                },
            ],
            "final_answer": "U=2 V",
            "confidence": 0.8,
        },
        course_id="CT",
    )
    assert packet is not None
    assert packet.skill_ids[0] == "CT.NODAL"
    assert mapping.status == "mapped"
    assert [item.step_id for item in packet.steps] == ["S1", "S2"]
    assert {item.step_source for item in packet.steps} == {"solver_execution"}
    assert any("not pedagogical" in item for item in packet.warnings)


def test_unknown_problem_does_not_fabricate_skill() -> None:
    packet, mapping = adapter().from_structured_result(
        {
            "status": "partial",
            "course": "CT",
            "problem_type": "unknown",
            "problem_summary": "未知题型",
            "final_answer": "",
        },
        course_id="CT",
    )
    assert packet is not None
    assert mapping.status == "partial"
    assert packet.skill_ids == []


def test_completed_model_answer_replaces_stale_detail_and_infers_target_unit() -> None:
    packet, _ = adapter().from_structured_result(
        {
            "status": "success",
            "course": "CT",
            "problem_type": "general",
            "problem_summary": (
                "一个 2Ω 电阻两端电压为 10V，电流参考方向与电压参考方向"
                "满足关联参考方向。求电流 I。"
            ),
            "final_answer": "由欧姆定律 I=U/R=10 V/2 Ω=5 A。",
            "final_answer_detail": {
                "value": "没有足够方程形成确定性结果",
                "unit": None,
            },
            "model_execution": {"status": "completed"},
        },
        course_id="CT",
    )

    assert packet is not None
    assert packet.final_answer == "由欧姆定律 I=U/R=10 V/2 Ω=5 A。"
    assert packet.units == ["A"]

    report, _ = StudentVerificationService().verify(
        StudentAttempt(raw_text="根据欧姆定律，I=U/R=10/2=5。"),
        packet,
    )
    assert report.overall_status == "verified_incorrect"
    assert report.step_results[0].error_type.value == "unit_missing"
