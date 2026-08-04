from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.main import create_app
from app.models import SystemSettingModel
from fastapi.testclient import TestClient

from .test_authentication import register


def test_feedback_is_saved_with_task_snapshot_and_can_be_updated(api) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])['id'])

    created = api.client.post(
        "/api/v1/feedback",
        json={
            "task_id": task["id"],
            "resolved": False,
            "satisfaction": "unsatisfied",
            "problem_type": "answer_quality",
            "manual_review_required": True,
            "comment": "needs a teacher review",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["task_id"] == task["id"]
    assert body["course_id"] == "CT"
    assert body["task_type"] == "solve_problem"
    assert body["satisfaction"] == "unsatisfied"
    assert body["manual_review_required"] is True
    assert "user_id" not in body

    updated = api.client.post(
        "/api/v1/feedback",
        json={
            "task_id": task["id"],
            "resolved": True,
            "satisfaction": "satisfied",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == body["id"]
    assert updated.json()["resolved"] is True
    assert updated.json()["satisfaction"] == "satisfied"


def test_feedback_metrics_are_bounded_telemetry(api) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])['id'])
    response = api.client.post(
        "/api/v1/feedback",
        json={
            "task_id": task["id"],
            "resolved": True,
            "satisfaction": "satisfied",
        },
    )
    assert response.status_code == 200, response.text

    metrics = api.client.get(
        "/api/v1/feedback/metrics",
        params={
            "course_id": "CT",
            "window_start": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
            "window_end": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        },
    )
    assert metrics.status_code == 200, metrics.text
    body = metrics.json()
    assert body["feedback_count"] == 1
    assert body["satisfaction_counts"] == {"satisfied": 1}
    assert body["resolved_count"] == 1
    assert body["resolved_rate"] == 1.0
    assert body["task_count"] >= 1
    assert "user_id" not in body


def test_feedback_metrics_require_teacher_or_admin_when_auth_enabled(
    settings: Settings,
) -> None:
    auth_settings = settings.model_copy(
        update={
            "auth_required": True,
            "auth_allow_registration": True,
            "auth_scrypt_n_log2": 14,
        }
    )
    app = create_app(auth_settings)
    with TestClient(app) as client:
        register(client, login="feedback-student@example.com")
        response = client.get("/api/v1/feedback/metrics")
    assert response.status_code == 403


def test_feedback_rejects_non_terminal_task(api) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    response = api.client.post(
        "/api/v1/feedback", json={"task_id": task["id"], "satisfaction": "neutral"}
    )
    assert response.status_code == 409


def test_feedback_loop_switch_blocks_submission_and_metrics(api) -> None:
    async def disable_feature() -> None:
        async with api.client.app.state.session_factory() as db:
            db.add(
                SystemSettingModel(
                    key="feedback_loop",
                    value={"enabled": False},
                    updated_by="test",
                )
            )
            await db.commit()

    asyncio.run(disable_feature())
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])['id'])
    response = api.client.post(
        "/api/v1/feedback", json={"task_id": task["id"], "satisfaction": "neutral"}
    )
    assert response.status_code == 409
    assert api.client.get("/api/v1/feedback/metrics").status_code == 409
