from fastapi.testclient import TestClient


def test_scenario_catalog_endpoint_lists_and_filters(client: TestClient) -> None:
    response = client.get(
        "/api/v1/scenarios", params={"course": "CT", "role": "teacher"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 6
    assert {item["id"] for item in payload} >= {
        "faculty_course_copilot_v1",
        "assessment_diagnosis_v1",
    }
    assert all(item["evidence_policy"]["manual_review_required"] for item in payload)


def test_scenario_catalog_endpoint_returns_detail(client: TestClient) -> None:
    response = client.get("/api/v1/scenarios/research_data_workbench_v1")

    assert response.status_code == 200
    assert response.json()["agent_id"] == "RESEARCH_03_DATA_ANALYSIS_V1"


def test_chat_rejects_invalid_scenario_before_task_creation(client: TestClient) -> None:
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "生成课程设计",
            "course_hint": "SS",
            "scenario_id": "faculty_course_copilot_v1",
        },
    )

    assert response.status_code == 422
    assert "不支持课程" in response.json()["detail"]
