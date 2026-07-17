def create_session(client, session_payload) -> str:
    response = client.post("/api/v1/sessions", json=session_payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_create_and_query_mock_task(
    client, session_payload, agent_request_payload
) -> None:
    session_id = create_session(client, session_payload)
    request_payload = {**agent_request_payload, "session_id": session_id}

    created = client.post("/api/v1/tasks", json=request_payload)
    assert created.status_code == 201
    task = created.json()
    assert task["status"] == "completed"
    assert task["provider"] == "mock"
    assert len(task["artifact_ids"]) == 1

    queried = client.get(f"/api/v1/tasks/{task['id']}")
    assert queried.status_code == 200
    assert queried.json()["result_content"]["provider"] == "mock"

    artifact = client.get(f"/api/v1/artifacts/{task['artifact_ids'][0]}")
    assert artifact.status_code == 200
    assert artifact.json()["content"]["provider"] == "mock"

    events = client.get(f"/api/v1/tasks/{task['id']}/events")
    assert events.status_code == 200
    event_types = [item["event_type"] for item in events.json()]
    assert event_types[0] == "task.created"
    assert event_types[-1] == "task.completed"
    assert {
        "input.validated",
        "session.context_loaded",
        "route.local_selected",
        "agent.started",
        "provider.request_started",
        "provider.request_completed",
        "result.normalized",
    } <= set(event_types)


def test_debug_page_displays_runtime_fields(client) -> None:
    response = client.get("/debug/")
    script = client.get("/debug/app.js")

    assert response.status_code == 200
    assert script.status_code == 200
    assert "本地总控调试页" in response.text
    assert "目标 Agent" in script.text
    assert "缓存命中" in script.text
