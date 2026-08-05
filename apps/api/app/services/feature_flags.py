from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemSettingModel

FEEDBACK_LOOP_FEATURE = "feedback_loop"

FEATURE_DEFINITIONS: dict[str, dict[str, str]] = {
    FEEDBACK_LOOP_FEATURE: {
        "label": "反馈闭环",
        "description": "控制学生反馈提交、教师反馈指标和学习反馈采纳链路。",
    }
}
DEFAULT_FEATURE_VALUES = {FEEDBACK_LOOP_FEATURE: True}


def feature_definition(key: str) -> dict[str, str]:
    definition = FEATURE_DEFINITIONS.get(key)
    if definition is None:
        raise KeyError(key)
    return definition


async def is_feature_enabled(
    db: AsyncSession, key: str, *, default: bool | None = None
) -> bool:
    fallback = DEFAULT_FEATURE_VALUES.get(key, True) if default is None else default
    setting = await db.get(SystemSettingModel, key)
    if setting is None:
        return fallback
    value: Any = setting.value or {}
    enabled = value.get("enabled") if isinstance(value, dict) else None
    return enabled if isinstance(enabled, bool) else fallback


async def list_feature_settings(db: AsyncSession) -> list[dict[str, object]]:
    rows = {
        item.key: item
        for item in (await db.scalars(select(SystemSettingModel))).all()
    }
    result: list[dict[str, object]] = []
    for key, definition in FEATURE_DEFINITIONS.items():
        row = rows.get(key)
        result.append(
            {
                "key": key,
                "label": definition["label"],
                "description": definition["description"],
                "enabled": await is_feature_enabled(db, key),
                "updated_at": row.updated_at if row is not None else None,
                "updated_by": row.updated_by if row is not None else None,
            }
        )
    return result


async def set_feature_enabled(
    db: AsyncSession,
    key: str,
    enabled: bool,
    *,
    updated_by: str,
) -> dict[str, object]:
    definition = feature_definition(key)
    row = await db.get(SystemSettingModel, key)
    now = datetime.now(UTC)
    if row is None:
        row = SystemSettingModel(
            key=key,
            value={"enabled": enabled},
            updated_by=updated_by,
            updated_at=now,
        )
        db.add(row)
    else:
        row.value = {"enabled": enabled}
        row.updated_by = updated_by
        row.updated_at = now
    await db.commit()
    await db.refresh(row)
    return {
        "key": key,
        "label": definition["label"],
        "description": definition["description"],
        "enabled": enabled,
        "updated_at": row.updated_at,
        "updated_by": row.updated_by,
    }
