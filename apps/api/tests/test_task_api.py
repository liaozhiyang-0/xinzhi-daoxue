def test_create_query_and_artifact(api, client) -> None:
    session = api.create_session()
    created = api.create_task(session["id"])
    assert created["status"] == "queued"
    task = api.wait_for_task(created["id"])
    assert task["status"] == "completed"
    assert task["provider"] == "local_graph"
    assert len(task["artifact_ids"]) == 1

    artifact = client.get(f"/api/v1/artifacts/{task['artifact_ids'][0]}")
    assert artifact.status_code == 200
    assert artifact.json()["content"]["execution_source"] == (
        "academic_problem_solver_graph"
    )
    assert artifact.json()["content"]["academic_solution"]["course"] == "CT"

    history = client.get(f"/api/v1/sessions/{session['id']}/tasks")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [task["id"]]
    assert history.json()[0]["question"] == "求电阻两端电压"
    assert history.json()[0]["answer"]
    assert "result_content" not in history.json()[0]
