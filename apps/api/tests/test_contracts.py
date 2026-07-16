from datetime import datetime

from app.contracts import AgentEvent, AgentEventType, AgentRequest, AgentResult


def test_agent_request_serialization() -> None:
    request = AgentRequest(
        session_id="session-1",
        user_id="user-1",
        canonical_input={"text": "test"},
    )
    payload = request.model_dump(mode="json")
    restored = AgentRequest.model_validate(payload)

    assert restored.task_id == request.task_id
    assert restored.attachments == []
    assert restored.options == {}
    assert payload["intent"] == "solve_problem"


def test_agent_result_serialization() -> None:
    result = AgentResult(agent_id="SOLVER_CT_V1", provider="mock")
    payload = result.model_dump(mode="json")
    restored = AgentResult.model_validate(payload)

    assert restored.provider == "mock"
    assert restored.artifacts == []
    assert restored.metrics == {}


def test_event_timestamp_is_timezone_aware() -> None:
    event = AgentEvent(task_id="task-1", type=AgentEventType.TASK_CREATED)
    assert isinstance(event.timestamp, datetime)
    assert event.timestamp.utcoffset() is not None
