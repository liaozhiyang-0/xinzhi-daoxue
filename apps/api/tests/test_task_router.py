import pytest
from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, RouteStatus


def request(course_id: str, intent: str) -> AgentRequest:
    return AgentRequest.model_validate(
        {
            "session_id": "session-route",
            "user_id": "user-route",
            "scene": "learning",
            "course_id": course_id,
            "intent": intent,
            "canonical_input": {"question": "测试问题"},
        }
    )


@pytest.mark.parametrize("course_id", ["CT", "AE", "DE"])
@pytest.mark.parametrize("intent", ["general_qa", "explain_concept"])
def test_learning_routes_to_local_knowledge_agent(course_id: str, intent: str) -> None:
    decision = TaskRouter(AgentRegistry()).route(request(course_id, intent))

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == "LEARN_01_LOCAL_RETRIEVAL_V1"
    assert decision.retrieval_required is True
    assert decision.provider_required is False
    assert decision.route_source == "local_degraded"
    assert decision.original_agent_id == "LEARN_01_KNOWLEDGE_QA_V1"


def test_ct_solve_routes_to_solver() -> None:
    decision = TaskRouter(AgentRegistry()).route(request("CT", "solve_problem"))

    assert decision.agent_id == "SOLVER_CT_V1"
    assert decision.provider_required is True
