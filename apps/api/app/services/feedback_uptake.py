from __future__ import annotations

import re
from datetime import UTC
from time import perf_counter
from typing import Any

from app.contracts.learning import (
    FeedbackUptakeStatus,
    FeedbackUptakeV1,
    HintDecisionV1,
)
from app.core.errors import ValidationAppError
from app.models.entities import PracticeAttemptModel

SPACE_RE = re.compile(r"\s+")


def _normalized(value: str | None) -> str:
    return SPACE_RE.sub("", value or "").casefold()


def _steps(attempt: PracticeAttemptModel) -> dict[str, str]:
    output: dict[str, str] = {}
    for index, raw in enumerate(attempt.steps_data or [], start=1):
        if not isinstance(raw, dict):
            continue
        step_id = str(raw.get("step_id") or f"step-{index}")
        output[step_id] = _normalized(
            " ".join(
                str(raw.get(key) or "")
                for key in ("content", "expression", "claimed_result", "unit")
            )
        )
    return output


class FeedbackUptakeService:
    """Local-only comparison; textual ambiguity degrades to indeterminate."""

    model_enabled = False

    def evaluate(
        self,
        *,
        previous: PracticeAttemptModel,
        current: PracticeAttemptModel,
        hint: HintDecisionV1 | None,
    ) -> tuple[FeedbackUptakeV1, float]:
        started = perf_counter()
        if (
            previous.user_id != current.user_id
            or previous.session_id != current.session_id
            or previous.source_task_id != current.source_task_id
        ):
            raise ValidationAppError("FeedbackUptake要求同一用户、Session和来源任务")

        previous_steps = _steps(previous)
        current_steps = _steps(current)
        modified_step_ids = sorted(
            key
            for key in previous_steps.keys() | current_steps.keys()
            if previous_steps.get(key) != current_steps.get(key)
        )
        text_modified = _normalized(previous.student_answer) != _normalized(
            current.student_answer
        )
        final_modified = _normalized(previous.final_answer) != _normalized(
            current.final_answer
        )
        student_modified = bool(text_modified or final_modified or modified_step_ids)
        target_step_id = hint.target_step_id if hint else None
        target_step_modified = bool(
            target_step_id
            and (
                target_step_id in modified_step_ids
                or (
                    target_step_id in {"student-final", "final"}
                    and (text_modified or final_modified)
                )
            )
        )
        previous_status = previous.verification_status
        current_status = current.verification_status
        warnings: list[str] = []
        modification_correct: bool | None = None
        confidence: float | None = None

        if hint is None:
            status = FeedbackUptakeStatus.NOT_APPLICABLE
            method = "no_feedback_target"
        elif not student_modified or (
            target_step_id is not None and not target_step_modified
        ):
            status = FeedbackUptakeStatus.NOT_APPLIED
            method = "normalized_text_and_step_ids"
            modification_correct = False
            confidence = 0.95
        elif current_status == "manual_review" or previous_status in {
            "manual_review",
            "heuristic",
            None,
        }:
            status = FeedbackUptakeStatus.INDETERMINATE
            method = "unsupported_complex_reasoning"
            warnings.append("复杂推导不能仅凭文本差异判断为理解提升")
        elif (
            previous_status == "verified_incorrect"
            and current_status == "verified_correct"
        ):
            status = FeedbackUptakeStatus.APPLIED_CORRECTLY
            method = "verification_transition"
            modification_correct = True
            confidence = 1.0
        elif current_status == "verified_incorrect":
            status = FeedbackUptakeStatus.APPLIED_INCORRECTLY
            method = "verification_transition"
            modification_correct = False
            confidence = 1.0
        elif current_status == "verified_correct":
            status = FeedbackUptakeStatus.PARTIALLY_APPLIED
            method = "verification_without_supported_error_transition"
            modification_correct = True
            confidence = 0.7
        else:
            status = FeedbackUptakeStatus.INDETERMINATE
            method = "unsupported_status_transition"
            warnings.append("当前验证状态不足以确定反馈是否被正确采用")

        previous_time = previous.submitted_at or previous.created_at
        current_time = current.submitted_at or current.created_at
        if previous_time.tzinfo is None:
            previous_time = previous_time.replace(tzinfo=UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        interval = max(0, int((current_time - previous_time).total_seconds()))
        result = FeedbackUptakeV1(
            user_id=current.user_id,
            session_id=str(current.session_id or ""),
            source_task_id=current.source_task_id,
            previous_attempt_id=previous.id,
            current_attempt_id=current.id,
            hint_level=hint.hint_level if hint else None,
            hint_source=hint.source if hint else None,
            target_step_id=target_step_id,
            target_skill_ids=list(hint.target_skill_ids) if hint else [],
            student_modified=student_modified,
            modified_step_ids=modified_step_ids,
            target_step_modified=target_step_modified,
            previous_verification_status=previous_status,
            current_verification_status=current_status,
            status=status,
            modification_correct=modification_correct,
            time_to_revision_seconds=interval,
            evaluation_method=method,
            confidence=confidence,
            warnings=warnings,
        )
        return result, (perf_counter() - started) * 1000

    @staticmethod
    def hint_from_payload(payload: dict[str, Any]) -> HintDecisionV1 | None:
        raw = payload.get("hint")
        if not isinstance(raw, dict):
            return None
        try:
            return HintDecisionV1.model_validate(raw)
        except ValueError:
            return None
