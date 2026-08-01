from __future__ import annotations

from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_evaluation_api_is_disabled_by_default(client: TestClient) -> None:
    response = client.get("/api/v1/evaluation/suites")
    assert response.status_code == 404


def test_evaluation_suite_api_is_read_only_and_lists_all_cases(
    settings: Settings,
) -> None:
    app = create_app(settings.model_copy(update={"enable_evaluation_api": True}))
    with TestClient(app) as client:
        response = client.get("/api/v1/evaluation/suites")
        assert response.status_code == 200
        assert response.json()["case_count"] == 73
        assert response.json()["execution_via_http"] is False
        assert client.post("/api/v1/evaluation/run").status_code == 404
