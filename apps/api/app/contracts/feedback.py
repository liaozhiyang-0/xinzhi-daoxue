from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FeedbackSatisfaction(StrEnum):
    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    NEUTRAL = "neutral"


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=64)
    resolved: bool | None = None
    satisfaction: FeedbackSatisfaction | None = None
    problem_type: str | None = Field(default=None, max_length=64)
    manual_review_required: bool = False
    comment: str = Field(default="", max_length=2_000)

    @field_validator("task_id", "comment")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("problem_type")
    @classmethod
    def normalize_problem_type(cls, value: str | None) -> str | None:
        normalized = value.strip() if value is not None else None
        return normalized or None


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    user_role: str
    course_id: str
    task_type: str
    agent_id: str
    agent_version: str | None
    provider: str
    model_version: str | None
    rag_version: str | None
    retrieval_mode: str | None
    resolved: bool | None
    satisfaction: FeedbackSatisfaction | None
    problem_type: str | None
    manual_review_required: bool
    citation_coverage: float | None = Field(default=None, ge=0, le=1)
    latency_ms: int | None = Field(default=None, ge=0)
    comment: str | None
    created_at: datetime
    updated_at: datetime


class FeedbackMetricsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "v1"
    course_id: str | None = None
    window_start: datetime
    window_end: datetime
    data_source: str = "local_database"
    task_count: int = Field(ge=0)
    task_status_counts: dict[str, int] = Field(default_factory=dict)
    completed_task_count: int = Field(ge=0)
    failed_task_count: int = Field(ge=0)
    task_completion_rate: float | None = Field(default=None, ge=0, le=1)
    average_latency_ms: float | None = Field(default=None, ge=0)
    unique_user_count: int = Field(ge=0)
    repeat_user_rate: float | None = Field(default=None, ge=0, le=1)
    feedback_count: int = Field(ge=0)
    feedback_response_rate: float | None = Field(default=None, ge=0, le=1)
    satisfaction_counts: dict[str, int] = Field(default_factory=dict)
    resolved_count: int = Field(ge=0)
    resolved_rate: float | None = Field(default=None, ge=0, le=1)
    manual_review_request_count: int = Field(ge=0)
    problem_type_counts: dict[str, int] = Field(default_factory=dict)
    user_role_counts: dict[str, int] = Field(default_factory=dict)
    task_type_counts: dict[str, int] = Field(default_factory=dict)
    average_citation_coverage: float | None = Field(default=None, ge=0, le=1)
    row_limit: int = Field(ge=1)
    truncated: bool = False
    data_quality_warnings: list[str] = Field(default_factory=list)


class FeedbackFeatureStatusRead(BaseModel):
    key: str = "feedback_loop"
    enabled: bool
