def test_sse_returns_standard_events(api, client) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    api.wait_for_task(task["id"])
    with client.stream("GET", f"/api/v1/tasks/{task['id']}/stream") as response:
        content = "".join(response.iter_text())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: task.created" in content
    assert "event: task.completed" in content
    assert "id: 1" in content
