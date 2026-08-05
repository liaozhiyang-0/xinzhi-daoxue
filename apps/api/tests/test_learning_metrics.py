from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.main import create_app
from app.models import PracticeAttemptModel, RetestPlanModel
from fastapi.testclient import TestClient

from .test_authentication import register


def test_learning_metrics_aggregates_existing_learning_telemetry(api, app) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])["id"])
    window_start = datetime.now(UTC) - timedelta(minutes=5)
    window_end = datetime.now(UTC) + timedelta(minutes=5)

    async def seed() -> None:
        async with app.state.session_factory() as db:
            db.add_all(
                [
                    PracticeAttemptModel(
                        id="metrics-attempt-1",
                        source_task_id=task["id"],
                        task_id=task["id"],
                        session_id=session["id"],
                        user_id="user-test",
                        course_id="CT",
                        student_answer="P=20 W",
                        final_answer="P=20 W",
                        verification_status="verified_correct",
                        status="verified",
                        feedback_uptake={"status": "applied_correctly"},
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    ),
                    PracticeAttemptModel(
                        id="metrics-attempt-2",
                        source_task_id=task["id"],
                        task_id=task["id"],
                        session_id=session["id"],
                        user_id="user-test",
                        course_id="CT",
                        student_answer="P=18 W",
                        verification_status="manual_review",
                        status="manual_review",
                        feedback_uptake={"status": "indeterminate"},
                        review_result={"decision": "pending"},
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    ),
                    RetestPlanModel(
                        id="metrics-retest-1",
                        user_id="user-test",
                        skill_id="CT.AC_POWER",
                        source_task_id=task["id"],
                        source_attempt_id="metrics-attempt-1",
                        interval_days=3,
                        due_at=datetime.now(UTC) + timedelta(days=3),
                        status="scheduled",
                        reason_code="feedback_not_applied",
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    ),
                ]
            )
            await db.commit()

    asyncio.run(seed())

    response = api.client.get(
        "/api/v1/learning/metrics",
        params={
            "course_id": "CT",
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["course_id"] == "CT"
    assert body["attempt_count"] == 2
    assert body["attempt_status_counts"] == {"verified": 1, "manual_review": 1}
    assert body["verification_status_counts"] == {
        "verified_correct": 1,
        "manual_review": 1,
    }
    assert body["manual_review_count"] == 1
    assert body["feedback_uptake_event_count"] == 2
    assert body["feedback_uptake_status_counts"] == {
        "applied_correctly": 1,
        "indeterminate": 1,
    }
    assert body["feedback_uptake_determinate_count"] == 1
    assert body["feedback_uptake_determinate_rate"] == 0.5
    assert body["feedback_uptake_correct_rate"] == 1.0
    assert body["retest_count"] == 1
    assert body["retest_status_counts"] == {"scheduled": 1}
    assert body["truncated"] is False
    assert "feedback_metrics_are_deterministic_telemetry_only" in body[
        "data_quality_warnings"
    ]


def test_learning_metrics_rejects_invalid_window(api) -> None:
    now = datetime.now(UTC)
    response = api.client.get(
        "/api/v1/learning/metrics",
        params={
            "window_start": now.isoformat(),
            "window_end": (now - timedelta(minutes=1)).isoformat(),
        },
    )

    assert response.status_code == 422


def test_learning_metrics_requires_teacher_or_admin_when_auth_is_enabled(
    settings,
) -> None:
    auth_settings = settings.model_copy(
        update={
            "auth_required": True,
            "auth_allow_registration": True,
            "auth_scrypt_n_log2": 14,
        }
    )
    app = create_app(auth_settings)
    with TestClient(app) as auth_client:
        register(auth_client, login="metrics-student@example.com")

        response = auth_client.get("/api/v1/learning/metrics")

        assert response.status_code == 403
