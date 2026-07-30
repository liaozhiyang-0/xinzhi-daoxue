from __future__ import annotations

from apps.api.tests.phase3_helpers import learning_action, submit_power


def test_retest_api_start_and_dismiss_use_existing_learning_action(api) -> None:
    session = api.create_session()
    task = submit_power(
        api,
        session["id"],
        student_attempt={"raw_text": "P=20"},
    )
    assert (
        learning_action(
            api,
            task["id"],
            "switch_to_direct_answer",
            key="phase3-retest-api-switch",
        ).status_code
        == 200
    )
    revision = learning_action(
        api,
        task["id"],
        "submit_attempt_revision",
        key="phase3-retest-api-revision",
        answer="P=20 W",
    )
    plan = revision.json()["retest_plans"][0]
    start = learning_action(
        api,
        task["id"],
        "start_retest",
        key="phase3-retest-api-start",
        payload={"retest_plan_id": plan["retest_plan_id"]},
    )
    assert start.status_code == 200
    assert start.json()["status"] == "needs_task"
    assert start.json()["follow_up_prompt"]

    dismissed = learning_action(
        api,
        task["id"],
        "dismiss_retest",
        key="phase3-retest-api-dismiss",
        payload={"retest_plan_id": plan["retest_plan_id"]},
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["retest_plans"][0]["status"] == "cancelled"
    hidden = api.client.get(
        "/api/v1/learning/retests",
        params={"user_id": "another-user"},
    )
    assert hidden.status_code == 200
    assert hidden.json() == []
