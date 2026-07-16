from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class UserRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    RESEARCHER = "researcher"
    ADMIN = "admin"
    SYSTEM = "system"


class Scene(StrEnum):
    SOLVING = "solving"
    LEARNING = "learning"
    TEACHING = "teaching"
    RESEARCH = "research"


class Intent(StrEnum):
    SOLVE_PROBLEM = "solve_problem"
    EXPLAIN_CONCEPT = "explain_concept"
    VERIFY_ANSWER = "verify_answer"
    GENERAL_QA = "general_qa"


class AgentResultStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentEventType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_QUEUED = "task.queued"
    TASK_RUNNING = "task.running"
    AGENT_STARTED = "agent.started"
    AGENT_PROGRESS = "agent.progress"
    KNOWLEDGE_RETRIEVED = "knowledge.retrieved"
    AGENT_OUTPUT = "agent.output"
    ARTIFACT_CREATED = "artifact.created"
    CANCEL_REQUESTED = "cancel.requested"
    TASK_CANCELLED = "task.cancelled"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_RETRY_CREATED = "task.retry_created"


class ArtifactType(StrEnum):
    ANSWER = "answer"
    REPORT = "report"
    FILE = "file"
    STRUCTURED_RESULT = "structured_result"


class AttachmentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    storage_key: str
    provider_file_id: str | None = None
    checksum_sha256: str | None = None


class RunMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latency_ms: int | None = Field(default=None, ge=0)
    queue_latency_ms: int | None = Field(default=None, ge=0)
    provider_latency_ms: int | None = Field(default=None, ge=0)
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    retrieval_calls: int = Field(default=0, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(default_factory=lambda: new_id("artifact"))
    artifact_type: ArtifactType = ArtifactType.ANSWER
    owner_id: str = ""
    task_id: str = ""
    course_id: str = "CT"
    version: str = "1.0.0"
    content: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    created_at: datetime = Field(default_factory=utc_now)


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(default_factory=lambda: new_id("task"))
    session_id: str
    user_id: str
    user_role: UserRole = UserRole.STUDENT
    scene: Scene = Scene.SOLVING
    course_id: str = "CT"
    intent: Intent = Intent.SOLVE_PROBLEM
    canonical_input: dict[str, Any] = Field(default_factory=dict)
    attachments: list[AttachmentRef] = Field(default_factory=list)
    context_refs: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AgentResultStatus = AgentResultStatus.COMPLETED
    agent_id: str
    provider: str
    answer: str = ""
    structured_result: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[Artifact] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    metrics: RunMetrics = Field(default_factory=RunMetrics)


class AgentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: new_id("event"))
    task_id: str
    sequence: int = Field(ge=1)
    type: AgentEventType
    agent_id: str = ""
    timestamp: datetime = Field(default_factory=utc_now)
    data: dict[str, Any] = Field(default_factory=dict)


class CoursePack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str
    course_name: str
    domain_id: str
    version: str
    knowledge_spaces: dict[str, str] = Field(default_factory=dict)
    agents: dict[str, str] = Field(default_factory=dict)
    tools: dict[str, bool] = Field(default_factory=dict)
    evaluation: dict[str, str] = Field(default_factory=dict)


class ProviderAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_name: str
    available: bool
    reason: str | None = None
    publication_status: str
