from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CourseClassification(BaseModel):
    course: Literal[
        "CT",
        "AE",
        "DE",
        "SS",
        "DSP",
        "COMM",
        "RF",
        "EM",
        "INFO",
        "EMBEDDED",
        "IC",
        "UNKNOWN",
    ]
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list, max_length=5)


class IntentClassification(BaseModel):
    intent: Literal[
        "solve_problem",
        "explain_concept",
        "follow_up_question",
        "summarize_knowledge",
        "learning_advice",
        "check_simple_step",
        "lesson_prep",
        "assignment_review",
        "academic_writing",
        "data_analysis",
        "fallback",
        "unknown",
    ]
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list, max_length=5)


class OverallRouteDecision(BaseModel):
    """Small structured contract used by the pre-execution overall router."""

    target_agent_id: str = Field(min_length=1, max_length=80)
    intent: str = Field(min_length=1, max_length=40)
    course_id: str = Field(default="UNKNOWN", max_length=20)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=300)
    reason_codes: list[str] = Field(default_factory=list, max_length=5)
    task_subtype: str = Field(default="", max_length=80)


class AcademicPaperReviewDecision(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=64)
    approved: bool
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=300)


class AcademicPaperReview(BaseModel):
    decisions: list[AcademicPaperReviewDecision] = Field(
        default_factory=list, max_length=50
    )


class AcademicSearchPlan(BaseModel):
    topic_summary: str = Field(min_length=1, max_length=300)
    search_queries: list[str] = Field(min_length=1, max_length=6)
    required_concepts: list[str] = Field(default_factory=list, max_length=12)
    excluded_concepts: list[str] = Field(default_factory=list, max_length=12)
    minimum_results: int = Field(default=4, ge=1, le=20)
    citation_preference: Literal[
        "not_requested", "prefer_high", "required"
    ] = "not_requested"


class QueryRewrite(BaseModel):
    rewritten_query: str = Field(min_length=1, max_length=500)
    keywords: list[str] = Field(min_length=1, max_length=12)
    preserved_constraints: list[str] = Field(min_length=1, max_length=12)


class CircuitPlan(BaseModel):
    method: str = Field(min_length=1, max_length=200)
    steps: list[str] = Field(min_length=1, max_length=12)
    equations_to_build: list[str] = Field(default_factory=list, max_length=12)
    assumptions: list[str] = Field(default_factory=list, max_length=8)
    missing_information: list[str] = Field(default_factory=list, max_length=8)
    needs_tool_verification: bool = True
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"


class LessonPrepDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    learning_objectives: list[str] = Field(min_length=1, max_length=8)
    lesson_flow: list[str] = Field(min_length=1, max_length=12)
    formative_assessment: list[str] = Field(default_factory=list, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)


class AssignmentReviewDraft(BaseModel):
    correctness: Literal["correct", "partially_correct", "incorrect", "uncertain"]
    correct_parts: list[str] = Field(default_factory=list, max_length=10)
    errors: list[str] = Field(default_factory=list, max_length=10)
    feedback: str = Field(min_length=1, max_length=2000)
    review_required: bool = True


class AcademicWritingDraft(BaseModel):
    revised_text: str = Field(min_length=1, max_length=5000)
    revision_notes: list[str] = Field(min_length=1, max_length=10)
    unsupported_claims: list[str] = Field(default_factory=list, max_length=10)
    citation_check_required: bool = True


class DataAnalysisExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_status: Literal["plan", "interpreted", "insufficient_data"]
    method: str = Field(min_length=1, max_length=500)
    steps: list[str] = Field(min_length=1, max_length=12)
    interpretation: str = Field(min_length=1, max_length=3000)
    limitations: list[str] = Field(min_length=1, max_length=10)
    summary: str = Field(default="", max_length=3000)
    findings: list[str] = Field(default_factory=list, max_length=20)
    effect_estimates: list[str] = Field(default_factory=list, max_length=20)
    uncertainty: list[str] = Field(default_factory=list, max_length=20)
    diagnostics: list[str] = Field(default_factory=list, max_length=30)
    robustness: list[str] = Field(default_factory=list, max_length=20)
    conclusion_boundary: str = Field(default="", max_length=3000)


class VisionComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_type: str = Field(min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=80)
    value: str | None = Field(default=None, max_length=80)
    connections: list[str] = Field(default_factory=list, max_length=8)
    certainty: Literal["certain", "uncertain"] = "certain"


class VisionExtraction(BaseModel):
    recognized_text: list[str] = Field(default_factory=list, max_length=30)
    diagram_description: str = Field(min_length=1, max_length=500)
    components: list[VisionComponent] = Field(default_factory=list, max_length=30)
    uncertain_info: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0, le=1)


class InternalAgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    task_type: str
    provider: str
    model: str
    content: str
    structured_result: dict[str, Any] = Field(default_factory=dict)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    elapsed_ms: int = Field(ge=0)
    provider_request_id: str | None = None
