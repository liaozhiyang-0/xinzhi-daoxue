from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, AgentRequestV2, CourseCode, OrchestrationIntent
from app.core.config import Settings
from app.observability import TraceStore
from app.orchestrator import XZDSupervisor


def supervisor() -> XZDSupervisor:
    settings = Settings(app_env="test", rag_enabled=False, _env_file=None)
    registry = AgentRegistry()
    return XZDSupervisor(registry, TaskRouter(registry, settings), TraceStore())


def test_supervisor_routes_ct_solver_without_model_classification() -> None:
    prepared = supervisor().prepare(
        AgentRequestV2(message="已知10Ω电阻接20V电源，求支路电流"),
        session_id="session-1",
        user_id="user-1",
    )

    assert prepared.state["course"] == CourseCode.CT.value
    assert prepared.state["intent"] == OrchestrationIntent.SOLVE_PROBLEM.value
    assert prepared.state["task_family"] == "ACADEMIC_SOLVING"
    assert prepared.route.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert prepared.request.options["trace_id"] == prepared.state["trace_id"]


def test_supervisor_inherits_follow_up_course() -> None:
    prepared = supervisor().prepare(
        AgentRequestV2(message="为什么上一问的电流方向要取负号？"),
        session_id="session-1",
        user_id="user-1",
        session_context={"course_id": "CT", "intent": "solve_problem"},
    )

    assert prepared.state["course"] == CourseCode.CT.value
    assert prepared.state["intent"] == OrchestrationIntent.FOLLOW_UP_QUESTION.value
    assert prepared.route.agent_id == "LEARN_01_LOCAL_RETRIEVAL_V1"
    assert prepared.route.route_source == "supervisor_local_rag_primary"


def test_supervisor_routes_switching_regulator_to_analog_knowledge_base() -> None:
    prepared = supervisor().prepare(
        AgentRequestV2(message="讲解一下开关稳压电路"),
        session_id="session-knowledge",
        user_id="user-knowledge",
    )

    assert prepared.state["course"] == CourseCode.AE.value
    assert prepared.state["intent"] == OrchestrationIntent.EXPLAIN_CONCEPT.value
    assert prepared.route.agent_id == "LEARN_01_LOCAL_RETRIEVAL_V1"
    assert prepared.route.retrieval_required is True
    assert "local_rag_primary" in prepared.route.reason_codes


def test_supervisor_recognizes_general_concept_question() -> None:
    prepared = supervisor().prepare(
        AgentRequestV2(message="什么是戴维宁定理"),
        session_id="session-general-knowledge",
        user_id="user-general-knowledge",
    )

    assert prepared.state["course"] == CourseCode.CT.value
    assert prepared.state["intent"] == OrchestrationIntent.EXPLAIN_CONCEPT.value
    assert prepared.route.agent_id == "LEARN_01_LOCAL_RETRIEVAL_V1"


def test_task_router_recognizes_knowledge_language_without_supervisor() -> None:
    router = TaskRouter(
        AgentRegistry(), Settings(app_env="test", rag_enabled=False, _env_file=None)
    )
    decision = router.route(
        AgentRequest(
            session_id="session-router",
            user_id="user-router",
            course_id="UNKNOWN",
            intent="unknown",
            canonical_input={"text": "讲解一下开关稳压电路"},
        )
    )

    assert decision.agent_id == "LEARN_01_LOCAL_RETRIEVAL_V1"
    assert decision.course_id == CourseCode.AE.value
    assert decision.intent == OrchestrationIntent.EXPLAIN_CONCEPT.value
