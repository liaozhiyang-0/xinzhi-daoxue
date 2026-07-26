from __future__ import annotations

import json
from pathlib import Path

from app.evaluation.loader import EvaluationCaseLoader


def _case(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "title": "synthetic case",
        "course": "CT",
        "task_family": "ACADEMIC_SOLVING",
        "intent": "solve_problem",
        "message": "10V 与 5Ω 串联，求电流",
        "expected_agent": "ACADEMIC_PROBLEM_SOLVER",
        "reference_solution": {"final_answer": "2 A"},
        "judge_type": "rule",
        "provenance": {
            "source_type": "synthetic",
            "source_name": "unit_test",
            "publishable": True,
        },
    }


def test_loader_accepts_yaml_collections_and_single_json_cases(tmp_path: Path) -> None:
    (tmp_path / "case.json").write_text(
        json.dumps(_case("JSON_001"), ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "case.yaml").write_text(
        "cases:\n  - case_id: YAML_001\n    title: synthetic case\n"
        "    course: CT\n    task_family: ACADEMIC_SOLVING\n"
        "    intent: solve_problem\n    message: test\n"
        "    expected_agent: ACADEMIC_PROBLEM_SOLVER\n",
        encoding="utf-8",
    )
    cases = EvaluationCaseLoader(tmp_path).load_all()
    assert [item.case_id for item in cases] == ["JSON_001", "YAML_001"]
    assert cases[0].provenance.source_type == "synthetic"
    assert cases[0].rubric.reasoning == 1


def test_repository_synthetic_suites_validate() -> None:
    root = Path(__file__).resolve().parents[3] / "evaluation" / "cases"
    cases = [
        *EvaluationCaseLoader(root / "learning_loop").load_all(),
        *EvaluationCaseLoader(root / "task_reliability").load_all(),
    ]
    ids = {item.case_id for item in cases}
    assert "SYN_LEARN_CT_001" in ids
    assert "SYN_RELIABILITY_001" in ids
    assert all(item.provenance.source_type for item in cases)
