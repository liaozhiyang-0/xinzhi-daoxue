from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ReflectionAction = Literal["skip", "critique", "needs_review", "fail"]
CriticStatus = Literal["pass", "revise", "fail", "needs_review"]
RevisionStatus = Literal["revised", "no_change", "failed"]


class CriticResult(BaseModel):
    """Bounded advice from the internal Reflection worker.

    This is advisory only.  The Runtime result pipeline remains the owner of
    deterministic verification and terminal publication decisions.
    """

    model_config = ConfigDict(extra="forbid")

    status: CriticStatus
    issue_types: list[str] = Field(default_factory=list, max_length=12)
    severity: Literal["low", "medium", "high", "critical"] = "low"
    issue_summary: str = Field(default="", max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=30)
    unsupported_claims: list[str] = Field(default_factory=list, max_length=12)
    required_changes: list[str] = Field(default_factory=list, max_length=12)
    confidence: float = Field(default=0, ge=0, le=1)
    critic_version: str = Field(min_length=1, max_length=64)
    revision_allowed: bool = False


class ReflectionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ReflectionAction
    reason_codes: list[str] = Field(default_factory=list, max_length=12)
    max_revision_count: int = Field(default=0, ge=0, le=1)
    critic_profile: str = Field(default="default", max_length=64)
    budget_tokens: int = Field(default=0, ge=0, le=16_000)
    budget_ms: int = Field(default=0, ge=0, le=120_000)
    required_verifiers: list[str] = Field(default_factory=list, max_length=12)


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_result: dict[str, Any] = Field(default_factory=dict)
    critic_result: CriticResult
    allowed_changes: list[str] = Field(default_factory=list, max_length=12)
    evidence_refs: list[str] = Field(default_factory=list, max_length=30)
    revision_count: int = Field(default=0, ge=0, le=1)
    revision_budget: int = Field(default=1, ge=0, le=1)


class RevisionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RevisionStatus
    revised_answer: str = Field(default="", max_length=20_000)
    revised_business_data: dict[str, Any] = Field(default_factory=dict)
    revised_structured_result: dict[str, Any] = Field(default_factory=dict)
    changed_fields: list[str] = Field(default_factory=list, max_length=20)
    change_summary: str = Field(default="", max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=30)
    revision_count: int = Field(default=1, ge=0, le=1)


class ReflectionMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    critic_attempted: bool = False
    critic_status: str = "not_run"
    critic_latency_ms: int = Field(default=0, ge=0)
    critic_tokens: int = Field(default=0, ge=0)
    revision_attempted: bool = False
    revision_status: str = "not_run"
    revision_latency_ms: int = Field(default=0, ge=0)
    revision_tokens: int = Field(default=0, ge=0)
    revision_count: int = Field(default=0, ge=0, le=1)
    unsupported_critique_count: int = Field(default=0, ge=0)
    verifier_critic_disagreement: str = "none"
    error: str = ""


class ReflectionTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["reflection.v1"] = "reflection.v1"
    mode: Literal["off", "shadow", "bounded_revision"] = "off"
    capability: str = ""
    available_evidence_refs: list[str] = Field(default_factory=list, max_length=60)
    decision: ReflectionDecision
    critic: CriticResult | None = None
    revision: RevisionProposal | None = None
    metrics: ReflectionMetrics = Field(default_factory=ReflectionMetrics)
    deterministic_status: str = "not_checked"
    final_status: str = "not_run"
