def test_sse_returns_standard_events(
    client, session_payload, agent_request_payload
) -> None:
    session_id = client.post("/api/v1/sessions", json=session_payload).json()["id"]
    task = client.post(
        "/api/v1/tasks",
        json={**agent_request_payload, "session_id": session_id},
    ).json()

    with client.stream("GET", f"/api/v1/tasks/{task['id']}/stream") as response:
        content = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: task.created" in content
    assert "event: agent.started" in content
    assert "event: task.completed" in content
    assert "data: " in content
