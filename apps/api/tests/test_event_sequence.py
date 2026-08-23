def test_event_sequence_is_unique_and_increasing(api, client) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    api.wait_for_task(task["id"])
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    sequences = [event["sequence"] for event in events]
    assert sequences == list(range(1, len(sequences) + 1))
    assert len(sequences) == len(set(sequences))


def test_task_stream_reconnect_replays_only_events_after_last_event_id(
    api, client
) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    api.wait_for_task(task["id"])
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    assert len(events) >= 2

    last_seen = events[0]["sequence"]
    response = client.get(
        f"/api/v1/tasks/{task['id']}/stream",
        headers={"Last-Event-ID": str(last_seen)},
    )

    assert response.status_code == 200, response.text
    assert f"id: {last_seen}\n" not in response.text
    assert f"id: {events[-1]['sequence']}\n" in response.text
