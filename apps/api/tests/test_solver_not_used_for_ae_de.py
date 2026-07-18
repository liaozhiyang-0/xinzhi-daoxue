import pytest
from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, RouteStatus


@pytest.mark.parametrize("course_id", ["AE", "DE"])
def test_solver_is_not_used_as_fallback_for_ae_de(course_id: str) -> None:
    request = AgentRequest(
        session_id="session-route",
        user_id="user-route",
        course_id=course_id,
        intent="solve_problem",
        canonical_input={"question": "求解"},
    )

    decision = TaskRouter(AgentRegistry()).route(request)

    assert decision.route_status == RouteStatus.UNRESOLVED
    assert decision.agent_id == "UNRESOLVED"
