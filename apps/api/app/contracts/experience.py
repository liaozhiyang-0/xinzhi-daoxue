from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _now() -> datetime:
    return datetime.now(UTC)


class ExperienceType(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    STRATEGY = "strategy"


class ExperienceLifecycle(StrEnum):
    OBSERVED = "observed"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    APPROVED = "approved"
    ACTIVE = "active"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"
    EXPIRED = "expired"
    FORGOTTEN = "forgotten"


class ExperienceScope(StrEnum):
    USER_SCOPED = "user_scoped"
    COURSE_SCOPED = "course_scoped"
    CAPABILITY_SCOPED = "capability_scoped"
    GLOBAL_DEIDENTIFIED = "global_deidentified"


class ExperienceEvidenceLevel(StrEnum):
    SYNTHETIC_PROVIDER_FREE = "synthetic_provider_free"
    OFFLINE_REAL_CASE = "offline_real_case"
    REAL_PROVIDER_TEST = "real_provider_test"
    CONTROLLED_CANARY = "controlled_canary"
    PRODUCTION = "production"


class ExperiencePrivacyClass(StrEnum):
    USER_PRIVATE = "user_private"
    COURSE_DEIDENTIFIED = "course_deidentified"
    CAPABILITY_DEIDENTIFIED = "capability_deidentified"
    GLOBAL_DEIDENTIFIED = "global_deidentified"


class ExperienceRedactionStatus(StrEnum):
    REQUIRED = "required"
    REDACTED = "redacted"
    VERIFIED = "verified"


class ExperienceRecord(BaseModel):
    """The single governed contract for reusable execution experience.

    This is deliberately not the user-memory contract.  A record is never
    executable by itself and is only a bounded prior after lifecycle and
    policy checks.
    """

    model_config = ConfigDict(extra="forbid")

    experience_id: str = Field(default_factory=lambda: f"exp_{uuid4().hex}")
    record_version: int = Field(default=1, ge=1)
    experience_type: ExperienceType
    lifecycle_status: ExperienceLifecycle = ExperienceLifecycle.CANDIDATE
    scope: ExperienceScope
    scope_owner_id: str | None = None
    course_id: str | None = None
    capability_id: str = ""
    skill_ids: list[str] = Field(default_factory=list, max_length=32)
    skill_versions: dict[str, str] = Field(default_factory=dict, max_length=32)
    tool_ids: list[str] = Field(default_factory=list, max_length=32)
    tool_versions: dict[str, str] = Field(default_factory=dict, max_length=32)
    planner_version: str = ""
    plan_signature: str = ""
    model_versions: dict[str, str] = Field(default_factory=dict, max_length=16)
    input_feature_summary: dict[str, Any] = Field(
        default_factory=dict, max_length=32
    )
    problem_type: str = ""
    risk_level: str = "low"
    strategy_summary: str = Field(default="", max_length=4000)
    failure_stage: str = ""
    error_codes: list[str] = Field(default_factory=list, max_length=32)
    verification_result: dict[str, Any] = Field(
        default_factory=dict, max_length=32
    )
    reflection_result: dict[str, Any] = Field(
        default_factory=dict, max_length=32
    )
    outcome_metrics: dict[str, Any] = Field(default_factory=dict, max_length=32)
    evidence_level: ExperienceEvidenceLevel = (
        ExperienceEvidenceLevel.SYNTHETIC_PROVIDER_FREE
    )
    source_trace_ids: list[str] = Field(default_factory=list, max_length=32)
    source_run_ids: list[str] = Field(default_factory=list, max_length=32)
    source_eval_ids: list[str] = Field(default_factory=list, max_length=32)
    confidence: float = Field(default=0.0, ge=0, le=1)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    expires_at: datetime | None = None
    supersedes: str | None = None
    conflicts_with: list[str] = Field(default_factory=list, max_length=32)
    privacy_class: ExperiencePrivacyClass
    redaction_status: ExperienceRedactionStatus = (
        ExperienceRedactionStatus.REQUIRED
    )
    promotion_provenance: dict[str, Any] = Field(
        default_factory=dict, max_length=32
    )
    applicability: list[str] = Field(default_factory=list, max_length=32)
    counterexamples: list[str] = Field(default_factory=list, max_length=32)
    failure_rate: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_scope_owner(self) -> ExperienceRecord:
        if self.scope == ExperienceScope.USER_SCOPED and not self.scope_owner_id:
            raise ValueError("user_scoped experience requires scope_owner_id")
        if self.scope != ExperienceScope.USER_SCOPED and self.scope_owner_id:
            raise ValueError("scope_owner_id is only valid for user_scoped experience")
        if self.scope == ExperienceScope.COURSE_SCOPED and not self.course_id:
            raise ValueError("course_scoped experience requires course_id")
        if self.scope == ExperienceScope.GLOBAL_DEIDENTIFIED:
            if self.privacy_class != ExperiencePrivacyClass.GLOBAL_DEIDENTIFIED:
                raise ValueError("global experience must be deidentified")
            if self.scope_owner_id:
                raise ValueError("global experience cannot have an owner")
        return self


class ExperienceCandidateCreate(ExperienceRecord):
    """Explicit candidate input; lifecycle is forced by the write service."""

    lifecycle_status: ExperienceLifecycle = ExperienceLifecycle.CANDIDATE


class ExperienceRetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str | None = None
    capability_id: str = ""
    problem_type: str = ""
    selected_skill_ids: list[str] = Field(default_factory=list, max_length=32)
    selected_tool_ids: list[str] = Field(default_factory=list, max_length=32)
    risk_level: str = "low"
    planner_version: str = ""
    user_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class ExperienceMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: str
    experience_type: ExperienceType
    score: float = Field(ge=0)
    match_reasons: list[str] = Field(default_factory=list, max_length=16)
    strategy_summary: str = ""
    failure_warning: str = ""
    evidence_level: ExperienceEvidenceLevel
    confidence: float = Field(ge=0, le=1)
    scope: ExperienceScope
    planner_version: str = ""
    experience_version: int = Field(default=1, ge=1)


class ExperienceInfluence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_plan: dict[str, Any] = Field(default_factory=dict)
    experience_matches: list[ExperienceMatch] = Field(
        default_factory=list, max_length=20
    )
    influence_applied: bool = False
    influence_reason: str = "disabled"
    final_candidate_plan: dict[str, Any] = Field(default_factory=dict)
    preflight_result: dict[str, Any] = Field(default_factory=dict)


class ExperiencePromotionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replay_passed: bool = False
    no_critical_regression: bool = False
    independent_reviewed: bool = False
    legal_evidence_ok: bool = False
    reason: str = ""
    reviewer_id: str = ""


class ExperienceEvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval_valid_match_rate: float = Field(default=0, ge=0, le=1)
    retrieval_irrelevant_match_rate: float = Field(default=0, ge=0, le=1)
    stale_filtered: int = Field(default=0, ge=0)
    wrong_scope_filtered: int = Field(default=0, ge=0)
    version_mismatch_filtered: int = Field(default=0, ge=0)
    planner_improvement: float = 0
    planner_degradation: float = 0
    failure_avoidance: float = 0
    invalid_target_count: int = Field(default=0, ge=0)
    privacy_leak_count: int = Field(default=0, ge=0)
    provenance_complete: bool = False
    status: str = "structural_go"
