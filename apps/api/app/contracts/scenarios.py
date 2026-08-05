from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")
    version: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    customer_segment: str = Field(min_length=1, max_length=160)
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
