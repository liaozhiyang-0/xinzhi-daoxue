def test_failed_task_retry_creates_child_attempt(api, client) -> None:
    session = api.create_session()
    original = api.create_task(session["id"], options={"mock_force_failure": True})
    original = api.wait_for_task(original["id"])
    response = client.post(f"/api/v1/tasks/{original['id']}/retry")
    assert response.status_code == 202
    retried = response.json()
    assert retried["id"] != original["id"]
    assert retried["parent_task_id"] == original["id"]
    assert retried["attempt"] == 2


def test_completed_task_cannot_retry(api, client) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])["id"])
    response = client.post(f"/api/v1/tasks/{task['id']}/retry")
    assert response.status_code == 409
