from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.agent import AgentRequest, AttachmentRef, UserRole, utc_now


class TaskRequestContext(BaseModel):
    """Single normalized request view shared by routing, retrieval and mapping."""

    model_config = ConfigDict(extra="allow")

    task_id: str
    request_id: str
    session_id: str
    user_id: str
    user_role: UserRole
    question: str = ""
    normalized_question: str = ""
    course_id: str = ""
    intent: str = "unknown"
    input_mode: str = "text"
    attachments: list[AttachmentRef] = Field(default_factory=list)
    active_course: str = ""
    previous_course: str = ""
    previous_intent: str = ""
    previous_agent: str = ""
    conversation_summary: str = ""
    previous_answer_summary: str = ""
    options: dict[str, Any] = Field(default_factory=dict)
    canonical_input: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def from_agent_request(
        cls, request: AgentRequest, *, input_mode: str
    ) -> TaskRequestContext:
        question = ""
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                question = value.strip()
                break
        options = dict(request.options)
        return cls(
            task_id=request.task_id,
            request_id=str(options.get("request_id", request.task_id)),
            session_id=request.session_id,
            user_id=request.user_id,
            user_role=request.user_role,
            question=question,
            normalized_question=" ".join(question.split()),
            course_id=request.course_id.upper(),
            intent=request.intent.value,
            input_mode=input_mode,
            attachments=list(request.attachments),
            active_course=str(options.get("active_course", request.course_id)).upper(),
            previous_course=str(options.get("previous_course", "")).upper(),
            previous_intent=str(options.get("previous_intent", "")),
            previous_agent=str(options.get("previous_agent", "")),
            conversation_summary=str(options.get("conversation_summary", "")),
            previous_answer_summary=str(options.get("previous_answer_summary", "")),
            options=options,
            canonical_input=dict(request.canonical_input),
        )


class ExecutionTimeBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_budget_ms: int = Field(default=50, ge=1)
    normalization_budget_ms: int = Field(default=20, ge=1)
    retrieval_p95_target_ms: int = Field(default=600, ge=1)
    context_format_budget_ms: int = Field(default=50, ge=1)
    local_total_p95_target_ms: int = Field(default=1000, ge=1)
    cloud_timeout_seconds: float = Field(default=45, gt=0)
    deadline: datetime

    @classmethod
    def create(
        cls,
        *,
        cloud_timeout_seconds: float,
        route_budget_ms: int = 50,
        normalization_budget_ms: int = 20,
        retrieval_p95_target_ms: int = 600,
        context_format_budget_ms: int = 50,
        local_total_p95_target_ms: int = 1000,
    ) -> ExecutionTimeBudget:
        return cls(
            route_budget_ms=route_budget_ms,
            normalization_budget_ms=normalization_budget_ms,
            retrieval_p95_target_ms=retrieval_p95_target_ms,
            context_format_budget_ms=context_format_budget_ms,
            local_total_p95_target_ms=local_total_p95_target_ms,
            cloud_timeout_seconds=cloud_timeout_seconds,
            deadline=utc_now() + timedelta(seconds=cloud_timeout_seconds),
        )

    def remaining_ms(self) -> int:
        return max(0, int((self.deadline - utc_now()).total_seconds() * 1000))


class AgentExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    provider_type: str
    route_status: str
    use_rag: bool
    retrieval_policy_name: str
    retrieval_mode: str
    use_images: bool
    reranker_mode: str
    context_budget: int
    cloud_timeout_seconds: float
    max_retries: int = Field(default=0, ge=0, le=1)
    fallback_type: str
    fallback_handler: str
    input_mode: str
    configured: bool
    published: bool
    debug_enabled: bool
    budget: ExecutionTimeBudget
    skipped_optional_stages: list[str] = Field(default_factory=list)


class AgentResultEnvelope(BaseModel):
    """Forward-compatible public runtime envelope without raw cloud payloads."""

    model_config = ConfigDict(extra="allow")

    status: str = "completed"
    agent_id: str
    agent_version: str = "1.0"
    provider: str
    course_id: str = ""
    intent: str = "unknown"
    answer_text: str = ""
    business_data: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0, le=1)
    assumptions: list[str] = Field(default_factory=list)
    remaining_risks: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    related_images: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    request_id: str = ""
    task_id: str = ""
    retrieval_trace_id: str = ""
    rag_status: str = "disabled"
    evidence_status: str = "insufficient"
    cloud_status: str = "not_run"
    fallback_used: bool = False
    fallback_reason: str = ""
    timings: dict[str, int] = Field(default_factory=dict)
    schema_version: str = "1"
    raw_output_available: bool = False
    mock_used: bool = False
    mock_profile: str = ""
