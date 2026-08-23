from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .test_admin_management import promote_to_admin
from .test_authentication import register


@pytest.fixture
def analytics_auth_client(settings: Settings) -> Iterator[TestClient]:
    app: FastAPI = create_app(
        settings.model_copy(
            update={"auth_required": True, "auth_allow_registration": True}
        )
    )
    with TestClient(app) as client:
        yield client


def test_analytics_endpoints_require_admin(analytics_auth_client: TestClient) -> None:
    response = analytics_auth_client.get("/api/v1/analytics/overview")

    assert response.status_code == 401


def test_admin_analytics_reports_use_bounded_read_model(
    analytics_auth_client: TestClient,
) -> None:
    account = register(analytics_auth_client, login="analytics-admin@example.com")
    promote_to_admin(analytics_auth_client, account["account"]["id"])

    for kind in (
        "overview",
        "users",
        "sessions",
        "tasks",
        "answers",
        "agentic",
        "performance",
        "courses",
    ):
        response = analytics_auth_client.get(
            f"/api/v1/analytics/{kind}",
            params={
                "row_limit": 100,
                "role": "student",
                "course": "CT",
                "intent": "solve_problem",
                "capability": "academic_solver",
                "skill": "verification",
                "tool": "calculator",
                "scenario": "AC-01",
                "provider": "mock",
                "model": "test-model",
                "pilot_batch": "pilot-test",
                "task_id": "missing-task",
                "timezone": "Not/AZone",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["version"] == "v1"
        assert body["row_limit"] == 100
        assert "definitions" in body
        assert "input_content" not in response.text
        assert body["filters"]["task_id"] == "missing-task"
        assert (
            "analytics_timezone_invalid_fallback_utc"
            in body["data_quality_warnings"]
        )

    teacher = analytics_auth_client.get(
        "/api/v1/analytics/teacher", params={"row_limit": 100}
    )
    assert teacher.status_code == 200, teacher.text
    assert teacher.json()["data_source"] == "local_database"

    register(analytics_auth_client, login="analytics-student@example.com")
    student_response = analytics_auth_client.get("/api/v1/analytics/overview")
    assert student_response.status_code == 403
