from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.contracts.learning import HintDecisionV1
from app.models.entities import PracticeAttemptModel
from app.services.feedback_uptake import FeedbackUptakeService


def attempt(
    attempt_id: str,
    text: str,
    verification: str,
    *,
    submitted_at: datetime,
) -> PracticeAttemptModel:
    return PracticeAttemptModel(
        id=attempt_id,
        source_task_id="task-1",
        task_id="task-1",
        session_id="session-1",
        user_id="user-1",
        course_id="CT",
        attempt_sequence=1 if attempt_id == "a1" else 2,
        student_answer=text,
        final_answer=text,
        steps_data=[],
        verification_status=verification,
        status="verified",
        submitted_at=submitted_at,
        created_at=submitted_at,
        updated_at=submitted_at,
    )


def hint() -> HintDecisionV1:
    return HintDecisionV1(
        hint_level="H1",
        target_skill_ids=["CT.AC_POWER"],
        target_step_id="student-final",
        hint_text="检查单位",
        source="CT.unit_missing.H1",
        disclosure_checked=True,
        next_action="submit_attempt_revision",
    )


def test_p3_05_unit_fix_and_p3_06_modified_but_wrong() -> None:
    now = datetime.now(UTC)
    previous = attempt("a1", "P=20", "verified_incorrect", submitted_at=now)
    corrected = attempt(
        "a2",
        "P=20 W",
        "verified_correct",
        submitted_at=now + timedelta(seconds=12),
    )
    wrong = attempt(
        "a2",
        "P=18 W",
        "verified_incorrect",
        submitted_at=now + timedelta(seconds=15),
    )
    service = FeedbackUptakeService()
    fixed, _ = service.evaluate(
        previous=previous, current=corrected, hint=hint()
    )
    still_wrong, _ = service.evaluate(
        previous=previous, current=wrong, hint=hint()
    )
    assert fixed.status.value == "applied_correctly"
    assert fixed.modification_correct is True
    assert fixed.time_to_revision_seconds == 12
    assert still_wrong.status.value == "applied_incorrectly"
    assert still_wrong.modification_correct is False


def test_p3_07_not_applied_and_p3_08_complex_is_indeterminate() -> None:
    now = datetime.now(UTC)
    previous = attempt("a1", "P=20", "verified_incorrect", submitted_at=now)
    unchanged = attempt(
        "a2",
        "P=20",
        "verified_incorrect",
        submitted_at=now + timedelta(seconds=3),
    )
    complex_revision = attempt(
        "a2",
        "我使用另一条完整推导路径",
        "manual_review",
        submitted_at=now + timedelta(seconds=8),
    )
    service = FeedbackUptakeService()
    not_applied, _ = service.evaluate(
        previous=previous, current=unchanged, hint=hint()
    )
    indeterminate, _ = service.evaluate(
        previous=previous,
        current=complex_revision,
        hint=hint(),
    )
    assert not_applied.status.value == "not_applied"
    assert indeterminate.status.value == "indeterminate"
    assert indeterminate.modification_correct is None
    assert service.model_enabled is False
