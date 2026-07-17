def test_sse_reconnect_uses_header_before_query(api, client) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    api.wait_for_task(task["id"])
    response = client.get(
        f"/api/v1/tasks/{task['id']}/stream?after=1",
        headers={"Last-Event-ID": "2"},
    )
    ids = [
        int(line.removeprefix("id: "))
        for line in response.text.splitlines()
        if line.startswith("id: ")
    ]
    assert ids
    assert min(ids) == 3
    assert 1 not in ids and 2 not in ids
