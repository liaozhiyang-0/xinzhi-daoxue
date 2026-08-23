from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import TaskStatus


class SessionCreate(BaseModel):
    user_id: str
    course_id: str = "CT"
    title: str = ""


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    course_id: str
    title: str
    title_source: str
    archived_at: datetime | None
    last_message_at: datetime | None
    message_count: int
    session_revision: int
    parent_session_id: str | None
    branch_from_message_id: str | None
    memory_enabled: bool
    auto_memory_enabled: bool
    context_compaction_enabled: bool
    created_at: datetime
    updated_at: datetime


class SessionUpdate(BaseModel):
    user_id: str
    title: str | None = Field(default=None, max_length=255)
    course_id: str | None = Field(default=None, max_length=32)
    memory_enabled: bool | None = None
    auto_memory_enabled: bool | None = None
    context_compaction_enabled: bool | None = None


class SessionTaskHistoryItem(BaseModel):
    id: str
    course_id: str
    intent: str
    status: TaskStatus
    provider: str
    agent_id: str
    question: str
    answer: str
    error_message: str | None
    fallback_used: bool = False
    fallback_reason: str = ""
    answer_quality_status: str = "not_available"
    requires_review: bool = False
    publishable: bool | None = None
    math_quality_status: str = "not_available"
    formula_contract_status: str = "not_available"
    created_at: datetime
    completed_at: datetime | None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    user_id: str
    course_id: str
    intent: str
    status: TaskStatus
    provider: str
    agent_id: str
    route_status: str
    route_reason: str
    input_content: dict[str, Any]
    result_content: dict[str, Any] | None
    error_message: str | None
    parent_task_id: str | None
    attempt: int
    cancellation_requested: bool
    idempotency_key: str | None
    max_attempts: int
    execution_owner: str | None
    lease_expires_at: datetime | None
    heartbeat_at: datetime | None
    cancel_requested_at: datetime | None
    failure_category: str | None
    user_message_id: str | None
    assistant_message_id: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    artifact_ids: list[str] = Field(default_factory=list)
    retryable: bool = False


class TaskRuntimeControlRead(BaseModel):
    """One state-aware Runtime action safe for the task owner to inspect."""

    action: Literal["pause", "resume", "approve", "input"]
    available: bool
    reason_code: str = ""
    reason: str = ""


class TaskRuntimePlanProposalRead(BaseModel):
    """Redacted summary of a pending adaptive Runtime plan proposal."""

    proposal_id: str
    status: Literal["pending", "approved", "rejected", "applied"]
    state_version: int = Field(ge=1)
    base_iteration: int = Field(ge=0)
    target_iteration: int = Field(ge=1)
    reason_codes: list[str] = Field(default_factory=list, max_length=16)
    affected_node_ids: list[str] = Field(default_factory=list, max_length=100)


class TaskRuntimeControlProjectionRead(BaseModel):
    """Redacted Runtime control state for the student-facing task workspace.

    This deliberately excludes checkpoint state, request snapshots, Provider
    identifiers and raw control data. Mutations remain on the existing Task
    control endpoints, which enforce ownership and state transitions.
    """

    task_id: str
    runtime_run_id: str = ""
    run_kind: str = ""
    status: str = ""
    state_version: int = 0
    control_request: str = ""
    control_scope: Literal["runtime", "runtime_plan_proposal"] = "runtime"
    plan_proposal: TaskRuntimePlanProposalRead | None = None
    controls: list[TaskRuntimeControlRead] = Field(default_factory=list)


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    sequence: int
    event_type: str
    event_data: dict[str, Any]
    created_at: datetime


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    artifact_type: str
    version: str
    content: dict[str, Any]
    confidence: float | None
    created_at: datetime


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str | None
    filename: str
    course_id: str | None = None
    material_key: str | None = None
    material_version: str | None = None
    knowledge_status: str = "draft"
    knowledge_index_status: str = "not_indexed"
    knowledge_published_by: str | None = None
    knowledge_published_at: datetime | None = None
    content_type: str
    size_bytes: int
    storage_key: str
    checksum_sha256: str
    detected_content_type: str
    ingestion_status: str
    page_count: int
    extracted_text: str
    extraction_metadata: dict[str, Any]
    extraction_error: str | None
    extraction_version: str
    extraction_started_at: datetime | None
    extraction_completed_at: datetime | None
    created_at: datetime


class FileChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_id: str
    ordinal: int
    page_number: int | None
    section: str
    content: str
    char_start: int
    char_end: int
    source_ref: str
    created_at: datetime


class HealthRead(BaseModel):
    status: str
    environment: str
    database: str
    redis: str
    minio: str
    requested_provider: str
    active_provider: str
    provider_mode: str
    version: str
    runtime_identity: dict[str, Any] = Field(default_factory=dict)
    configuration_status: str = "unknown"
    configuration_warnings: list[str] = Field(default_factory=list)
    model_runtime: dict[str, Any] = Field(default_factory=dict)
    external_retrieval: dict[str, Any] = Field(default_factory=dict)
    task_queue: dict[str, Any] = Field(default_factory=dict)
