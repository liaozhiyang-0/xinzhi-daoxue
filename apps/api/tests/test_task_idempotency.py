def test_duplicate_task_id_is_rejected_without_second_run(api, client) -> None:
    session = api.create_session()
    task_id = "task_fixed_idempotency"
    first = client.post(
        "/api/v1/tasks",
        json=api.task_payload(task_id=task_id, session_id=session["id"]),
    )
    second = client.post(
        "/api/v1/tasks",
        json=api.task_payload(task_id=task_id, session_id=session["id"]),
    )
    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"
