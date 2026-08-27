from datetime import UTC

from app.contracts import (
    AgentEvent,
    AgentEventType,
    AgentRequest,
    AgentResult,
    RunMetrics,
)


def test_agent_request_and_result_serialization() -> None:
    request = AgentRequest(session_id="session-1", user_id="user-1")
    restored_request = AgentRequest.model_validate(request.model_dump(mode="json"))
    assert restored_request.attachments == []

    result = AgentResult(
        agent_id="ACADEMIC_PROBLEM_SOLVER",
        provider="mock",
        metrics=RunMetrics(latency_ms=10),
    )
    restored_result = AgentResult.model_validate(result.model_dump(mode="json"))
    assert restored_result.provider == "mock"
    assert restored_result.metrics.latency_ms == 10


def test_event_timestamp_is_timezone_aware() -> None:
    event = AgentEvent(
        task_id="task-1",
        sequence=1,
        type=AgentEventType.TASK_CREATED,
    )
    assert event.timestamp.tzinfo == UTC
