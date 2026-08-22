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
    ("problem_type", "text"),
    [
        ("bjt_bias", "计算 BJT 静态工作点，并检查晶体管是否工作在放大区"),
        ("mos_bias", "分析 NMOS 静态工作点，判断截止区、线性区或饱和区"),
    ],
)
def test_ae_bias_exposes_pending_operating_region_check(
    problem_type: str, text: str
) -> None:
    result = graph().run(
        AcademicProblem(
            course="AE",
            problem_type=problem_type,
            problem_text=text,
            extraction_confidence=0.9,
        )
    )

    assert result.status == "partial"
    assert any(
        step.get("label") == "工作区判断" for step in result.solution_steps
    )
