from __future__ import annotations

from apps.api.tests.phase3_helpers import submit_power


def test_attempt_api_is_paginated_owned_and_hides_internal_report(api) -> None:
    session = api.create_session()
    task = submit_power(
        api,
        session["id"],
        student_attempt={"raw_text": "P=20", "final_answer": "20"},
    )
    response = api.client.get(
        "/api/v1/learning/attempts",
        params={
            "user_id": "user-test",
            "source_task_id": task["id"],
            "offset": 0,
            "limit": 1,
        },
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    attempt = response.json()[0]
    assert "verification_report" not in attempt
    assert attempt["verification_report_ref"] == task["id"]
    assert (
        api.client.get(
            f"/api/v1/learning/attempts/{attempt['attempt_id']}",
            params={"user_id": "another-user"},
        ).status_code
        == 404
    )
