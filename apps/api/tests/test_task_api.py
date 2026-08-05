def test_create_query_and_artifact(api, client) -> None:
    session = api.create_session()
    created = api.create_task(session["id"])
    assert created["status"] == "queued"
    assert created["provider"] == "local_agent"
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


def test_legacy_task_scenario_binds_catalog_agent_and_policy(api) -> None:
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        intent="lesson_prep",
    )
    payload.update(
        {
            "scene": "teaching",
            "scenario_id": "faculty_course_copilot_v1",
            "canonical_input": {"text": "璇峰府鎴戝噯澶囦竴鑺傝"},
        }
    )

    response = api.client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 202, response.text
    created = response.json()
    assert created["agent_id"] == "TEACH_01_LESSON_PREP_V1"
    assert created["route_status"] == "selected"
    assert created["input_content"]["scenario_id"] == "faculty_course_copilot_v1"
    assert (
        created["input_content"]["options"]["_scenario_catalog_bound"] is True
    )
