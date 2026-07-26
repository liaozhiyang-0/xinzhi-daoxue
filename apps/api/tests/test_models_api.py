def test_models_api_reports_unconfigured_without_live_calls(client) -> None:
    response = client.get("/api/v1/models")
    health = client.get("/api/v1/models/health?live=false")

    assert response.status_code == 200
    assert len(response.json()["models"]) == 4
    assert {item["configured"] for item in response.json()["models"]} == {False}
    assert health.status_code == 200
    assert health.json()["live"] is False
    assert {item["error_type"] for item in health.json()["providers"]} == {
        "unconfigured"
    }
