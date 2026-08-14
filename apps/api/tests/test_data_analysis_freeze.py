from __future__ import annotations

from fastapi.testclient import TestClient


def test_data_analysis_capability_is_explicitly_frozen(client: TestClient) -> None:
    payload = client.get("/api/v1/capabilities")

    assert payload.status_code == 200
    feature = next(
        item for item in payload.json()["workspace_features"]
        if item["id"] == "data_analysis"
    )
    assert feature["available"] is False
    assert feature["frozen"] is True
    assert feature["unavailable_reason"] == "data_analysis_frozen"


def test_frozen_data_analysis_rejects_new_tasks(client: TestClient) -> None:
    session = client.post(
        "/api/v1/sessions",
        json={"user_id": "freeze-test-user", "course_id": "CT", "title": ""},
    )
    assert session.status_code == 201

    response = client.post(
        "/api/v1/tasks",
        json={
            "session_id": session.json()["id"],
            "user_id": "freeze-test-user",
            "user_role": "researcher",
            "scene": "research",
            "course_id": "CT",
            "intent": "data_analysis",
            "canonical_input": {"text": "比较两组结果"},
            "attachments": [],
            "context_refs": [],
            "options": {},
        },
    )

    assert response.status_code == 409
    assert "已冻结" in response.json()["detail"]
