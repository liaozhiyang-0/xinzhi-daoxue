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


@pytest.mark.parametrize("course_id", ["CT", "AE", "DE", "SS", "DSP", "COMM"])
@pytest.mark.parametrize("intent", ["general_qa", "explain_concept"])
def test_learning_routes_to_local_knowledge_agent(course_id: str, intent: str) -> None:
    decision = TaskRouter(AgentRegistry()).route(request(course_id, intent))

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == "LEARN_01_LOCAL_RETRIEVAL_V1"
    assert decision.retrieval_required is True
    assert decision.provider_required is False
    assert decision.route_source == "local_fast"
    assert decision.original_agent_id is None
    assert decision.fallback_used is False


def test_ct_solve_routes_to_solver() -> None:
    decision = TaskRouter(AgentRegistry()).route(request("CT", "solve_problem"))

    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert decision.provider_required is False


def test_dynamic_circuit_state_variables_do_not_route_to_data_analysis() -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-dynamic-circuit",
            "user_id": "user-dynamic-circuit",
            "scene": "dispatch",
            "course_id": "CT",
            "intent": "unknown",
            "canonical_input": {
                "text": (
                    "含受控源的二阶动态电路，以v(t)和iL(t)为状态变量，"
                    "求换路初始条件，建立状态方程和二阶微分方程，求完整响应、"
                    "自然频率、阻尼类型、第一次经过零点的时刻并验证能量平衡。"
                )
            },
            "options": {"allow_cloud": False},
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.route_status == RouteStatus.SELECTED
    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert decision.intent == "solve_problem"
    assert decision.provider_required is False
    assert "domain_contract:dynamic_circuit_problem" in decision.reason_codes
    data_candidate = next(
        item
        for item in decision.candidate_agents
        if item.agent_id == "RESEARCH_03_DATA_ANALYSIS_V1"
    )
    assert data_candidate.score == 0.0
