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
    assert [item["event_type"] for item in events.json()] == [
        "task.created",
        "agent.started",
        "task.completed",
    ]
