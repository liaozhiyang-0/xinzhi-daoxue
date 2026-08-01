from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.learning import (
    MasteryEvidenceType,
    PracticeProblem,
    RetestPlanStatus,
    RetestPlanV1,
)
from app.core.errors import NotFoundError, ValidationAppError
from app.models.entities import RetestPlanModel, TaskModel, utc_now
from app.repositories.learning import LearningRecordRepository
from app.services.practice_generation import PracticeGenerationService

SUPPORTED_RETEST_COURSES = {"CT", "AE", "DE"}


class RetestPlanService:
    """Creates and queries local due records; it has no scheduler or notifier."""

    def __init__(
        self,
        intervals: dict[str, list[int]],
        practice: PracticeGenerationService | None = None,
    ) -> None:
        self.intervals = {
            str(key): [int(item) for item in value] for key, value in intervals.items()
        }
        self.practice = practice or PracticeGenerationService()

    async def create_for_evidence(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        skill_id: str,
        source_task_id: str,
        source_attempt_id: str | None,
        evidence_type: MasteryEvidenceType,
        now: datetime | None = None,
    ) -> list[RetestPlanModel]:
        intervals = self.intervals.get(evidence_type.value, [])
        current = now or utc_now()
        repository = LearningRecordRepository(session)
        output: list[RetestPlanModel] = []
        for interval_days in intervals:
            existing = await repository.existing_retest(
                user_id=user_id,
                skill_id=skill_id,
                source_task_id=source_task_id,
                interval_days=interval_days,
            )
            if existing is not None:
                if evidence_type == MasteryEvidenceType.DELAYED_RETEST_INCORRECT:
                    existing.due_at = current + timedelta(days=interval_days)
                    existing.status = RetestPlanStatus.SCHEDULED.value
                    existing.result = None
                    existing.completed_task_id = None
                    existing.updated_at = current
                output.append(existing)
                continue
            model = RetestPlanModel(
                user_id=user_id,
                skill_id=skill_id,
                source_task_id=source_task_id,
                source_attempt_id=source_attempt_id,
                interval_days=interval_days,
                due_at=current + timedelta(days=interval_days),
                status=RetestPlanStatus.SCHEDULED.value,
                reason_code=evidence_type.value,
                created_at=current,
                updated_at=current,
            )
            session.add(model)
            await session.flush()
            output.append(model)
        return output

    async def list(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        status: str | None,
        offset: int,
        limit: int,
        now: datetime | None = None,
    ) -> list[RetestPlanV1]:
        current = now or utc_now()
        rows = await LearningRecordRepository(session).list_retests(
            user_id,
            status=status,
            now=current,
            offset=offset,
            limit=limit,
        )
        return [self.to_contract(item, now=current) for item in rows]

    async def get_owned(
        self, session: AsyncSession, *, retest_plan_id: str, user_id: str
    ) -> RetestPlanModel:
        model = await LearningRecordRepository(session).retest_by_id(
            retest_plan_id, user_id
        )
        if model is None:
            raise NotFoundError("未找到可访问的复习计划")
        return model

    async def start(
        self,
        session: AsyncSession,
        *,
        retest_plan_id: str,
        user_id: str,
    ) -> tuple[RetestPlanModel, PracticeProblem]:
        plan = await self.get_owned(
            session, retest_plan_id=retest_plan_id, user_id=user_id
        )
        task = await session.get(TaskModel, plan.source_task_id)
        if task is None or task.user_id != user_id:
            raise NotFoundError("未找到可访问的来源任务")
        if task.course_id.upper() not in SUPPORTED_RETEST_COURSES:
            raise ValidationAppError("当前再测只支持CT、AE和DE课程")
        canonical = task.input_content.get("canonical_input", {})
        problem_text = (
            str(canonical.get("text", "")) if isinstance(canonical, dict) else ""
        )
        practice = self.practice.generate(task.id, problem_text)
        plan.generated_problem_id = (
            f"practice-{uuid4().hex}" if practice.status == "ready" else None
        )
        plan.updated_at = utc_now()
        return plan, practice

    async def complete(
        self,
        session: AsyncSession,
        *,
        retest_plan_id: str,
        user_id: str,
        completed_task_id: str,
        result: str,
    ) -> RetestPlanModel:
        if result not in {"correct", "incorrect"}:
            raise ValidationAppError("再测结果必须为correct或incorrect")
        plan = await self.get_owned(
            session, retest_plan_id=retest_plan_id, user_id=user_id
        )
        task = await session.get(TaskModel, completed_task_id)
        if task is None or task.user_id != user_id:
            raise NotFoundError("未找到可访问的再测任务")
        plan.completed_task_id = completed_task_id
        plan.result = result
        plan.status = RetestPlanStatus.COMPLETED.value
        plan.updated_at = utc_now()
        return plan

    async def dismiss(
        self,
        session: AsyncSession,
        *,
        retest_plan_id: str,
        user_id: str,
    ) -> RetestPlanModel:
        plan = await self.get_owned(
            session, retest_plan_id=retest_plan_id, user_id=user_id
        )
        plan.status = RetestPlanStatus.CANCELLED.value
        plan.updated_at = utc_now()
        return plan

    @staticmethod
    def to_contract(
        item: RetestPlanModel, *, now: datetime | None = None
    ) -> RetestPlanV1:
        current = now or utc_now()
        due_at = item.due_at
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        status = RetestPlanStatus(item.status)
        if status == RetestPlanStatus.SCHEDULED and due_at <= current:
            status = RetestPlanStatus.DUE
        return RetestPlanV1(
            retest_plan_id=item.id,
            user_id=item.user_id,
            skill_id=item.skill_id,
            source_task_id=item.source_task_id,
            source_attempt_id=item.source_attempt_id,
            interval_days=item.interval_days,
            due_at=due_at,
            status=status,
            reason_code=item.reason_code,
            generated_problem_id=item.generated_problem_id,
            completed_task_id=item.completed_task_id,
            result=item.result,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
