def test_execution_debug_uses_persisted_task_summary_and_redacts(api, client) -> None:
    session = api.create_session()
    created = api.create_task(session["id"])
    task = api.wait_for_task(created["id"])
    assert task["status"] == "completed"

    response = client.get(f"/api/v1/debug/execution/{task['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["task"]["id"] == task["id"]
    assert data["overview"]["title"]
    assert data["retrieval"]["rag_mode"] in {
        "grounded_generation",
        "method_reference",
        "reference_only",
        "no_rag",
    }
    assert data["performance"]["waterfall"]
    serialized = response.text.casefold()
    assert "authorization" not in serialized
    assert "api_secret" not in serialized
