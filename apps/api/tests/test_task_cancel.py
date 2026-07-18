def test_queued_task_can_be_cancelled(api, client, monkeypatch) -> None:
    monkeypatch.setattr(client.app.state.task_runner, "submit", lambda task_id: True)
    session = api.create_session()
    task = api.create_task(session["id"])
    response = client.post(f"/api/v1/tasks/{task['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_running_mock_task_can_be_cancelled(api, client) -> None:
    session = api.create_session()
    task = api.create_task(session["id"], options={"mock_delay_seconds": 1.0})
    api.wait_for_task(task["id"], statuses={"running"})
    response = client.post(f"/api/v1/tasks/{task['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["cancellation_requested"] is True
    assert api.wait_for_task(task["id"])["status"] == "cancelled"


def test_completed_task_cannot_be_cancelled(api, client) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])["id"])
    response = client.post(f"/api/v1/tasks/{task['id']}/cancel")
    assert response.status_code == 409
