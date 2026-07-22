from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.math_content import MathRichContent


class AcademicProblem(BaseModel):
    """Course-neutral structured problem at the API/service boundary."""

    model_config = ConfigDict(extra="forbid")

    input_source: str = "text"
    user_intent: str = "solve_problem"
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


class AcademicSolutionResult(BaseModel):
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
