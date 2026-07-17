from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RouteStatus(StrEnum):
    SELECTED = "selected"
    UNSUPPORTED = "unsupported"


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
