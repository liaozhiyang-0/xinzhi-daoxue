from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RouteStatus(StrEnum):
    SELECTED = "selected"
    UNSUPPORTED = "unsupported"
    UNRESOLVED = "unresolved"


class RouteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    score: float = 0.0
    available: bool = False
    reason_codes: list[str] = Field(default_factory=list)


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    scene: str
    course_id: str
    intent: str
    route_status: RouteStatus
    reason: str
    retrieval_required: bool
    provider_required: bool
    route_source: str = "local_fast"
    route_confidence: float = 1.0
    fallback_used: bool = False
    original_agent_id: str | None = None
    fallback_instruction: str = ""
    task_subtype: str = ""
    secondary_intents: list[str] = Field(default_factory=list)
    requires_pipeline: bool = False
    candidate_agents: list[RouteCandidate] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    local_confidence: float = 0.0
    cloud_router_invoked: bool = False
    availability: dict[str, Any] = Field(default_factory=dict)
    material_extraction: dict[str, Any] = Field(default_factory=dict)
    inferred_user_role: str = ""
    visited_agents: list[str] = Field(default_factory=list)
    reroute_count: int = 0
