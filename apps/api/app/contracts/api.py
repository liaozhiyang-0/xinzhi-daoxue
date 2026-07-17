from __future__ import annotations

from datetime import datetime
from typing import Any

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
    created_at: datetime
    updated_at: datetime


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
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    artifact_ids: list[str] = Field(default_factory=list)


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
    content_type: str
    size_bytes: int
    storage_key: str
    checksum_sha256: str
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
    xingchen_publication_status: str
    xingchen_runtime_available: bool
    version: str
