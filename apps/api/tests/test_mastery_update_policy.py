from __future__ import annotations

import asyncio

from app.models import PracticeAttemptModel, TaskModel, TaskStatus
from app.services.learning_outcome import LearningOutcomeService
from sqlalchemy import select

from apps.api.tests.phase3_helpers import submit_power


def test_p3_09_to_p3_13_configured_delta_order_and_safe_zeroes() -> None:
    service = LearningOutcomeService()
    updates = service.config["evidence_updates"]
    assert updates["independent_correct"]["delta"] > updates[
        "h0_h1_correct"
    ]["delta"]
    assert updates["h0_h1_correct"]["delta"] > updates["h2_correct"]["delta"]
    assert updates["full_solution_seen"]["delta"] == 0
    assert updates["manual_review"]["delta"] == 0
    assert service.config["calibration_status"] == "uncalibrated_heuristic"


def test_p3_15_and_p3_16_delayed_retest_rules_are_asymmetric() -> None:
    updates = LearningOutcomeService().config["evidence_updates"]
    assert updates["delayed_retest_correct"]["delta"] == 0.12
    assert updates["delayed_retest_incorrect"]["delta"] == -0.07


def test_p3_18_p3_19_cancelled_or_failed_task_has_no_new_evidence(
    api, app
) -> None:
    session = api.create_session()
    task_data = submit_power(
        api,
        session["id"],
        student_attempt={"raw_text": "P=20"},
    )

    async def check(status: TaskStatus) -> None:
        async with app.state.session_factory() as db:
            task = await db.get(TaskModel, task_data["id"])
            assert task is not None
            attempt = await db.scalar(
                select(PracticeAttemptModel).where(
                    PracticeAttemptModel.source_task_id == task.id
                )
            )
            assert attempt is not None
            task.status = status
            outcome = await app.state.learning_loop.learning_outcome.process_attempt(
                db,
                task=task,
                attempt=attempt,
                skill_ids=["CT.AC_POWER"],
            )
            assert outcome.evidence == []
            await db.rollback()

    asyncio.run(check(TaskStatus.CANCELLED))
    asyncio.run(check(TaskStatus.FAILED))
