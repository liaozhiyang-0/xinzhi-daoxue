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


def test_scenario_catalog_endpoint_returns_detail(client: TestClient) -> None:
    response = client.get("/api/v1/scenarios/research_data_workbench_v1")

    assert response.status_code == 200
    assert response.json()["agent_id"] == "RESEARCH_03_DATA_ANALYSIS_V1"
