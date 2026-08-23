def test_debug_page_exposes_rag_controls(client) -> None:
    response = client.get("/debug/rag")

    assert response.status_code == 200
    assert 'id="debug-question"' in response.text
    assert 'data-tab-target="context"' in response.text


def test_local_knowledge_qa_runs_through_unified_task_api(api, client) -> None:
    session = api.create_session()
    payload = api.task_payload(session["id"])
    payload.update(
        {
            "scene": "learning",
            "course_id": "CT",
            "intent": "general_qa",
            "canonical_input": {"question": "什么是戴维南定理"},
        }
    )
    response = client.post("/api/v1/tasks", json=payload)
    task = api.wait_for_task(response.json()["id"])

    assert task["status"] == "completed"
    assert task["agent_id"] == "LEARN_01_KNOWLEDGE_QA_V1"
    assert task["result_content"]["provider"] == "local"
    assert task["result_content"]["cloud_status"] == "not_required"
    assert task["result_content"]["structured_result"]["mode"] == "local_model"
