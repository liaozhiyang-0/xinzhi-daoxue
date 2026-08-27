import asyncio

from app.models import AgentRunModel
from sqlalchemy import select


def test_task_state_transition_events(api, app, client) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    completed = api.wait_for_task(task["id"])
    audit = completed["input_content"]["options"]["_audit"]
    assert audit["schema_version"] == "task_audit.v1"
    assert audit["task_id"] == task["id"]
    assert audit["runtime_run_id"]
    assert len(audit["input_sha256"]) == 64
    assert audit["terminal_status"] == "completed"

    async def load_runtime_run() -> AgentRunModel | None:
        async with app.state.session_factory() as db:
            return await db.scalar(
                select(AgentRunModel).where(
                    AgentRunModel.task_id == task["id"],
                    AgentRunModel.run_kind == "runtime",
                )
            )

    runtime_run = asyncio.run(load_runtime_run())
    assert runtime_run is not None
    assert runtime_run.metrics_data["audit"]["runtime_run_id"] == runtime_run.id
    assert runtime_run.metrics_data["audit"]["task_id"] == task["id"]
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    names = [event["event_type"] for event in events]
    assert names[:2] == ["task.created", "route.selected"]
    assert names.index("intent.recognized") < names.index("plan.created")
    assert names.index("plan.created") < names.index("task.queued")
    assert names.index("task.queued") < names.index("task.running")
    assert names.index("task.running") < names.index("agent.started")
    assert "artifact.created" in names
    assert names[-1] == "task.completed"


def test_provider_failure_marks_task_failed(api, client) -> None:
    session = api.create_session()
    task = api.create_task(
        session["id"],
        options={
            "mock_force_failure": True,
            "debug_agent_id": "ACADEMIC_PROBLEM_SOLVER",
        },
        user_role="admin",
    )
    failed = api.wait_for_task(task["id"])
    assert failed["status"] == "failed"
    assert failed["error_message"] == "Mock Provider 按请求触发失败"
    audit = failed["input_content"]["options"]["_audit"]
    assert audit["terminal_status"] == "failed"
    assert audit["failure_category"] == "provider_error"
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    assert events[-1]["event_type"] == "task.failed"
    terminal_data = events[-1]["event_data"]["data"]
    assert terminal_data["terminal_status"] == "failed"
    assert terminal_data["failure_category"] == "provider_error"
    assert terminal_data["error_code"] == "provider_error"
    assert terminal_data["error_message"] == failed["error_message"]
    assert terminal_data["runtime_run_id"] == audit["runtime_run_id"]


def test_follow_up_transfers_context_without_reusing_course_route(api, client) -> None:
    session = api.create_session()
    first_payload = api.task_payload(
        session["id"],
        intent="unknown",
        options={"allow_cloud": False},
    )
    first_payload.update(
        {
            "scene": "dispatch",
            "course_id": "AUTO",
            "canonical_input": {"text": "解释TCP三次握手"},
        }
    )
    first_response = client.post("/api/v1/tasks", json=first_payload)
    assert first_response.status_code == 202, first_response.text
    first = api.wait_for_task(first_response.json()["id"])
    assert first["agent_id"] == "GENERAL_QUESTION_V1"

    second_payload = dict(first_payload)
    second_payload["task_id"] = "follow-up-context-transfer"
    second_payload["canonical_input"] = {
        "text": "那为什么服务器要回复 SYN+ACK？"
    }
    second_payload["options"] = {
        **first_payload["options"],
        "source_task_id": first["id"],
        "learning_action": "follow_up",
    }
    second_response = client.post("/api/v1/tasks", json=second_payload)
    assert second_response.status_code == 202, second_response.text
    second = api.wait_for_task(second_response.json()["id"])

    assert second["agent_id"] == "GENERAL_QUESTION_V1"
    assert second["course_id"] == "UNKNOWN"
    assert second["parent_task_id"] == first["id"]
    events = client.get(f"/api/v1/tasks/{second['id']}/events").json()
    route_event = next(
        item for item in events if item["event_type"] == "route.selected"
    )
    intent_event = next(
        item for item in events if item["event_type"] == "intent.recognized"
    )
    assert route_event["event_data"]["data"]["course_id"] == "UNKNOWN"
    assert intent_event["event_data"]["data"]["intent"] == "general_qa"
    assert "conversation_context" not in second["input_content"]["options"]


def test_follow_up_source_task_cannot_cross_sessions(api, client) -> None:
    first_session = api.create_session()
    first = api.create_task(first_session["id"])
    first = api.wait_for_task(first["id"])
    second_session = api.create_session()
    payload = api.task_payload(
        second_session["id"],
        task_id="cross-session-follow-up",
        intent="unknown",
        options={
            "source_task_id": first["id"],
            "learning_action": "follow_up",
        },
    )

    response = client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 422, response.text
    assert "当前会话" in response.text
