def test_event_sequence_is_unique_and_increasing(api, client) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    api.wait_for_task(task["id"])
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    sequences = [event["sequence"] for event in events]
    assert sequences == list(range(1, len(sequences) + 1))
    assert len(sequences) == len(set(sequences))
