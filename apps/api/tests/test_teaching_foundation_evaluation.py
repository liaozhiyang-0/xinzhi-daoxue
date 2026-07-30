from __future__ import annotations

from pathlib import Path

from app.evaluation.loader import EvaluationCaseLoader
from app.evaluation.scorers import EvaluationScorer
from app.tools import default_tool_registry


def test_phase1_synthetic_cases_are_non_official_and_complete() -> None:
    root = Path("evaluation/cases/teaching_foundation")
    cases = EvaluationCaseLoader(root).load_all()
    assert len(cases) == 15
    assert {item.case_id for item in cases} == {
        f"TF{index:02d}_{suffix}"
        for index, suffix in (
            (1, "LEGACY_DEFAULT_MODE"),
            (2, "TEXT_STUDENT_ATTEMPT"),
            (3, "CHECK_MY_WORK_CONTEXT"),
            (4, "CT_SKILL_MAPPING"),
            (5, "AE_SKILL_MAPPING"),
            (6, "DE_SKILL_MAPPING"),
            (7, "UNKNOWN_SKILL"),
            (8, "SOLUTION_PACKET_COMPAT"),
            (9, "EXECUTION_STEP_SOURCE"),
            (10, "EVIDENCE_PAGE_NULL"),
            (11, "UNAVAILABLE_COURSE_EVIDENCE"),
            (12, "ERROR_POOL_EXACT"),
            (13, "ERROR_POOL_NO_FUZZY_MATCH"),
            (14, "MEMORY_BOUNDARY"),
            (15, "MASTERY_BOUNDARY"),
        )
    }
    assert all(item.provenance.source_type == "synthetic" for item in cases)
    assert all(item.official_scoring is False for item in cases)


def test_teaching_dimension_scores_contract_without_second_runner() -> None:
    case = EvaluationCaseLoader(
        Path("evaluation/cases/teaching_foundation")
    ).load_all()[3]
    result = EvaluationScorer(default_tool_registry()).score(
        case,
        {
            "task_status": "completed",
            "task_families": ["ACADEMIC_SOLVING"],
            "intent": "solve_problem",
            "course": "CT",
            "agent_id": "ACADEMIC_PROBLEM_SOLVER",
            "course_pack": "CT",
            "execution_path": "STANDARD",
            "status": "success",
            "answer": "U=2 V",
            "structured_result": {
                "problem_summary": "节点电压",
                "course": "CT",
            },
            "solution_packet_valid": True,
            "skill_mapping_valid": True,
            "skill_ids": ["CT.NODAL"],
        },
        elapsed_ms=1,
        model_calls=[],
        trace_id="trace-teaching",
    )
    assert result.status == "passed"
    assert result.dimension_scores["teaching_foundation"] == 100
