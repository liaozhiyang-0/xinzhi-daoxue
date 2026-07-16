def test_create_query_and_artifact(api, client) -> None:
    session = api.create_session()
    created = api.create_task(session["id"])
    assert created["status"] == "queued"
    task = api.wait_for_task(created["id"])
    assert task["status"] == "completed"
    assert task["provider"] == "mock"
    assert len(task["artifact_ids"]) == 1

    artifact = client.get(f"/api/v1/artifacts/{task['artifact_ids'][0]}")
    assert artifact.status_code == 200
    assert artifact.json()["content"]["provider"] == "mock"
