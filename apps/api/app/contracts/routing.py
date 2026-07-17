from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class InputMode(StrEnum):
    TEXT = "text"
    SINGLE_IMAGE = "single_image"
    TEXT_AND_SINGLE_IMAGE = "text_and_single_image"


class RouteStatus(StrEnum):
    SELECTED = "selected"
    UNSUPPORTED = "unsupported"
    UNRESOLVED = "route_unresolved"


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_status: RouteStatus
    course_id: str
    intent: str
    target_agent_id: str
    route_confidence: float = Field(ge=0, le=1)
    route_source: str
    reason: str
    input_mode: InputMode
    needs_knowledge: bool = False
    needs_fallback: bool = False

