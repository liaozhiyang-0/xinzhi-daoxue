from fastapi.testclient import TestClient


def test_scenario_catalog_endpoint_lists_and_filters(client: TestClient) -> None:
    response = client.get(
        "/api/v1/scenarios", params={"course": "CT", "role": "teacher"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 5
    assert {item["id"] for item in payload} >= {
        "faculty_course_copilot_v1",
        "assessment_diagnosis_v1",
    }
    assert all(item["evidence_policy"]["manual_review_required"] for item in payload)
    assert all(len(item["demo_cases"]) == 1 for item in payload)
    assert all(len(item["demo_cases"][0]["prompt"]) >= 80 for item in payload)
    assert all(item["demo_cases"][0]["expected_agent"] for item in payload)


def test_frozen_data_analysis_scenario_is_not_exposed(client: TestClient) -> None:
    response = client.get("/api/v1/scenarios/research_data_workbench_v1")

    assert response.status_code == 404


def test_scenario_evidence_review_endpoint_returns_review_state(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/scenarios/faculty_course_copilot_v1/evidence-review",
        json={
            "sources": [
                {
                    "source_type": "course_asset_manifest",
                    "source_ref": "config/course_assets/CT.yaml",
                    "cited": True,
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_manual_review"


def test_chat_submission_returns_bound_scenario_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "生成课程设计",
            "course_hint": "CT",
            "scenario_id": "faculty_course_copilot_v1",
        },
    )

    assert response.status_code == 202
    assert response.json()["scenario_id"] == "faculty_course_copilot_v1"


def test_scenario_preflight_exposes_demo_and_production_readiness(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/scenarios/faculty_course_copilot_v1/preflight")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario_id"] == "faculty_course_copilot_v1"
    assert payload["demo_ready"] == (
        not payload["blockers"]
        and (payload["runtime_available"] or payload["mock_available"])
    )
    assert payload["commercialization_complete"] is True
    assert payload["evidence_review_required"] is True


def test_scenario_readiness_endpoint_batches_all_scenarios(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/scenarios/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 5
    assert {item["scenario_id"] for item in payload} >= {
        "faculty_course_copilot_v1",
    }
    assert all(item["evidence_review_required"] for item in payload)


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
