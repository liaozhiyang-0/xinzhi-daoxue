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


def test_bound_scenario_selects_declared_agent_before_keyword_routing() -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-scenario",
            "user_id": "user-scenario",
            "scene": "teaching",
            "course_id": "CT",
            "intent": "lesson_prep",
            "canonical_input": {"text": "璇峰府鎴戝噯澶囦竴鑺傝"},
            "options": {
                "scenario_id": "faculty_course_copilot_v1",
                "scenario_agent_id": "TEACH_01_LESSON_PREP_V1",
                "_scenario_catalog_bound": True,
            },
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "TEACH_01_LESSON_PREP_V1"
    assert decision.route_source == "scenario_catalog"
    assert "scenario_catalog_bound" in decision.reason_codes


def test_latest_paper_request_routes_to_dedicated_academic_search() -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-paper-search",
            "user_id": "user-paper-search",
            "scene": "research",
            "course_id": "CT",
            "intent": "unknown",
            "canonical_input": {
                "text": "帮我查找最新的电子信息领域相关论文，并提供链接和摘要"
            },
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert decision.reason_codes[-1] == "academic_search_request"
    assert decision.provider_required is False


def test_writing_request_stays_on_academic_writing_agent() -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-paper-writing",
            "user_id": "user-paper-writing",
            "scene": "research",
            "course_id": "CT",
            "intent": "unknown",
            "canonical_input": {"text": "请把这段内容改写成论文摘要"},
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "RESEARCH_02_ACADEMIC_WRITING_V1"


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


@pytest.mark.parametrize(
    "text",
    [
        "已知电阻电压 u=10V、电流 i=2A，按关联参考方向求吸收功率。",
        "求端口等效电阻。",
        "判断二极管当前工作状态。",
        "计算放大电路的电压增益。",
        "化简逻辑式并给出真值表。",
        "求离散系统的卷积响应。",
    ],
)
def test_natural_academic_problem_language_routes_to_solver(text: str) -> None:
    task_request = AgentRequest.model_validate(
        {
            "session_id": "session-natural-problem",
            "user_id": "user-natural-problem",
            "scene": "learning",
            "course_id": "CT",
            "intent": "general_qa",
            "canonical_input": {"text": text},
            "options": {"allow_cloud": False},
        }
    )

    decision = TaskRouter(AgentRegistry()).route(task_request)

    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert decision.intent == "solve_problem"
    assert "domain_contract:academic_problem_language" in decision.reason_codes


def test_general_qa_problem_submission_completes_with_solver_answer(
    api, client
) -> None:
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        intent="general_qa",
        options={"allow_cloud": False, "use_local_rag": False},
    )
    payload["canonical_input"] = {
        "text": "已知电阻电压 u=10V、电流 i=2A，按关联参考方向求吸收功率。"
    }

    response = client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 202
    task = api.wait_for_task(response.json()["id"], timeout=15)
    assert task["status"] == "completed"
    assert task["agent_id"] == "ACADEMIC_PROBLEM_SOLVER"
    assert task["intent"] == "solve_problem"
    assert task["result_content"]["answer"].strip()
