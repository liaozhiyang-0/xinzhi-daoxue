from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.math_content import MathRichContent


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    FALLBACK = "fallback"


class InputType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"
    MIXED = "mixed"


class ExecutionMode(StrEnum):
    LOCAL = "local"
    DISABLED = "disabled"


class TaskFamily(StrEnum):
    KNOWLEDGE_QA = "KNOWLEDGE_QA"
    ACADEMIC_SOLVING = "ACADEMIC_SOLVING"
    LESSON_PREP = "LESSON_PREP"
    ASSIGNMENT_REVIEW = "ASSIGNMENT_REVIEW"
    ACADEMIC_WRITING = "ACADEMIC_WRITING"
    DATA_ANALYSIS = "DATA_ANALYSIS"
    RESEARCH = "RESEARCH"
    LEARNING_SUPPORT = "LEARNING_SUPPORT"
    TEACHING_ANALYTICS = "TEACHING_ANALYTICS"
    FALLBACK = "FALLBACK"


class CourseCode(StrEnum):
    CT = "CT"
    AE = "AE"
    DE = "DE"
    SS = "SS"
    DSP = "DSP"
    COMM = "COMM"
    RF = "RF"
    EM = "EM"
    INFO = "INFO"
    EMBEDDED = "EMBEDDED"
    IC = "IC"
    UNKNOWN = "UNKNOWN"


class OrchestrationIntent(StrEnum):
    SOLVE_PROBLEM = "solve_problem"
    EXPLAIN_CONCEPT = "explain_concept"
    FOLLOW_UP_QUESTION = "follow_up_question"
    SUMMARIZE_KNOWLEDGE = "summarize_knowledge"
    LEARNING_ADVICE = "learning_advice"
    CHECK_SIMPLE_STEP = "check_simple_step"
    GENERAL_QA = "general_qa"
    LESSON_PREP = "lesson_prep"
    ASSIGNMENT_REVIEW = "assignment_review"
    ACADEMIC_WRITING = "academic_writing"
    DATA_ANALYSIS = "data_analysis"
    ACADEMIC_SEARCH = "academic_search"
    FALLBACK = "fallback"
    UNKNOWN = "unknown"


class FileReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    filename: str = ""
    content_type: str = "application/octet-stream"
    size_bytes: int = Field(default=0, ge=0)
    resource_id: str | None = None
    page_numbers: list[int] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: str
    filename: str
    chapter: str = ""
    page_number: int | None = Field(default=None, ge=1)
    chunk_id: str = ""
    source_ref: str
    title: str = ""
    score: float | None = Field(default=None, ge=0)


class AgentRequestV2(BaseModel):
    """Public orchestration request; converted to the existing task contract."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(default_factory=lambda: f"req_{uuid4().hex}")
    session_id: str | None = None
    user_id: str | None = None
    message: str = Field(default="", max_length=50_000)
    input_type: InputType = InputType.TEXT
    files: list[FileReference] = Field(default_factory=list)
    course_hint: CourseCode | None = None
    intent_hint: OrchestrationIntent | None = None
    scenario_id: str | None = Field(default=None, max_length=64)
    previous_answer_summary: str | None = Field(default=None, max_length=4_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    debug: bool = False

    @model_validator(mode="after")
    def validate_content(self) -> AgentRequestV2:
        self.message = " ".join(self.message.split())
        if not self.message and not self.files:
            raise ValueError("message 与 files 至少提供一项")
        return self


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    session_id: str
    status: ExecutionStatus
    agent_id: str
    course: CourseCode
    intent: OrchestrationIntent
    answer_text: str
    math_content: MathRichContent | None = None
    structured_result: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    trace_id: str
    elapsed_ms: int = Field(ge=0)


class NodeTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_name: str
    start_time: datetime
    end_time: datetime
    elapsed_ms: int = Field(ge=0)
    status: ExecutionStatus
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    model_provider: str = ""
    model_name: str = ""
    workflow_id: str = ""
    retry_count: int = Field(default=0, ge=0)
    error_type: str = ""
    task_id: str = ""
    trace_id: str = ""
    agent_id: str = ""
    course_id: str = ""
    intent: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)
    fallback_used: bool = False
    sanitized_summary: str = ""


class ChatSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    session_id: str
    task_id: str
    trace_id: str
    scenario_id: str | None = None
    status: str = "queued"
    stream_url: str
    result_url: str


class WorkflowStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    execution_mode: ExecutionMode
    enabled: bool
    local_ready: bool
    available: bool
    unavailable_reason: str | None = None
    last_health_check: str = "not_run"
