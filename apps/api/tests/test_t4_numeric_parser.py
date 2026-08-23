from __future__ import annotations

import pytest
from app.capabilities import default_capability_registry
from app.contracts.solver import AcademicProblem
from app.courses import default_course_registry
from app.orchestrator.graphs import AcademicProblemSolverGraph
from app.tools import default_tool_registry


def graph() -> AcademicProblemSolverGraph:
    return AcademicProblemSolverGraph(
        default_course_registry(),
        default_capability_registry(),
        default_tool_registry(),
    )


@pytest.mark.parametrize(
    ("course", "problem_text", "problem_type", "target", "expected"),
    [
        (
            "AE",
            "理想反相运放输入电阻2kΩ、反馈电阻10kΩ、输入1V，求输出。",
            "op_amp",
            "vo",
            "-5",
        ),
        (
            "CT",
            "已知电阻电压u=10V、电流i=2A，按关联参考方向求吸收功率。",
            "power",
            "P",
            "20",
        ),
        (
            "DE",
            "将二进制1011转换为十进制，并写出位权展开",
            "number_encoding",
            "value",
            "11",
        ),
    ],
)
def test_unambiguous_numeric_text_is_structured_for_deterministic_solver(
    course: str,
    problem_text: str,
    problem_type: str,
    target: str,
    expected: str,
) -> None:
    result = graph().run(AcademicProblem(course=course, problem_text=problem_text))

    assert result.status == "success"
    assert result.problem_type == problem_type
    expected_target = {"name": target}
    if target == "vo":
        expected_target["unit"] = "V"
    elif target == "P":
        expected_target["unit"] = "W"
    assert result.target_quantities == [expected_target]
    assert result.key_equations
    assert expected in result.final_answer
    assert result.tool_verification[0]["status"] == "success"
