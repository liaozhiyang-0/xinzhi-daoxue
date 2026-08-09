def test_task_state_transition_events(api, client) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    api.wait_for_task(task["id"])
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
            "debug_agent_id": "SOLVER_CT_V1",
        },
        user_role="admin",
    )
    failed = api.wait_for_task(task["id"])
    assert failed["status"] == "failed"
    assert failed["error_message"] == "Mock Provider 按请求触发失败"
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    assert events[-1]["event_type"] == "task.failed"


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
    second_response = client.post("/api/v1/tasks", json=second_payload)
    assert second_response.status_code == 202, second_response.text
    second = api.wait_for_task(second_response.json()["id"])

    assert second["agent_id"] == "GENERAL_QUESTION_V1"
    assert second["course_id"] == "UNKNOWN"
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
