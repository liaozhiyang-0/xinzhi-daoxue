from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.math_content import MathRichContent


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
    DISPATCH = "dispatch"
    SOLVING = "solving"
    LEARNING = "learning"
    TEACHING = "teaching"
    RESEARCH = "research"
    INFRASTRUCTURE = "infrastructure"


class Intent(StrEnum):
    UNKNOWN = "unknown"
    FOLLOW_UP_QUESTION = "follow_up_question"
    SOLVE_PROBLEM = "solve_problem"
    EXPLAIN_CONCEPT = "explain_concept"
    VERIFY_ANSWER = "verify_answer"
    CHECK_USER_SOLUTION = "check_user_solution"
    GENERAL_QA = "general_qa"
    SUMMARIZE_KNOWLEDGE = "summarize_knowledge"
    LEARNING_ADVICE = "learning_advice"
    CHECK_SIMPLE_STEP = "check_simple_step"
    LESSON_PREP = "lesson_prep"
    ASSIGNMENT_REVIEW = "assignment_review"
    ACADEMIC_WRITING = "academic_writing"
    DATA_ANALYSIS = "data_analysis"


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
    ROUTE_SELECTED = "route.selected"
    ROUTE_UNSUPPORTED = "route.unsupported"
    KNOWLEDGE_QUERY_NORMALIZED = "knowledge.query_normalized"
    KNOWLEDGE_RETRIEVED = "knowledge.retrieved"
    KNOWLEDGE_CONTEXT_BUILT = "knowledge.context_built"
    KNOWLEDGE_INSUFFICIENT = "knowledge.insufficient"
    ANSWER_RETRIEVAL_ONLY_CREATED = "answer.retrieval_only_created"
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
    retrieval_latency_ms: int | None = Field(default=None, ge=0)
    context_latency_ms: int | None = Field(default=None, ge=0)
    citation_latency_ms: int | None = Field(default=None, ge=0)
    fallback_used: bool = False
    error_type: str | None = None
    total_latency_ms: int | None = Field(default=None, ge=0)
    first_token_latency_ms: int | None = Field(default=None, ge=0)
    route_latency_ms: int | None = Field(default=None, ge=0)
    rerank_latency_ms: int | None = Field(default=None, ge=0)
    model_latency_ms: int | None = Field(default=None, ge=0)
    verification_latency_ms: int | None = Field(default=None, ge=0)
    presentation_latency_ms: int | None = Field(default=None, ge=0)
    retry_count: int = Field(default=0, ge=0)
    provider_used: str = ""
    degraded_reason: str = ""
    quality_status: str = "not_checked"
    final_confidence: float | None = Field(default=None, ge=0, le=1)
    message_count: int = Field(default=0, ge=0)
    recent_message_count: int = Field(default=0, ge=0)
    older_message_count: int = Field(default=0, ge=0)
    session_summary_used: bool = False
    summary_version: int = Field(default=0, ge=0)
    context_estimated_tokens: int = Field(default=0, ge=0)
    context_budget_tokens: int = Field(default=0, ge=0)
    context_budget_ratio: float = Field(default=0, ge=0)
    context_trimmed: bool = False
    compaction_count: int = Field(default=0, ge=0)
    memory_enabled: bool = False
    memory_retrieval_count: int = Field(default=0, ge=0)
    memory_write_count: int = Field(default=0, ge=0)
    memory_candidate_count: int = Field(default=0, ge=0)
    context_cache_hit: bool = False
    context_cache_backend: str = "none"
    context_build_latency_ms: float = Field(default=0, ge=0)
    compaction_latency_ms: float = Field(default=0, ge=0)
    memory_latency_ms: float = Field(default=0, ge=0)
    prompt_cache_supported: bool = False
    prompt_cache_read_tokens: int = Field(default=0, ge=0)
    prompt_cache_write_tokens: int = Field(default=0, ge=0)


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
    math_content: MathRichContent | None = None
    structured_result: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[Artifact] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    rag_status: str = "disabled"
    evidence_status: str = "insufficient"
    related_images: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_trace_id: str = ""
    retrieval_latency_ms: int = Field(default=0, ge=0)
    index_version: str = ""
    agent_version: str = "1.0"
    course_id: str = ""
    intent: str = "unknown"
    business_data: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    remaining_risks: list[str] = Field(default_factory=list)
    request_id: str = ""
    trace_id: str = ""
    task_id: str = ""
    cloud_status: str = "not_run"
    fallback_used: bool = False
    fallback_reason: str = ""
    timings: dict[str, int] = Field(default_factory=dict)
    schema_version: str = "1"
    raw_output_available: bool = False
    mock_used: bool = False
    mock_profile: str = ""


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
