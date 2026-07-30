from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.learning import (
    StudentAttempt,
    StudentAttemptStatus,
    StudentAttemptStep,
    StudentAttemptV2,
    TeachingMode,
)
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.models.entities import (
    PracticeAttemptModel,
    TaskModel,
    TaskStatus,
    utc_now,
)
from app.repositories.learning import LearningRecordRepository


class StudentAttemptService:
    """Creates immutable attempt versions on top of the existing practice table."""

    async def create(
        self,
        session: AsyncSession,
        *,
        task: TaskModel,
        user_id: str,
        idempotency_key: str,
        attempt: StudentAttempt,
        revision_of_attempt_id: str | None = None,
        teaching_mode: TeachingMode = TeachingMode.CHECK_MY_WORK,
        hint_level_used: str | None = None,
        full_solution_seen: bool = False,
        verification_report: dict[str, Any] | None = None,
    ) -> PracticeAttemptModel:
        if task.user_id != user_id:
            raise NotFoundError("未找到可访问的来源任务")
        repository = LearningRecordRepository(session)
        existing = await repository.attempt_by_idempotency(user_id, idempotency_key)
        if existing is not None:
            return existing

        previous = None
        if revision_of_attempt_id:
            previous = await repository.attempt_by_id(revision_of_attempt_id, user_id)
            if previous is None:
                raise NotFoundError("未找到可访问的前一版本")
            if previous.source_task_id != task.id:
                raise ValidationAppError("修订版本必须属于同一来源任务")
        else:
            previous = await repository.latest_attempt(task.id, user_id)

        sequence = int(previous.attempt_sequence or 0) + 1 if previous else 1
        if revision_of_attempt_id is None and previous is not None:
            revision_of_attempt_id = previous.id
        report = dict(verification_report or {})
        verification_status = str(report.get("overall_status")) if report else None
        status = StudentAttemptStatus.SUBMITTED
        if task.status == TaskStatus.CANCELLED or task.cancellation_requested:
            status = StudentAttemptStatus.CANCELLED
            verification_status = None
            report = {}
        elif verification_status == "manual_review":
            status = StudentAttemptStatus.MANUAL_REVIEW
        elif verification_status in {"verified_correct", "verified_incorrect"}:
            status = StudentAttemptStatus.VERIFIED

        if previous is not None:
            if previous.status == StudentAttemptStatus.CANCELLED.value:
                raise ConflictError("已取消的Attempt不能作为修订来源")
            previous.status = StudentAttemptStatus.SUPERSEDED.value
            previous.updated_at = utc_now()

        now = utc_now()
        model = PracticeAttemptModel(
            source_task_id=task.id,
            user_id=user_id,
            course_id=task.course_id,
            session_id=task.session_id,
            task_id=task.id,
            attempt_sequence=sequence,
            revision_of_attempt_id=revision_of_attempt_id,
            idempotency_key=idempotency_key,
            student_answer=attempt.raw_text,
            steps_data=[item.model_dump(mode="json") for item in attempt.steps],
            final_answer=attempt.final_answer,
            student_confidence=attempt.confidence,
            teaching_mode=teaching_mode.value,
            hint_level_used=hint_level_used,
            full_solution_seen=full_solution_seen,
            verification_status=verification_status,
            verification_report=report,
            review_result={},
            status=status.value,
            submitted_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(model)
        await session.flush()
        return model

    async def list(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        source_task_id: str | None,
        offset: int,
        limit: int,
    ) -> list[StudentAttemptV2]:
        rows = await LearningRecordRepository(session).list_attempts(
            user_id,
            source_task_id=source_task_id,
            offset=offset,
            limit=limit,
        )
        return [self.to_contract(item) for item in rows]

    async def get(
        self, session: AsyncSession, *, attempt_id: str, user_id: str
    ) -> StudentAttemptV2:
        row = await LearningRecordRepository(session).attempt_by_id(attempt_id, user_id)
        if row is None or row.attempt_sequence is None:
            raise NotFoundError("未找到可访问的Attempt")
        return self.to_contract(row)

    @staticmethod
    def to_contract(item: PracticeAttemptModel) -> StudentAttemptV2:
        if (
            item.session_id is None
            or item.task_id is None
            or item.attempt_sequence is None
            or item.submitted_at is None
        ):
            raise ValidationAppError("旧变式题记录不是正式StudentAttempt")
        return StudentAttemptV2(
            attempt_id=item.id,
            user_id=item.user_id,
            session_id=item.session_id,
            task_id=item.task_id,
            source_task_id=item.source_task_id,
            attempt_sequence=item.attempt_sequence,
            revision_of_attempt_id=item.revision_of_attempt_id,
            raw_text=item.student_answer,
            final_answer=item.final_answer,
            steps=[
                StudentAttemptStep.model_validate(step)
                for step in item.steps_data
            ],
            confidence=item.student_confidence,
            teaching_mode=TeachingMode(item.teaching_mode),
            hint_level_used=item.hint_level_used,
            full_solution_seen=item.full_solution_seen,
            verification_status=item.verification_status,
            verification_report_ref=(
                item.task_id if item.verification_report else None
            ),
            submitted_at=item.submitted_at,
            status=StudentAttemptStatus(item.status),
        )
