from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field


class AnalyticsReportRead(BaseModel):
    version: str = "v1"
    data_source: str = "local_database"
    window_start: datetime
    window_end: datetime
    filters: dict[str, str | None] = Field(default_factory=dict)
    row_limit: int = Field(ge=1)
    truncated: bool = False
    metrics: dict[str, int | float | str | None] = Field(default_factory=dict)
    breakdowns: dict[str, dict[str, int | float | None] | list[dict[str, Any]]] = Field(
        default_factory=dict
    )
    definitions: dict[str, str] = Field(default_factory=dict)
    data_quality_warnings: list[str] = Field(default_factory=list)


class AnalyticsQuery(BaseModel):
    window_start: datetime
    window_end: datetime
    timezone: str = "UTC"
    course: str | None = None
    role: str | None = None
    intent: str | None = None
    capability: str | None = None
    skill: str | None = None
    tool: str | None = None
    scenario: str | None = None
    provider: str | None = None
    model: str | None = None
    task_id: str | None = None
    pilot_batch: str | None = None
    row_limit: int = Field(default=20_000, ge=100, le=20_000)

    @classmethod
    def default(cls) -> AnalyticsQuery:
        end = datetime.now(UTC)
        return cls(window_start=end - timedelta(days=30), window_end=end)
