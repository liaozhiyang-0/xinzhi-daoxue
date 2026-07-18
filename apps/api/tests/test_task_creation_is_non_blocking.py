from time import perf_counter


def test_task_creation_returns_before_slow_mock_finishes(api, client) -> None:
    session = api.create_session()
    started = perf_counter()
    response = client.post(
        "/api/v1/tasks",
        json=api.task_payload(session["id"], options={"mock_delay_seconds": 1.0}),
    )
    elapsed = perf_counter() - started
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert elapsed < 0.7
    assert api.wait_for_task(response.json()["id"])["status"] == "completed"
