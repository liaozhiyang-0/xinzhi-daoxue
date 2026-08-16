def test_background_runtime_persists_result_and_artifact(api) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    completed = api.wait_for_task(task["id"])
    assert completed["result_content"]["provider"] == "local_graph"
    assert completed["result_content"]["metrics"]["latency_ms"] is not None
    assert completed["artifact_ids"]
