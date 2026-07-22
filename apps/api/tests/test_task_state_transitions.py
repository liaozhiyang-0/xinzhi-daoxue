def test_task_state_transition_events(api, client) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    api.wait_for_task(task["id"])
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    names = [event["event_type"] for event in events]
    assert names[:5] == [
        "task.created",
        "route.selected",
        "task.queued",
        "task.running",
        "agent.started",
    ]
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
