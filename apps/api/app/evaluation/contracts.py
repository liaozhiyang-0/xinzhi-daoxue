from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EvaluationMode = Literal[
    "offline",
    "live",
    "local_deterministic",
    "local_mock",
    "real_model",
]


class EvaluationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["synthetic", "licensed", "private", "public"] = "synthetic"
    source_name: str = ""
    license_or_authorization: str = ""
    imported_at: str | None = None
    publishable: bool = True


class EvaluationRubric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routing: float = Field(default=1, ge=0)
    structure: float = Field(default=1, ge=0)
    reasoning: float = Field(default=1, ge=0)
    numeric: float = Field(default=1, ge=0)
    units: float = Field(default=1, ge=0)
    citations: float = Field(default=1, ge=0)
    safety: float = Field(default=1, ge=0)
    teaching_foundation: float = Field(default=0, ge=0)


class FailureStage(StrEnum):
    INPUT_NORMALIZATION = "input_normalization"
    ROUTING = "routing"
    COURSE_PACK_RESOLUTION = "course_pack_resolution"
    MULTIMODAL_EXTRACTION = "multimodal_extraction"
    PROBLEM_STRUCTURING = "problem_structuring"
    SOLVABILITY = "solvability"
    CAPABILITY_SELECTION = "capability_selection"
    RETRIEVAL = "retrieval"
    PLANNING = "planning"
    GENERATION = "generation"
    TOOL_EXECUTION = "tool_execution"
    VERIFICATION = "verification"
    CORRECTION = "correction"
    CITATION_VALIDATION = "citation_validation"
    FINALIZATION = "finalization"
    TIMEOUT = "timeout"
    PROVIDER = "provider"
    UNKNOWN = "unknown"


class EvaluationErrorType(StrEnum):
    ROUTE_MISMATCH = "route_mismatch"
    COURSE_MISMATCH = "course_mismatch"
    AGENT_MISMATCH = "agent_mismatch"
    STRUCTURE_MISSING = "structure_missing"
    PATH_MISMATCH = "path_mismatch"
    STATUS_MISMATCH = "status_mismatch"
    KEYWORD_MISSING = "keyword_missing"
    STEP_MISSING = "step_missing"
    FORBIDDEN_CLAIM = "forbidden_claim"
    NUMERIC_MISMATCH = "numeric_mismatch"
    TOOL_DISABLED = "tool_disabled"
    TOOL_NOT_SELECTED = "tool_not_selected"
    TOOL_NOT_EXECUTED = "tool_not_executed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    TOOL_CONFLICT = "tool_conflict"
    FORBIDDEN_TOOL = "forbidden_tool"
    CITATION_MISSING = "citation_missing"
    CITATION_INVALID = "citation_invalid"
    INSUFFICIENT_HANDLING = "insufficient_handling"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    EXECUTION_ERROR = "execution_error"
    TEACHING_FOUNDATION_MISMATCH = "teaching_foundation_mismatch"


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    course: str
    task_family: str
    intent: str
    problem_type: str | None = None
    difficulty: Literal["easy", "medium", "hard", "boundary"] = "medium"
    input_type: str = "text"
    message: str
    file_refs: list[dict[str, Any]] = Field(default_factory=list)
    structured_input: dict[str, Any] = Field(default_factory=dict)
    task_options: dict[str, Any] = Field(default_factory=dict)
    expected_agent: str
    expected_course_pack: str | None = None
    expected_execution_paths: list[str] = Field(default_factory=list)
    expected_statuses: list[str] = Field(default_factory=lambda: ["success", "partial"])
    reference_answer: str | None = None
    reference_values: dict[str, float | int | str] = Field(default_factory=dict)
    required_keywords: list[str] = Field(default_factory=list)
    required_equations: list[str] = Field(default_factory=list)
    required_steps: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    expected_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    expected_citations: bool | None = None
    min_citation_count: int | None = Field(default=None, ge=0)
    allowed_assumptions: list[str] = Field(default_factory=list)
    required_warnings: list[str] = Field(default_factory=list)
    numeric_tolerance: float | None = Field(default=None, gt=0)
    timeout_seconds: int = Field(default=180, ge=1, le=600)
    tags: list[str] = Field(default_factory=list)
    source: str | None = None
    notes: str | None = None
    input_source: str = "synthetic"
    expected_route: dict[str, Any] = Field(default_factory=dict)
    required_knowledge_points: list[str] = Field(default_factory=list)
    forbidden_errors: list[str] = Field(default_factory=list)
    reference_solution: dict[str, Any] = Field(default_factory=dict)
    tolerance: dict[str, float] = Field(default_factory=dict)
    rubric: EvaluationRubric = Field(default_factory=EvaluationRubric)
    judge_type: Literal["rule", "human", "model", "hybrid"] = "rule"
    evidence_requirements: dict[str, Any] = Field(default_factory=dict)
    provenance: EvaluationProvenance = Field(default_factory=EvaluationProvenance)
    official_scoring: bool = False
    student_attempt_parsed: bool | None = None
    teaching_mode_respected: bool | None = None
    solution_packet_valid: bool | None = None
    skill_mapping_valid: bool | None = None
    evidence_packet_valid: bool | None = None
    error_pool_match_valid: bool | None = None
    answer_disclosure_compliant: bool | None = None
    requires_manual_review: bool | None = None
    expected_teaching_execution_path: str | None = None
    verification_report_valid: bool | None = None
    expected_verification_status: str | None = None
    expected_error_type: str | None = None
    expected_hint_level: str | None = None
    expected_disclosure_mode: str | None = None
    next_check_valid: bool | None = None
    solution_packet_reused: bool | None = None
    full_solution_disclosed: bool | None = None
    no_additional_model_calls: bool | None = None
    first_confirmed_error_found: bool | None = None
    cross_user_isolated: bool | None = None
    expected_skill_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_expectations(self) -> EvaluationCase:
        valid_paths = {"FAST", "STANDARD", "HIGH_RISK", "CONDITIONAL", "FALLBACK"}
        invalid = set(self.expected_execution_paths) - valid_paths
        if invalid:
            raise ValueError(f"无效执行路径: {', '.join(sorted(invalid))}")
        if self.min_citation_count is not None and self.expected_citations is False:
            raise ValueError("expected_citations=false时不能设置min_citation_count")
        return self


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    status: Literal["passed", "failed", "error", "timeout", "cached"]
    route_passed: bool
    course_passed: bool
    agent_passed: bool
    structure_passed: bool
    execution_path_passed: bool
    tools_passed: bool
    answer_passed: bool
    citations_passed: bool
    safety_passed: bool
    total_score: float = Field(ge=0, le=100)
    expected: dict[str, Any] = Field(default_factory=dict)
    actual: dict[str, Any] = Field(default_factory=dict)
    missing_keywords: list[str] = Field(default_factory=list)
    missing_steps: list[str] = Field(default_factory=list)
    forbidden_claims_found: list[str] = Field(default_factory=list)
    numeric_comparisons: list[dict[str, Any]] = Field(default_factory=list)
    tool_mismatches: list[dict[str, Any]] = Field(default_factory=list)
    failure_stage: FailureStage | None = None
    error_types: list[EvaluationErrorType] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: int = Field(default=0, ge=0)
    model_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str | None = None
    cache_key: str | None = None
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    judge_type: str = "rule"
    evaluation_mode: str = "offline"


class EvaluationRunMetadata(BaseModel):
    """Reproducibility metadata that contains no prompts or answers."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    run_id: str = ""
    case_count: int = Field(default=0, ge=0)
    case_ids_sha256: str = ""
    case_catalog_sha256: str = ""
    case_catalog_content_sha256: str = ""
    case_catalog_content_version: Literal[
        "canonical_evaluation_case_payloads.v1"
    ] | None = None
    case_source_files_sha256: str = ""
    case_source_files_version: Literal["evaluation_case_source_files.v1"] | None = None
    case_attachment_manifest_sha256: str = ""
    case_attachment_manifest_version: Literal[
        "evaluation_case_attachments.v1"
    ] | None = None
    case_attachment_count: int = Field(default=0, ge=0)
    filters_sha256: str = ""
    implementation_fingerprint: str = ""
    execution_channel: Literal["in_process_http"] = "in_process_http"
    model_trace_retention: Literal["bounded_in_memory_metadata_only"] = (
        "bounded_in_memory_metadata_only"
    )
    raw_prompts_stored: Literal[False] = False


class SuiteReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    mode: EvaluationMode
    started_at: str
    completed_at: str
    filters: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any]
    statistics: dict[str, Any]
    results: list[EvaluationResult]
    estimated_cost: float | None = None
    run_metadata: EvaluationRunMetadata = Field(default_factory=EvaluationRunMetadata)


class EvaluationReportSummary(BaseModel):
    """Safe report view for teacher/admin clients; never includes case results."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    report_kind: Literal["summary"] = "summary"
    schema_version: str
    mode: EvaluationMode
    started_at: str
    completed_at: str
    filters: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any]
    statistics: dict[str, Any]
    run_metadata: EvaluationRunMetadata
    result_status_counts: dict[str, int] = Field(default_factory=dict)
    raw_results_included: Literal[False] = False
    data_boundary: list[str] = Field(
        default_factory=lambda: [
            "summary_only_no_case_answers",
            "synthetic_or_local_evaluation_not_learning_effectiveness",
            "model_trace_is_bounded_process_memory",
        ]
    )
