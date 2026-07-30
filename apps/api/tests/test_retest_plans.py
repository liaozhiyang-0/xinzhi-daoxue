from __future__ import annotations

import asyncio
from datetime import timedelta

from app.models.entities import RetestPlanModel, utc_now

from apps.api.tests.phase3_helpers import learning_action, submit_power


def full_solution_plans(api):
    session = api.create_session()
    task = submit_power(
        api,
        session["id"],
        student_attempt={"raw_text": "P=20", "final_answer": "20"},
    )
    switched = learning_action(
        api,
        task["id"],
        "switch_to_direct_answer",
        key="phase3-switch-direct-0001",
    )
    assert switched.status_code == 200
    revised = learning_action(
        api,
        task["id"],
        "submit_attempt_revision",
        key="phase3-full-seen-0001",
        answer="P=20 W",
    )
    assert revised.status_code == 200, revised.text
    plans = revised.json()["retest_plans"]
    return session, task, plans


def test_p3_12_full_solution_creates_unique_one_and_seven_day_plans(api) -> None:
    _, task, plans = full_solution_plans(api)
    assert {item["interval_days"] for item in plans} == {1, 7}
    assert all(item["reason_code"] == "full_solution_seen" for item in plans)
    rows = api.client.get(
        "/api/v1/learning/retests",
        params={"user_id": "user-test"},
    )
    assert rows.status_code == 200
    assert len(rows.json()) == 2
    assert task["id"] == rows.json()[0]["source_task_id"]


def test_p3_14_due_query_and_p3_15_p3_16_retest_outcomes(api, app) -> None:
    _, task, plans = full_solution_plans(api)

    async def make_due() -> None:
        async with app.state.session_factory() as db:
            row = await db.get(RetestPlanModel, plans[0]["retest_plan_id"])
            assert row is not None
            row.due_at = utc_now() - timedelta(minutes=1)
            await db.commit()

    asyncio.run(make_due())
    due = api.client.get(
        "/api/v1/learning/retests",
        params={"user_id": "user-test", "status": "due"},
    )
    assert due.status_code == 200
    assert due.json()[0]["status"] == "due"

    correct = learning_action(
        api,
        task["id"],
        "complete_retest",
        key="phase3-retest-correct-0001",
        answer="P=20 W",
        payload={
            "retest_plan_id": plans[0]["retest_plan_id"],
            "completed_task_id": task["id"],
            "result": "correct",
        },
    )
    assert correct.status_code == 200, correct.text
    assert correct.json()["mastery_evidence"][0]["evidence_type"] == (
        "delayed_retest_correct"
    )

    incorrect = learning_action(
        api,
        task["id"],
        "complete_retest",
        key="phase3-retest-incorrect-0001",
        answer="P=18 W",
        payload={
            "retest_plan_id": plans[1]["retest_plan_id"],
            "completed_task_id": task["id"],
            "result": "incorrect",
        },
    )
    assert incorrect.status_code == 200, incorrect.text
    body = incorrect.json()
    assert body["mastery_evidence"][0]["evidence_type"] == (
        "delayed_retest_incorrect"
    )
    assert any(
        item["interval_days"] == 1 and item["status"] == "scheduled"
        for item in body["retest_plans"]
    )
