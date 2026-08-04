from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import TaskStatus

AccountRole = Literal["student", "teacher", "operator", "admin"]
AccountStatusValue = Literal["active", "disabled", "locked"]


class AdminAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    login: str
    display_name: str
    role: str
    status: str
    failed_login_attempts: int
    locked_until: datetime | None
    last_login_at: datetime | None
    password_changed_at: datetime
    created_at: datetime
    updated_at: datetime


class AdminAccountCreate(BaseModel):
    login: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(default="", max_length=255)
    role: AccountRole = "student"


class AdminAccountUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    role: AccountRole | None = None
    status: AccountStatusValue | None = None


class AdminPasswordReset(BaseModel):
    password: str = Field(min_length=12, max_length=256)


class AdminFeatureSettingRead(BaseModel):
    key: str
    label: str
    description: str
    enabled: bool
    updated_at: datetime | None
    updated_by: str | None


class AdminFeatureSettingUpdate(BaseModel):
    enabled: bool


class AdminSessionRead(BaseModel):
    id: str
    account_id: str
    login: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    revoked_at: datetime | None
    last_seen_at: datetime | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_account_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    details: dict[str, object]
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class AdminOverviewRead(BaseModel):
    account_count: int
    active_account_count: int
    disabled_account_count: int
    locked_account_count: int
    active_session_count: int
    audit_event_count: int


class AdminTaskRead(BaseModel):
    id: str
    session_id: str
    user_id: str
    login: str | None
    display_name: str | None
    course_id: str
    intent: str
    status: TaskStatus
    provider: str
    agent_id: str
    route_status: str
    attempt: int
    failure_category: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class AdminTaskSummaryRead(BaseModel):
    total: int
    active: int
    completed: int
    failed: int
    status_counts: dict[str, int]
    failure_category_counts: dict[str, int] = Field(default_factory=dict)
    provider_counts: dict[str, int] = Field(default_factory=dict)
    route_status_counts: dict[str, int] = Field(default_factory=dict)
    cancellation_requested_count: int = 0


class AdminTaskObservabilityRead(BaseModel):
    version: str = "v1"
    data_source: str = "local_database"
    window_start: datetime
    window_end: datetime
    row_limit: int
    truncated: bool = False
    task_count: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    failure_category_counts: dict[str, int] = Field(default_factory=dict)
    provider_counts: dict[str, int] = Field(default_factory=dict)
    route_status_counts: dict[str, int] = Field(default_factory=dict)
    cancellation_requested_count: int = 0
    measured_total_latency_count: int = 0
    average_total_latency_ms: float | None = None
    p50_total_latency_ms: float | None = None
    p95_total_latency_ms: float | None = None
    measured_queue_latency_count: int = 0
    average_queue_latency_ms: float | None = None
    p50_queue_latency_ms: float | None = None
    p95_queue_latency_ms: float | None = None
    data_quality_warnings: list[str] = Field(default_factory=list)


class AdminFileRead(BaseModel):
    id: str
    filename: str
    owner_user_id: str | None
    task_id: str | None
    content_type: str
    detected_content_type: str
    size_bytes: int
    checksum_sha256: str
    purpose: str
    ingestion_status: str
    page_count: int
    extracted_text: str
    extraction_metadata: dict[str, object]
    extraction_error: str | None
    extraction_version: str
    created_at: datetime
    extraction_started_at: datetime | None
    extraction_completed_at: datetime | None


class AdminFileSummaryRead(BaseModel):
    total: int
    pending: int
    processing: int
    ready: int
    partial: int
    failed: int
    total_bytes: int


class AdminEvaluationAttachmentResidueRead(BaseModel):
    purpose: str
    as_of: datetime
    grace_seconds: int
    cutoff: datetime
    total_file_count: int
    total_bytes: int
    unbound_file_count: int
    active_task_file_count: int
    terminal_task_file_count: int
    missing_task_file_count: int
    cleanup_candidate_count: int
    cleanup_candidate_bytes: int
    oldest_created_at: datetime | None
