from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import Settings
from app.main import create_app
from app.observability.model_tracer import ModelCallRecord
from fastapi.testclient import TestClient

from .test_authentication import register


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
        assert response.json()["case_count"] >= 73
        assert response.json()["execution_via_http"] is False
        assert client.post("/api/v1/evaluation/run").status_code == 404


def test_evaluation_summary_excludes_case_results(settings: Settings) -> None:
    app = create_app(settings.model_copy(update={"enable_evaluation_api": True}))
    with TestClient(app) as client:
        response = client.get("/api/v1/evaluation/reports/latest/summary")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["report_kind"] == "summary"
    assert body["raw_results_included"] is False
    assert "results" not in body
    assert body["run_metadata"]["case_count"] == 0
    assert body["run_metadata"]["raw_prompts_stored"] is False


def test_model_call_observability_returns_bounded_metadata(settings: Settings) -> None:
    app = create_app(settings.model_copy(update={"enable_evaluation_api": True}))
    with TestClient(app) as client:
        app.state.model_tracer.record(
            ModelCallRecord(
                trace_id="trace-test",
                provider="mock",
                model="mock-model",
                task_type="evaluation",
                start_time=datetime.now(UTC),
                elapsed_ms=25,
                status="completed",
                retry_count=0,
                fallback_used=False,
            )
        )
        response = client.get("/api/v1/evaluation/observability/model-calls")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["retained_record_count"] == 1
    assert body["provider_counts"] == {"mock": 1}
    assert body["model_counts"] == {"mock-model": 1}
    assert body["total_elapsed_ms"] == 25
    assert body["raw_prompts_stored"] is False
    assert "metadata_only_no_prompt_or_reasoning" in body["warnings"]


def test_evaluation_api_requires_teacher_or_admin_when_auth_enabled(
    settings: Settings,
) -> None:
    auth_settings = settings.model_copy(
        update={
            "enable_evaluation_api": True,
            "auth_required": True,
            "auth_allow_registration": True,
            "auth_scrypt_n_log2": 14,
        }
    )
    app = create_app(auth_settings)
    with TestClient(app) as client:
        register(client, login="evaluation-student@example.com")
        response = client.get("/api/v1/evaluation/reports/latest/summary")

    assert response.status_code == 403
