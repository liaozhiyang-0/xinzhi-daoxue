from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class SuiteReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    mode: Literal["offline", "live"]
    started_at: str
    completed_at: str
    filters: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any]
    statistics: dict[str, Any]
    results: list[EvaluationResult]
    estimated_cost: float | None = None
