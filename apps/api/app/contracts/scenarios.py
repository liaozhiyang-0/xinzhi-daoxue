from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CommercializationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    buyer: str = Field(min_length=1, max_length=160)
    delivery_unit: str = Field(min_length=1, max_length=120)
    value_capture: str = Field(min_length=1, max_length=200)
    expansion_path: str = Field(min_length=1, max_length=200)


class KnowledgeEvidencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authoritative_source_types: list[str] = Field(min_length=1, max_length=12)
    supplemental_source_types: list[str] = Field(default_factory=list, max_length=12)
    citation_required: bool = True
    manual_review_required: bool = True
    allow_synthetic: bool = False
    freshness_days: int | None = Field(default=None, ge=1, le=3650)


class ScenarioDemoCase(BaseModel):
    """Reproducible product-facing demonstration contract for one scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")
    role: str = Field(min_length=1, max_length=32)
    course: str = Field(min_length=1, max_length=32)
    prompt: str = Field(min_length=80, max_length=8_000)
    expected_agent: str = Field(min_length=1, max_length=100)
    expected_output: list[str] = Field(min_length=1, max_length=24)
    business_context: str = Field(min_length=1, max_length=1_000)
    evidence_requirements: list[str] = Field(min_length=1, max_length=12)
    review_boundary: str = Field(min_length=1, max_length=1_000)
    acceptance_conditions: list[str] = Field(min_length=1, max_length=16)
    formula_output_contract: dict[str, Any] | None = None
    visual_acceptance: dict[str, Any] | None = None


class ScenarioEvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: str = Field(min_length=1, max_length=80)
    source_ref: str = Field(min_length=1, max_length=512)
    cited: bool = False
    synthetic: bool = False
    published_at: datetime | None = None


class ScenarioEvidenceReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[ScenarioEvidenceSource] = Field(max_length=50)


class ScenarioEvidenceReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    status: Literal["approved", "needs_manual_review", "rejected"]
    checked_count: int = Field(ge=0)
    cited_count: int = Field(ge=0)
    accepted_source_refs: list[str] = Field(default_factory=list)
    rejected_source_refs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ScenarioPreflightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    scenario_version: str
    agent_id: str
    agent_status: Literal[
        "runtime_available",
        "fallback_only",
        "mock_only",
        "configured_unavailable",
        "unavailable",
    ]
    fallback_agent_id: str | None = None
    fallback_available: bool = False
    runtime_available: bool
    configured: bool
    mock_available: bool
    demo_ready: bool
    production_ready: bool
    commercialization_complete: bool
    evidence_review_required: bool
    input_modes: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")
    version: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    customer_segment: str = Field(min_length=1, max_length=160)
    commercialization: CommercializationPlan
    evidence_policy: KnowledgeEvidencePolicy
    roles: list[str] = Field(min_length=1, max_length=8)
    courses: list[str] = Field(min_length=1, max_length=32)
    agent_id: str = Field(min_length=1, max_length=100)
    intents: list[str] = Field(min_length=1, max_length=8)
    input_modes: list[str] = Field(min_length=1, max_length=8)
    retrieval_profile: str = Field(min_length=1, max_length=64)
    primary_value_metric: str = Field(min_length=1, max_length=200)
    evidence_requirements: list[str] = Field(min_length=1, max_length=12)
    demo_steps: list[str] = Field(min_length=1, max_length=8)
    demo_cases: list[ScenarioDemoCase] = Field(default_factory=list, max_length=8)
    enabled: bool = True


class ScenarioCatalogDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=32)
    scenarios: list[ScenarioDefinition] = Field(min_length=1)
