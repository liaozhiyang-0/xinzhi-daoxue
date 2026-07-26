from app.contracts import (
    AgentRequestV2,
    CourseCode,
    OrchestrationIntent,
)
from app.orchestrator.state import new_graph_state


def test_v2_request_normalizes_message_and_state_ids() -> None:
    request = AgentRequestV2(message="  为什么   电容电压不能突变？ ")
    state = new_graph_state(request_id=request.request_id, message=request.message)

    assert request.message == "为什么 电容电压不能突变？"
    assert state["course"] == CourseCode.UNKNOWN.value
    assert state["intent"] == OrchestrationIntent.UNKNOWN.value
    assert state["route_status"] == "skipped"
    assert state["trace_id"].startswith("trace_")
    assert state["run_id"].startswith("run_")


def test_supported_course_and_intent_codes_are_complete() -> None:
    assert {"CT", "AE", "DE", "SS", "DSP", "COMM", "RF", "EM"} <= {
        item.value for item in CourseCode
    }
    assert {"solve_problem", "follow_up_question", "data_analysis", "fallback"} <= {
        item.value for item in OrchestrationIntent
    }
