from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LearningAction = Literal[
    "add_wrong_answer",
    "get_hint",
    "check_answer",
    "generate_variant",
    "related_knowledge",
    "mark_mastered",
    "request_more_hint",
    "submit_check_response",
    "switch_to_direct_answer",
    "submit_attempt_revision",
    "start_retest",
    "complete_retest",
    "dismiss_retest",
]


class TeachingMode(StrEnum):
    DIRECT_ANSWER = "direct_answer"
    GUIDED_LEARNING = "guided_learning"
    CHECK_MY_WORK = "check_my_work"
    REVIEW = "review"


class StudentAttemptStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str | None = Field(default=None, max_length=128)
    sequence: int | None = Field(default=None, ge=1)
    content: str = Field(min_length=1, max_length=4_000)
    expression: str | None = Field(default=None, max_length=2_000)
    claimed_result: str | None = Field(default=None, max_length=2_000)
    unit: str | None = Field(default=None, max_length=64)
    reference_direction: str | None = Field(default=None, max_length=500)


class StudentAttempt(BaseModel):
    """Text-first attempt carried by Task input, never by long-term Memory."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(default="", max_length=10_000)
    final_answer: str | None = Field(default=None, max_length=2_000)
    steps: list[StudentAttemptStep] = Field(default_factory=list, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    attachment_ids: list[str] = Field(default_factory=list, max_length=20)
    version: Literal["v1"] = "v1"


class StudentAttemptStatus(StrEnum):
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    MANUAL_REVIEW = "manual_review"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class StudentAttemptV2(BaseModel):
    """Durable, user-owned attempt version; internal reports stay in storage."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["v2"] = "v2"
    attempt_id: str
    user_id: str
    session_id: str
    task_id: str
    source_task_id: str
    attempt_sequence: int = Field(ge=1)
    revision_of_attempt_id: str | None = None
    raw_text: str = Field(default="", max_length=10_000)
    final_answer: str | None = Field(default=None, max_length=2_000)
    steps: list[StudentAttemptStep] = Field(default_factory=list, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    teaching_mode: TeachingMode
    hint_level_used: str | None = None
    full_solution_seen: bool = False
    verification_status: str | None = None
    verification_report_ref: str | None = None
    submitted_at: datetime
    status: StudentAttemptStatus


class FeedbackUptakeStatus(StrEnum):
    APPLIED_CORRECTLY = "applied_correctly"
    APPLIED_INCORRECTLY = "applied_incorrectly"
    PARTIALLY_APPLIED = "partially_applied"
    NOT_APPLIED = "not_applied"
    INDETERMINATE = "indeterminate"
    NOT_APPLICABLE = "not_applicable"


class FeedbackUptakeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    user_id: str
    session_id: str
    source_task_id: str
    previous_attempt_id: str
    current_attempt_id: str
    hint_level: str | None
    hint_source: str | None
    target_step_id: str | None
    target_skill_ids: list[str] = Field(default_factory=list)
    student_modified: bool
    modified_step_ids: list[str] = Field(default_factory=list)
    target_step_modified: bool
    previous_verification_status: str | None
    current_verification_status: str | None
    status: FeedbackUptakeStatus
    modification_correct: bool | None
    time_to_revision_seconds: int | None = Field(default=None, ge=0)
    evaluation_method: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class LearningMetricsRead(BaseModel):
    """Aggregated learning telemetry for teacher/admin review.

    Counts are operational telemetry, not learner accuracy or causal impact
    measurements. Student identifiers are intentionally excluded.
    """

    version: Literal["v1"] = "v1"
    course_id: str | None = None
    window_start: datetime
    window_end: datetime
    data_source: Literal["local_database"] = "local_database"
    attempt_count: int = Field(ge=0)
    attempt_status_counts: dict[str, int] = Field(default_factory=dict)
    verification_status_counts: dict[str, int] = Field(default_factory=dict)
    manual_review_count: int = Field(ge=0)
    feedback_uptake_event_count: int = Field(ge=0)
    feedback_uptake_status_counts: dict[str, int] = Field(default_factory=dict)
    feedback_uptake_determinate_count: int = Field(ge=0)
    feedback_uptake_determinate_rate: float | None = Field(
        default=None, ge=0, le=1
    )
    feedback_uptake_applied_correctly_count: int = Field(ge=0)
    feedback_uptake_correct_rate: float | None = Field(default=None, ge=0, le=1)
    retest_count: int = Field(ge=0)
    retest_status_counts: dict[str, int] = Field(default_factory=dict)
    row_limit: int = Field(ge=1)
    truncated: bool = False
    data_quality_warnings: list[str] = Field(default_factory=list)


class MasteryEvidenceType(StrEnum):
    INDEPENDENT_CORRECT = "independent_correct"
    H0_H1_CORRECT = "h0_h1_correct"
    H2_CORRECT = "h2_correct"
    FULL_SOLUTION_SEEN = "full_solution_seen"
    FEEDBACK_APPLIED_CORRECTLY = "feedback_applied_correctly"
    FEEDBACK_NOT_APPLIED = "feedback_not_applied"
    VERIFIED_ERROR = "verified_error"
    MANUAL_REVIEW = "manual_review"
    DELAYED_RETEST_CORRECT = "delayed_retest_correct"
    DELAYED_RETEST_INCORRECT = "delayed_retest_incorrect"


class MasteryEvidenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    user_id: str
    skill_id: str
    source_task_id: str
    attempt_id: str | None
    evidence_type: MasteryEvidenceType
    verified: bool
    evidence_strength: float = Field(ge=0, le=1)
    mastery_delta: float = Field(ge=-1, le=1)
    reason_code: str
    created_at: datetime


class RetestPlanStatus(StrEnum):
    SCHEDULED = "scheduled"
    DUE = "due"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class RetestPlanV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retest_plan_id: str
    user_id: str
    skill_id: str
    source_task_id: str
    source_attempt_id: str | None
    interval_days: int = Field(ge=1)
    due_at: datetime
    status: RetestPlanStatus
    reason_code: str
    generated_problem_id: str | None
    completed_task_id: str | None
    result: str | None
    created_at: datetime
    updated_at: datetime


class TeachingExecutionPath(StrEnum):
    DIRECT = "direct"
    GUIDED = "guided"
    CHECK = "check"


class TeachingExecutionPlanV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    path: TeachingExecutionPath
    require_solver: bool
    reuse_solution_packet: bool
    require_student_verification: bool
    require_hint: bool
    require_next_check: bool
    maximum_disclosure_level: Literal["H0", "H1", "H2", "H5"]
    model_call_budget: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class StepVerificationStatus(StrEnum):
    VERIFIED_CORRECT = "verified_correct"
    VERIFIED_INCORRECT = "verified_incorrect"
    HEURISTIC_CORRECT = "heuristic_correct"
    HEURISTIC_INCORRECT = "heuristic_incorrect"
    MANUAL_REVIEW = "manual_review"
    NOT_CHECKED = "not_checked"


class StudentErrorType(StrEnum):
    UNIT_MISSING = "unit_missing"
    UNIT_INCOMPATIBLE = "unit_incompatible"
    NUMERIC_ERROR = "numeric_error"
    SIGN_ERROR = "sign_error"
    REFERENCE_DIRECTION_ERROR = "reference_direction_error"
    FORMULA_MISMATCH = "formula_mismatch"
    BOOLEAN_INEQUIVALENCE = "boolean_inequivalence"
    CONDITION_MISSING = "condition_missing"
    VALID_BUT_NONOPTIMAL = "valid_but_nonoptimal"
    UNKNOWN = "unknown"


class StepVerificationV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_step_id: str | None = None
    matched_solution_step_id: str | None = None
    skill_ids: list[str] = Field(default_factory=list)
    status: StepVerificationStatus
    error_type: StudentErrorType | None = None
    message: str | None = None
    repair_hint_key: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    verification_method: str
    tool_evidence: list[dict[str, Any]] = Field(default_factory=list)


class VerificationReportV1(BaseModel):
    """Finite deterministic/heuristic checks, not a universal first-error system."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    overall_status: Literal[
        "verified_correct",
        "verified_incorrect",
        "heuristic",
        "manual_review",
        "not_checked",
    ]
    supported_scope: list[str] = Field(default_factory=list)
    step_results: list[StepVerificationV1] = Field(default_factory=list)
    first_confirmed_error_step: str | None = None
    manual_review_required: bool = False
    verified_final_answer: bool | None = None
    warnings: list[str] = Field(default_factory=list)


class HintDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    hint_status: Literal["available", "unavailable"] = "available"
    hint_level: Literal["H0", "H1", "H2"]
    target_skill_ids: list[str] = Field(default_factory=list)
    target_step_id: str | None = None
    hint_text: str
    source: str
    disclosure_checked: bool = False
    next_action: str


class AnswerDisclosureMode(StrEnum):
    FULL = "full"
    WITHHOLD_FINAL = "withhold_final"
    NEXT_STEP_ONLY = "next_step_only"


class AnswerDisclosurePolicyV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    mode: AnswerDisclosureMode
    maximum_hint_level: Literal["H0", "H1", "H2", "H5"]
    reveal_final_answer: bool
    reveal_intermediate_results: bool
    reveal_complete_solution_packet: bool
    source: str


class NextCheckQuestionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    question_id: str
    question_text: str
    target_skill_ids: list[str] = Field(default_factory=list)
    target_solution_step_id: str | None = None
    expected_response_type: str
    source: str
    answer_key_internal: str | None = None


class LearnerKnowledgeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str
    knowledge_point: str
    mastery_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    correct_count: int = Field(ge=0)
    incorrect_count: int = Field(ge=0)
    hint_count: int = Field(ge=0)


class AnswerReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["correct", "partially_correct", "incorrect", "insufficient"]
    aligned_steps: list[dict[str, Any]] = Field(default_factory=list)
    first_error: dict[str, Any] | None = None
    error_types: list[str] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
    mastery_delta: float = Field(ge=-1, le=1)


class PracticeProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "unsupported", "invalid"]
    problem_text: str = ""
    known_conditions: list[dict[str, Any]] = Field(default_factory=list)
    target_quantities: list[dict[str, Any]] = Field(default_factory=list)
    reference_answer: dict[str, Any] = Field(default_factory=dict)
    validation_checks: list[dict[str, Any]] = Field(default_factory=list)
    source_task_id: str


class LearningActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_task_id: str
    user_id: str
    action: LearningAction
    idempotency_key: str = Field(min_length=8, max_length=128)
    student_answer: str = Field(default="", max_length=10_000)
    payload: dict[str, Any] = Field(default_factory=dict)


class LearningRuntimeApprovalRequest(BaseModel):
    """Approve a teaching interaction Runtime waiting for teacher review."""

    model_config = ConfigDict(extra="forbid")

    expected_state_version: int | None = Field(default=None, ge=1)


LearningRuntimeControlAction = Literal["approve", "pause", "resume", "input"]


class LearningRuntimeControlRequest(BaseModel):
    """Request one durable, optimistic-concurrency control operation."""

    model_config = ConfigDict(extra="forbid")

    action: LearningRuntimeControlAction
    expected_state_version: int | None = Field(default=None, ge=1)
    data: dict[str, Any] = Field(default_factory=dict, max_length=64)
    idempotency_key: str = Field(default="", max_length=128)

    @model_validator(mode="after")
    def validate_control_data(self) -> LearningRuntimeControlRequest:
        if self.action == "input" and not self.data:
            raise ValueError("input control requires non-empty data")
        if self.action != "input" and self.data:
            raise ValueError("control data is only valid for input")
        return self


class LearningRuntimeControlRead(BaseModel):
    """One state-aware, provider-free LearningLoop operator control."""

    model_config = ConfigDict(extra="forbid")

    action: LearningRuntimeControlAction
    available: bool
    reason_code: str = Field(default="", max_length=160)
    reason: str = Field(default="", max_length=500)


class LearningRuntimeControlProjectionRead(BaseModel):
    """Redacted control projection for one owned LearningLoop Runtime run."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    provider_called: Literal[False] = False
    run_id: str = Field(min_length=1, max_length=120)
    runtime_id: str = Field(min_length=1, max_length=120)
    run_kind: Literal["teaching_interaction", "learning_progress"]
    status: str = Field(min_length=1, max_length=32)
    state_version: int = Field(ge=1)
    control_scope: Literal["learning_loop"] = "learning_loop"
    controls: list[LearningRuntimeControlRead] = Field(
        default_factory=list, max_length=4
    )
    available_controls: list[LearningRuntimeControlAction] = Field(
        default_factory=list, max_length=4
    )


class LearningRuntimeNodeStatusRead(BaseModel):
    """Redacted node state for the LearningLoop Runtime status projection."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=32)
    effect_status: str = Field(min_length=1, max_length=32)
    attempt: int = Field(ge=0)
    error_code: str = Field(default="", max_length=160)


class LearningRuntimeStatusRead(BaseModel):
    """Provider-free, ownership-checked LearningLoop Runtime snapshot."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=120)
    task_id: str = Field(min_length=1, max_length=120)
    runtime_id: str = Field(min_length=1, max_length=120)
    run_kind: Literal["teaching_interaction", "learning_progress"]
    status: str = Field(min_length=1, max_length=32)
    state_version: int = Field(ge=1)
    goal: str = Field(min_length=1, max_length=8_000)
    success_criteria: list[str] = Field(default_factory=list, max_length=32)
    required_capabilities: list[str] = Field(default_factory=list, max_length=32)
    goal_source: str = Field(default="request", max_length=64)
    node_statuses: list[LearningRuntimeNodeStatusRead] = Field(
        default_factory=list, max_length=100
    )
    control_scope: Literal["learning_loop"] = "learning_loop"
    available_controls: list[LearningRuntimeControlAction] = Field(
        default_factory=list, max_length=4
    )
    approval_required: bool = False
    resumable: bool = False


class LearningRuntimeCapabilityRead(BaseModel):
    """Provider-free descriptor for one LearningLoop Runtime capability."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str = Field(min_length=1, max_length=100)
    domain: Literal["learning_loop"] = "learning_loop"
    runtime_id: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=120)
    agent_version: str = Field(default="", max_length=120)
    runtime_plan_version: str = Field(default="", max_length=120)
    canary_release_eligible: bool = False
    canary_reason: str = Field(default="", max_length=160)
    enabled: bool
    supported_actions: list[str] = Field(default_factory=list, max_length=64)
    supports_pause: bool = False
    supports_resume: bool = False
    supports_approval: bool = False
    supports_input: bool = False
    control_scope: str = Field(min_length=1, max_length=64)
    result_contract: str = Field(min_length=1, max_length=160)
    blockers: list[str] = Field(default_factory=list, max_length=16)


class LearningRuntimeReadinessRead(BaseModel):
    """Read-only readiness projection for the LearningLoop Runtime boundary."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    provider_called: Literal[False] = False
    capabilities: list[LearningRuntimeCapabilityRead] = Field(
        default_factory=list, max_length=2
    )
    blockers: list[str] = Field(default_factory=list, max_length=32)


class LearningFollowUpContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_task_id: str
    course_id: str
    intent: str
    action: LearningAction


class LearningActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interaction_id: str
    action: LearningAction
    status: Literal["completed", "accepted", "needs_task"]
    message: str
    follow_up_prompt: str = ""
    follow_up_context: LearningFollowUpContext | None = None
    review: AnswerReviewResult | None = None
    practice: PracticeProblem | None = None
    mastery: list[LearnerKnowledgeState] = Field(default_factory=list)
    teaching: dict[str, Any] = Field(default_factory=dict)
    attempt: StudentAttemptV2 | None = None
    feedback_uptake: FeedbackUptakeV1 | None = None
    mastery_evidence: list[MasteryEvidenceV1] = Field(default_factory=list)
    retest_plans: list[RetestPlanV1] = Field(default_factory=list)
    runtime_run_id: str | None = None
    runtime_status: str = ""
    approval_required: bool = False


class LearningRuntimeControlResultRead(BaseModel):
    """Result envelope for an accepted LearningLoop operator action."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    provider_called: Literal[False] = False
    run_id: str = Field(min_length=1, max_length=120)
    action: LearningRuntimeControlAction
    accepted: Literal[True] = True
    status: str = Field(min_length=1, max_length=32)
    state_version: int = Field(ge=1)
    result: LearningActionResponse | None = None
