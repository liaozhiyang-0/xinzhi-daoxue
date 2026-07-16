def test_sse_ids_follow_database_sequence(api, client) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    api.wait_for_task(task["id"])
    content = client.get(f"/api/v1/tasks/{task['id']}/stream").text
    ids = [
        int(line.removeprefix("id: "))
        for line in content.splitlines()
        if line.startswith("id: ")
    ]
    assert ids == sorted(ids)
    assert ids == list(range(1, len(ids) + 1))
