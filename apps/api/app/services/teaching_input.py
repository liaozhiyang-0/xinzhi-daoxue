from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.contracts import StudentAttempt, TeachingMode
from app.core.errors import ValidationAppError

FOUNDATION_ONLY_MODES = frozenset(
    {TeachingMode.REVIEW}
)
FOUNDATION_WARNING = (
    "当前版本已保存学习模式，但完整分级辅导将在后续阶段启用。"
)


def normalize_teaching_options(
    options: dict[str, Any],
) -> tuple[dict[str, Any], TeachingMode, StudentAttempt | None]:
    normalized = dict(options)
    try:
        mode = TeachingMode(
            str(normalized.get("teaching_mode", TeachingMode.DIRECT_ANSWER))
        )
    except ValueError as exc:
        raise ValidationAppError(
            "teaching_mode 无效",
            details={"allowed": [item.value for item in TeachingMode]},
        ) from exc
    raw_attempt = normalized.get("student_attempt")
    try:
        attempt = (
            StudentAttempt.model_validate(raw_attempt)
            if raw_attempt is not None
            else None
        )
    except ValidationError as exc:
        errors = [
            {
                "loc": list(error["loc"]),
                "msg": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors(include_url=False)
        ]
        raise ValidationAppError(
            "student_attempt 校验失败",
            details={"errors": errors},
        ) from exc
    normalized["teaching_mode"] = mode.value
    if attempt is not None:
        normalized["student_attempt"] = attempt.model_dump(mode="json")
    return normalized, mode, attempt


def teaching_mode_status(mode: TeachingMode) -> tuple[str, str]:
    if mode in FOUNDATION_ONLY_MODES:
        return "foundation_only", FOUNDATION_WARNING
    return "available", ""
