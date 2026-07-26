from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequestV2, CourseCode, OrchestrationIntent
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
