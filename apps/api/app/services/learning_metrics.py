from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.learning import LearningMetricsRead
from app.models import PracticeAttemptModel, RetestPlanModel, TaskModel


class LearningMetricsService:
    """Build bounded, privacy-preserving aggregates from existing learning rows."""

    DEFAULT_ROW_LIMIT = 5_000
    DETERMINATE_FEEDBACK_STATUSES = frozenset(
        {
            "applied_correctly",
            "applied_incorrectly",
            "partially_applied",
            "not_applied",
        }
    )

    async def aggregate(
        self,
        session: AsyncSession,
        *,
        course_id: str | None,
        window_start: datetime,
        window_end: datetime,
        row_limit: int = DEFAULT_ROW_LIMIT,
    ) -> LearningMetricsRead:
        """Aggregate persisted attempts and retests without exposing user IDs.

        The current implementation deliberately uses a bounded read and Python
        aggregation because feedback uptake is stored as versioned JSON. A
        future migration can add event columns or a rollup table without
        changing this response contract.
        """

        attempt_filters = [
            PracticeAttemptModel.created_at >= window_start,
            PracticeAttemptModel.created_at < window_end,
        ]
        if course_id:
            attempt_filters.append(PracticeAttemptModel.course_id == course_id)
        attempts = list(
            (
                await session.scalars(
                    select(PracticeAttemptModel)
                    .where(*attempt_filters)
                    .order_by(PracticeAttemptModel.created_at, PracticeAttemptModel.id)
                    .limit(row_limit + 1)
                )
            ).all()
        )
        attempts_truncated = len(attempts) > row_limit
        attempts = attempts[:row_limit]

        attempt_status_counts = Counter(
            self._text_value(item.status, "unknown") for item in attempts
        )
        verification_status_counts = Counter(
            self._text_value(item.verification_status, "not_checked")
            for item in attempts
        )
        manual_review_count = sum(
            1 for item in attempts if self._requires_manual_review(item)
        )

        feedback_status_counts: Counter[str] = Counter()
        for item in attempts:
            status = self._feedback_status(item.feedback_uptake)
            if status:
                feedback_status_counts[status] += 1
        feedback_event_count = sum(feedback_status_counts.values())
        determinate_count = sum(
            feedback_status_counts[status]
            for status in self.DETERMINATE_FEEDBACK_STATUSES
        )
        applied_correctly_count = feedback_status_counts["applied_correctly"]

        retest_filters = [
            RetestPlanModel.created_at >= window_start,
            RetestPlanModel.created_at < window_end,
        ]
        retest_statement = select(RetestPlanModel).join(
            TaskModel, TaskModel.id == RetestPlanModel.source_task_id
        )
        if course_id:
            retest_filters.append(TaskModel.course_id == course_id)
        retests = list(
            (
                await session.scalars(
                    retest_statement.where(*retest_filters)
                    .order_by(RetestPlanModel.created_at, RetestPlanModel.id)
                    .limit(row_limit + 1)
                )
            ).all()
        )
        retests_truncated = len(retests) > row_limit
        retests = retests[:row_limit]
        retest_status_counts = Counter(
            self._text_value(item.status, "unknown") for item in retests
        )

        warnings: list[str] = []
        if attempts_truncated:
            warnings.append("attempt_rows_truncated_to_row_limit")
        if retests_truncated:
            warnings.append("retest_rows_truncated_to_row_limit")
        if feedback_event_count:
            warnings.append("feedback_metrics_are_deterministic_telemetry_only")
        if any(
            self._feedback_status(item.feedback_uptake) == "indeterminate"
            for item in attempts
        ):
            warnings.append("feedback_uptake_contains_indeterminate_events")

        return LearningMetricsRead(
            course_id=course_id,
            window_start=self._utc(window_start),
            window_end=self._utc(window_end),
            attempt_count=len(attempts),
            attempt_status_counts=dict(attempt_status_counts),
            verification_status_counts=dict(verification_status_counts),
            manual_review_count=manual_review_count,
            feedback_uptake_event_count=feedback_event_count,
            feedback_uptake_status_counts=dict(feedback_status_counts),
            feedback_uptake_determinate_count=determinate_count,
            feedback_uptake_determinate_rate=(
                determinate_count / feedback_event_count
                if feedback_event_count
                else None
            ),
            feedback_uptake_applied_correctly_count=applied_correctly_count,
            feedback_uptake_correct_rate=(
                applied_correctly_count / determinate_count
                if determinate_count
                else None
            ),
            retest_count=len(retests),
            retest_status_counts=dict(retest_status_counts),
            row_limit=row_limit,
            truncated=attempts_truncated or retests_truncated,
            data_quality_warnings=warnings,
        )

    @staticmethod
    def _text_value(value: Any, fallback: str) -> str:
        text = str(value or "").strip()
        return text or fallback

    @classmethod
    def _feedback_status(cls, payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get("status")
        return cls._text_value(value, "indeterminate") if value else None

    @staticmethod
    def _requires_manual_review(item: PracticeAttemptModel) -> bool:
        report = item.verification_report
        return bool(
            item.verification_status == "manual_review"
            or item.status == "manual_review"
            or (
                isinstance(report, dict)
                and report.get("manual_review_required") is True
            )
            or bool(item.review_result)
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
