from __future__ import annotations

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
    enabled: bool = True


class ScenarioCatalogDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=32)
    scenarios: list[ScenarioDefinition] = Field(min_length=1)
