from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RouteStatus(StrEnum):
    SELECTED = "selected"
    UNSUPPORTED = "unsupported"
    UNRESOLVED = "unresolved"


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
