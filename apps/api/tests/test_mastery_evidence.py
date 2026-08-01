from __future__ import annotations

from app.contracts.learning import MasteryEvidenceType
from app.models.entities import PracticeAttemptModel
from app.services.learning_outcome import LearningOutcomeService


def evidence_attempt(
    *,
    verification: str,
    hint_level: str | None = None,
    full_solution_seen: bool = False,
) -> PracticeAttemptModel:
    return PracticeAttemptModel(
        id="attempt-1",
        source_task_id="task-1",
        task_id="task-1",
        session_id="session-1",
        user_id="user-1",
        course_id="CT",
        attempt_sequence=1,
        student_answer="P=20 W",
        verification_status=verification,
        hint_level_used=hint_level,
        full_solution_seen=full_solution_seen,
        status="verified",
    )


def test_p3_09_independent_correct_and_p3_13_manual_review() -> None:
    independent = LearningOutcomeService._evidence_type(
        evidence_attempt(verification="verified_correct"),
        uptake=None,
        retest_result=None,
    )
    manual = LearningOutcomeService._evidence_type(
        evidence_attempt(verification="manual_review"),
        uptake=None,
        retest_result=None,
    )
    assert independent == MasteryEvidenceType.INDEPENDENT_CORRECT
    assert manual == MasteryEvidenceType.MANUAL_REVIEW


def test_p3_12_full_solution_overrides_subsequent_correctness() -> None:
    evidence_type = LearningOutcomeService._evidence_type(
        evidence_attempt(
            verification="verified_correct",
            full_solution_seen=True,
        ),
        uptake=None,
        retest_result=None,
    )
    assert evidence_type == MasteryEvidenceType.FULL_SOLUTION_SEEN
