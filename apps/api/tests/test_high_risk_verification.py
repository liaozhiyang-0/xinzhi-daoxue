from __future__ import annotations

from app.capabilities import default_capability_registry
from app.contracts.solver import (
    AcademicProblem,
    AcademicSolutionResult,
    SolutionPatch,
    ToolResult,
)
from app.courses import default_course_registry
from app.orchestrator.graphs import AcademicProblemSolverGraph
from app.services.high_risk_verification import HighRiskVerificationService
from app.tools import default_tool_registry


def result() -> AcademicSolutionResult:
    return AcademicSolutionResult(
        status="partial",
        course="CT",
        problem_type="controlled_source",
        problem_summary="受控源问题",
        final_answer="保留主答案",
        confidence=0.8,
        execution_path="HIGH_RISK",
    )


def test_source_direction_conflict_builds_machine_readable_report() -> None:
    report = HighRiskVerificationService().verify(
        AcademicProblem(
            course="CT",
            problem_text="受控源",
            source_conflicts=[{"description": "参考方向不一致"}],
        ),
        result(),
        [],
    )
    assert report.verification_status == "conflict"
    assert report.issues[0].issue_type == "direction"
    assert report.requires_patch is True
    assert report.requires_fallback is True


def test_failed_tool_creates_tool_conflict_and_failed_report() -> None:
    report = HighRiskVerificationService().verify(
        AcademicProblem(course="CT", problem_text="求解"),
        result(),
        [ToolResult(tool_id="sympy_solver", status="failed")],
    )
    assert report.verification_status == "failed"
    assert report.issues[0].issue_type == "tool_conflict"
    assert report.issues[0].deterministic is True


def test_no_deterministic_evidence_is_marked_uncertain() -> None:
    report = HighRiskVerificationService().verify(
        AcademicProblem(course="CT", problem_text="求解"), result(), []
    )
    assert report.verification_status == "uncertain"
    assert report.issues[0].issue_type == "evidence"


def test_patch_application_preserves_answer_and_records_sections() -> None:
    service = HighRiskVerificationService()
    report = service.verify(
        AcademicProblem(
            course="CT",
            problem_text="受控源",
            source_conflicts=[{"description": "方向冲突"}],
        ),
        result(),
        [],
    )
    patched = service.apply_patches(result(), service.patches_for(report), report)
    assert patched.final_answer.startswith("保留主答案")
    assert "不确定性标记" in patched.final_answer
    assert patched.patch_count == 1
    assert patched.patched_sections == ["final_answer"]
    assert patched.remaining_issues


def test_full_answer_replace_patch_is_refused() -> None:
    service = HighRiskVerificationService()
    report = service.verify(
        AcademicProblem(course="CT", problem_text="求解"), result(), []
    )
    patch = SolutionPatch(
        target_section="final_answer",
        operation="replace",
        new_content="整份新答案",
        reason="invalid",
        verification_issue_ids=[report.issues[0].issue_id],
    )
    patched = service.apply_patches(result(), [patch], report)
    assert patched.final_answer == "保留主答案"
    assert any("拒绝使用replace/remove" in item for item in patched.remaining_risks)


def test_secondary_model_opinion_remains_non_deterministic_evidence() -> None:
    service = HighRiskVerificationService()
    report = service.verify(
        AcademicProblem(course="CT", problem_text="求解"), result(), []
    )
    merged = service.merge_secondary_review(report, "可能存在符号方向问题")
    assert merged.issues[-1].location == "secondary_model_review"
    assert merged.issues[-1].deterministic is False
    assert "不作为确定性事实" in merged.issues[-1].correction_instruction


def test_high_risk_graph_returns_report_and_local_patch() -> None:
    graph = AcademicProblemSolverGraph(
        default_course_registry(),
        default_capability_registry(),
        default_tool_registry(),
    )
    solved = graph.run(
        AcademicProblem(
            course="CT",
            problem_text="分析受控源冲突",
            source_conflicts=[{"description": "受控源方向冲突"}],
            extraction_confidence=0.4,
        )
    )
    assert solved.execution_path == "HIGH_RISK"
    assert solved.verification_report is not None
    assert solved.verification_report.verification_status == "conflict"
    assert solved.patch_count == 1
