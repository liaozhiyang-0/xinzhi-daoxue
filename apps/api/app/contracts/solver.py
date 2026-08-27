from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.math_content import MathRichContent


class SolverTaskMode(StrEnum):
    SOLVE = "SOLVE"
    REVIEW = "REVIEW"
    VERIFY = "VERIFY"


class ProblemComplexity(StrEnum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    HIGH_RISK = "high_risk"


class FallbackReason(StrEnum):
    UNSUPPORTED_COURSE = "unsupported_course"
    UNSUPPORTED_TASK = "unsupported_task"
    LOW_EXTRACTION_CONFIDENCE = "low_extraction_confidence"
    CRITICAL_INPUT_MISSING = "critical_input_missing"
    PROFESSIONAL_VALIDATION_FAILED = "professional_validation_failed"
    PRIMARY_MODEL_TIMEOUT = "primary_model_timeout"
    PRIMARY_MODEL_ERROR = "primary_model_error"
    HIGH_RISK_PROBLEM = "high_risk_problem"


class AcademicProblem(BaseModel):
    """Course-neutral structured problem at the API/service boundary."""

    model_config = ConfigDict(extra="forbid")

    input_source: str = "text"
    user_intent: str = "solve_problem"
    task_mode: SolverTaskMode = SolverTaskMode.SOLVE
    student_answer: str | None = None
    verify_target: str | None = None
    course: str = "UNKNOWN"
    chapter: str | None = None
    topic: str | None = None
    problem_type: str | None = None
    problem_text: str
    known_conditions: list[dict[str, Any]] = Field(default_factory=list)
    target_quantities: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[dict[str, Any]] = Field(default_factory=list)
    reference_conventions: list[dict[str, Any]] = Field(default_factory=list)
    equations_given: list[str] = Field(default_factory=list)
    code_given: str | None = None
    tables_given: list[dict[str, Any]] = Field(default_factory=list)
    figures_given: list[dict[str, Any]] = Field(default_factory=list)
    source_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    uncertain_info: list[dict[str, Any]] = Field(default_factory=list)
    critical_missing_info: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_keywords: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    structure_status: str = "partial"
    can_continue: bool = True
    extraction_confidence: float = Field(default=0.5, ge=0, le=1)


class ProfessionalConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_type: str
    message: str
    affected_step: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_correction: str = ""


class ProfessionalValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool = True
    validator: str
    analysis_mode: str = "unknown"
    conflicts: list[ProfessionalConflict] = Field(default_factory=list)
    affected_steps: list[str] = Field(default_factory=list)
    suggested_corrections: list[str] = Field(default_factory=list)
    requires_regeneration: bool = False


class SolverReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_mode: Literal["REVIEW", "VERIFY"]
    student_answer_status: Literal[
        "correct", "partially_correct", "incorrect", "uncertain"
    ] = "uncertain"
    first_error_step: str = ""
    error_type: Literal[
        "concept",
        "condition",
        "formula",
        "sign",
        "calculation",
        "unit",
        "logic",
        "conclusion",
        "none",
        "unknown",
    ] = "unknown"
    why_incorrect: str = ""
    corrected_step: str = ""
    downstream_impact: str = ""
    remaining_valid_steps: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)


class SolverNodeTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    elapsed_ms: int = Field(default=0, ge=0)
    status: str
    model: str | None = None
    error_type: str | None = None


class SolverObservability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = ""
    course: str = ""
    task_mode: SolverTaskMode = SolverTaskMode.SOLVE
    complexity: ProblemComplexity = ProblemComplexity.MEDIUM
    route_path: list[str] = Field(default_factory=list)
    fallback_reason: FallbackReason | None = None
    fallback_count: int = Field(default=0, ge=0, le=2)
    model_call_count: int = Field(default=0, ge=0)
    rag_call_count: int = Field(default=0, ge=0)
    vision_call_count: int = Field(default=0, ge=0)
    verification_triggered: bool = False
    verification_reason: str | None = None
    time_budget_exhausted: bool = False
    deadline_remaining_ms: int = Field(default=0, ge=0)
    partial_result_available: bool = False
    verification_skipped_reason: str | None = None
    node_timings: list[SolverNodeTiming] = Field(default_factory=list)


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    status: Literal["success", "failed", "skipped", "disabled"]
    result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: int = Field(default=0, ge=0)
    deterministic: bool = True


class VerificationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    issue_type: Literal[
        "equation",
        "calculation",
        "unit",
        "direction",
        "condition",
        "logic",
        "evidence",
        "citation",
        "tool_conflict",
    ]
    location: str | None = None
    primary_value: str | None = None
    verified_value: str | None = None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    evidence: list[str] = Field(default_factory=list)
    correction_instruction: str | None = None
    deterministic: bool = False


class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_status: Literal["pass", "conflict", "uncertain", "failed"]
    issues: list[VerificationIssue] = Field(default_factory=list)
    requires_patch: bool = False
    requires_fallback: bool = False
    confidence: float = Field(default=0, ge=0, le=1)


class SolutionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_section: str
    target_step_id: str | None = None
    operation: Literal["replace", "append", "remove", "mark_uncertain"]
    old_content_summary: str | None = None
    new_content: str
    reason: str
    verification_issue_ids: list[str] = Field(default_factory=list)


class SolverFinalAnswer(BaseModel):
    """Structured companion to the legacy plain-text ``final_answer`` field."""

    model_config = ConfigDict(extra="forbid")

    value: str = ""
    unit: str | None = None
    conclusion: str = ""
    confidence: float = Field(default=0, ge=0, le=1)


class SolverVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["pass", "partial", "fail", "not_checked"] = "not_checked"
    checks: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class SolverKnowledgeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_status: Literal[
        "valid",
        "partially_supported",
        "unsupported",
        "stale",
        "invalid_locator",
        "missing_source",
        "not_applicable",
    ] = "not_applicable"
    cited_chunk_ids: list[str] = Field(default_factory=list)
    unsupported_conclusions: list[str] = Field(default_factory=list)


class QualityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    status: Literal["pass", "fail", "warn", "not_applicable"]
    message: str
    deterministic: bool = True


class QualityGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["pass", "partial", "fail"]
    checks: list[QualityCheck] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    applied_course_rules: list[str] = Field(default_factory=list)


class SolutionStepV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    title: str
    content: str
    skill_ids: list[str] = Field(default_factory=list)
    expression: str | None = None
    result: str | None = None
    unit: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    tool_output_refs: list[str] = Field(default_factory=list)
    step_source: Literal[
        "solver_execution", "pedagogical", "tool", "adapted_unknown"
    ]
    confidence: float | None = Field(default=None, ge=0, le=1)


class SolutionPacketV1(BaseModel):
    """Teaching adapter output; it does not replace the user-facing answer."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    course_id: str
    problem_type: str | None = None
    problem_summary: str = ""
    givens: list[dict[str, Any]] = Field(default_factory=list)
    targets: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    reference_directions: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)
    steps: list[SolutionStepV1] = Field(default_factory=list)
    final_answer: dict[str, Any] | str | None = None
    units: list[str] = Field(default_factory=list)
    common_errors: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    tool_outputs: list[dict[str, Any]] = Field(default_factory=list)
    mapping_status: Literal["mapped", "partial", "unavailable"]
    warnings: list[str] = Field(default_factory=list)


class SolverResult(BaseModel):
    """Unified solver result while retaining the stable v1 response fields.

    ``final_answer`` intentionally remains text because it is consumed by the
    current API and Workspace. New consumers should prefer
    ``final_answer_detail`` for machine-readable output.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "partial", "failed", "unsupported"]
    course: str
    problem_type: str = "unknown"
    problem_summary: str
    assumptions: list[str] = Field(default_factory=list)
    known_conditions: list[dict[str, Any]] = Field(default_factory=list)
    target_quantities: list[dict[str, Any]] = Field(default_factory=list)
    solution_method: str = ""
    solution_steps: list[dict[str, Any]] = Field(default_factory=list)
    key_equations: list[str] = Field(default_factory=list)
    intermediate_results: list[dict[str, Any]] = Field(default_factory=list)
    final_answer: str = ""
    math_content: MathRichContent | None = None
    tool_verification: list[dict[str, Any]] = Field(default_factory=list)
    consistency_status: str = "not_checked"
    remaining_risks: list[str] = Field(default_factory=list)
    knowledge_points: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    learning_suggestions: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    execution_path: Literal[
        "FAST", "STANDARD", "HIGH_RISK", "CONDITIONAL", "FALLBACK"
    ] = "STANDARD"
    fallback_used: bool = False
    fallback_target: str | None = None
    verification_report: VerificationReport | None = None
    patches: list[SolutionPatch] = Field(default_factory=list)
    patch_count: int = Field(default=0, ge=0)
    patched_sections: list[str] = Field(default_factory=list)
    remaining_issues: list[str] = Field(default_factory=list)
    final_answer_detail: SolverFinalAnswer | None = None
    verification: SolverVerification | None = None
    knowledge_evidence: SolverKnowledgeEvidence | None = None
    quality_gate: QualityGateResult | None = None


# Backward-compatible public name used by existing providers and tests.
AcademicSolutionResult = SolverResult
