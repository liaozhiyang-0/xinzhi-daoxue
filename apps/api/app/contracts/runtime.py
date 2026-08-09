from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.agent import AgentRequest, AttachmentRef, UserRole, utc_now
from app.contracts.conversation import ConversationContextBundle
from app.contracts.knowledge import KnowledgeHit, RelatedImage, RetrievalContextPacket


class RAGInteractionMode(StrEnum):
    GROUNDED_GENERATION = "grounded_generation"
    REFERENCE_ONLY = "reference_only"
    METHOD_REFERENCE = "method_reference"
    USER_SOURCES_ONLY = "user_sources_only"
    DATA_CONTEXT_ONLY = "data_context_only"
    NO_RAG = "no_rag"


class RuntimeInputSubmission(BaseModel):
    """User data submitted to a Runtime run waiting for input."""

    model_config = ConfigDict(extra="forbid")

    data: dict[str, Any] = Field(min_length=1, max_length=64)
    expected_state_version: int | None = Field(default=None, ge=1)


class RuntimeReconciliationSubmission(BaseModel):
    """Human acknowledgement for a non-replay-safe in-flight node."""

    model_config = ConfigDict(extra="forbid")

    runtime_run_id: str | None = Field(default=None, max_length=120)
    node_id: str = Field(min_length=1, max_length=100)
    reconciliation_id: str | None = Field(default=None, max_length=240)
    outcome: Literal["succeeded", "failed"]
    facts: dict[str, Any] = Field(default_factory=dict, max_length=64)
    artifact_ids: list[str] = Field(default_factory=list, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=32)
    errors: list[str] = Field(default_factory=list, max_length=32)
    error_code: str = Field(default="", max_length=160)
    expected_state_version: int | None = Field(default=None, ge=1)


class RuntimePlanProposalDecisionSubmission(BaseModel):
    """Explicit approval or rejection of a persisted plan proposal."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=2_000)
    expected_state_version: int | None = Field(default=None, ge=1)


class RuntimeApprovalSubmission(BaseModel):
    """Explicit decision for a Runtime side-effect approval gate."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"] = "approved"
    reason: str = Field(default="", max_length=2_000)
    expected_state_version: int | None = Field(default=None, ge=1)


class RuntimeApprovalAudit(BaseModel):
    """Durable identity and scope attached to a high-risk Runtime decision."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    approver_id: str = Field(min_length=1, max_length=128)
    approver_role: str = Field(min_length=1, max_length=32)
    scope: str = Field(min_length=1, max_length=200)
    state_version: int = Field(ge=1)


class WorkflowContextBundle(BaseModel):
    """One immutable retrieval view shared by mapping, validation and UI."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    task_id: str
    agent_id: str
    course_id: str
    intent: str
    retrieval_policy: str
    rag_mode: RAGInteractionMode
    rag_status: str = "disabled"
    evidence_status: str = "insufficient"
    retrieved_context: str = ""
    evidence_items: list[KnowledgeHit] = Field(default_factory=list)
    related_images: list[RelatedImage] = Field(default_factory=list)
    workflow_evidence_ids: list[str] = Field(default_factory=list)
    used_evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    index_version: str = ""
    trace_id: str = ""
    conversation_context: ConversationContextBundle | None = None

    @classmethod
    def from_packet(
        cls,
        packet: RetrievalContextPacket,
        *,
        request_id: str,
        task_id: str,
        agent_id: str,
        retrieval_policy: str,
        rag_mode: RAGInteractionMode,
        related_images: list[RelatedImage] | None = None,
        conversation_context: ConversationContextBundle | None = None,
    ) -> WorkflowContextBundle:
        evidence_ids = [item.evidence_id for item in packet.evidence]
        return cls(
            request_id=request_id,
            task_id=task_id,
            agent_id=agent_id,
            course_id=packet.course_id,
            intent=packet.intent,
            retrieval_policy=retrieval_policy,
            rag_mode=rag_mode,
            rag_status=packet.rag_status,
            evidence_status=packet.evidence_status,
            retrieved_context=packet.to_retrieved_context(),
            evidence_items=list(packet.evidence),
            related_images=list(related_images or []),
            workflow_evidence_ids=(
                evidence_ids
                if rag_mode == RAGInteractionMode.GROUNDED_GENERATION
                else []
            ),
            warnings=list(packet.warnings),
            index_version=packet.index_version,
            trace_id=packet.retrieval_trace_id,
            conversation_context=conversation_context,
        )


class EvidenceViewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    title: str
    course_id: str
    course_name: str
    chapter: str = ""
    section: str = ""
    content_type: str = "unknown"
    summary: str = ""
    source_ref: str = ""
    related_images: list[RelatedImage] = Field(default_factory=list)
    entered_workflow: bool = False
    used_by_answer: bool = False
    role: str = "supplementary"


class TaskExecutionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: dict[str, Any] = Field(default_factory=dict)
    agent_id: str
    agent_label: str
    rag_mode: RAGInteractionMode
    retrieval_policy: str
    evidence_count: int = Field(default=0, ge=0)
    workflow_evidence_count: int = Field(default=0, ge=0)
    used_evidence_count: int = Field(default=0, ge=0)
    provider: str
    cloud_status: str
    citation_status: str
    fallback: bool = False
    fallback_reason: str = ""
    mock: bool = False
    timings: dict[str, int] = Field(default_factory=dict)


class TaskPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    status_label: str
    source_summary: str
    provider_label: str
    fallback_message: str = ""
    evidence_message: str
    answer_quality_status: str = "not_checked"
    answer_quality_message: str = ""
    requires_review: bool = False
    generation_complete: bool = True
    execution_steps: list[dict[str, str]] = Field(default_factory=list)


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
    previous_business_summary: str = ""
    previous_evidence_ids: list[str] = Field(default_factory=list)
    recent_messages: list[dict[str, Any]] = Field(default_factory=list)
    active_memories: list[dict[str, Any]] = Field(default_factory=list)
    working_state: dict[str, Any] = Field(default_factory=dict)
    task_subtype: str = ""
    has_attachment: bool = False
    has_image: bool = False
    has_rubric: bool = False
    has_student_answer: bool = False
    has_data_summary: bool = False
    has_source_text: bool = False
    has_trusted_sources: bool = False
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
            previous_business_summary=str(options.get("previous_business_summary", "")),
            previous_evidence_ids=[
                str(item) for item in options.get("previous_evidence_ids", [])
            ][:10],
            recent_messages=[
                dict(item)
                for item in options.get("recent_messages", [])
                if isinstance(item, dict)
            ][:12],
            active_memories=[
                dict(item)
                for item in options.get("active_memories", [])
                if isinstance(item, dict)
            ][:8],
            working_state=dict(options.get("working_state", {})),
            task_subtype=str(options.get("task_subtype", "")),
            has_attachment=bool(request.attachments),
            has_image=any(
                item.content_type.startswith("image/") for item in request.attachments
            ),
            has_rubric=bool(
                request.canonical_input.get("rubric") or options.get("rubric")
            ),
            has_student_answer=bool(
                request.canonical_input.get("student_answer")
                or options.get("student_answer")
            ),
            has_data_summary=bool(
                request.canonical_input.get("data_description")
                or request.canonical_input.get("provided_results")
                or options.get("data_description")
                or options.get("provided_results")
            ),
            has_source_text=bool(
                request.canonical_input.get("source_text") or options.get("source_text")
            ),
            has_trusted_sources=bool(
                request.canonical_input.get("trusted_sources")
                or options.get("trusted_sources")
            ),
            options=options,
            canonical_input=dict(request.canonical_input),
        )


class MaterialExtractionResult(BaseModel):
    """Deterministic, lossless extraction metadata used by routing and adapters."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str = ""
    materials: dict[str, Any] = Field(default_factory=dict)
    source_fields: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0, le=1)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    attachment_types: list[str] = Field(default_factory=list)
    latency_ms: float = Field(default=0.0, ge=0)


class AgentValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_status: str
    validation_issues: list[str] = Field(default_factory=list)
    corrected_fields: list[str] = Field(default_factory=list)
    response_usable: bool = True
    result_status: str = "accepted"
    latency_ms: float = Field(default=0.0, ge=0)


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
    rag_mode: RAGInteractionMode = RAGInteractionMode.NO_RAG
    rag_used: bool = False
    evidence_count: int = Field(default=0, ge=0)
    context_injected: bool = False
    availability_checks: dict[str, bool] = Field(default_factory=dict)


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
