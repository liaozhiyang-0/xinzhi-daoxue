import pytest
from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, RouteStatus


@pytest.mark.parametrize("course_id", ["AE", "DE"])
def test_ae_de_use_universal_solver_not_ct_cloud_baseline(course_id: str) -> None:
    request = AgentRequest(
        session_id="session-route",
        user_id="user-route",
        course_id=course_id,
        intent="solve_problem",
        canonical_input={"question": "求解"},
    )

    decision = TaskRouter(AgentRegistry()).route(request)

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"


def test_ct_uses_universal_solver() -> None:
    request = AgentRequest(
        session_id="session-route",
        user_id="user-route",
        course_id="CT",
        intent="solve_problem",
        canonical_input={"question": "求解"},
    )

    decision = TaskRouter(AgentRegistry()).route(request)

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
