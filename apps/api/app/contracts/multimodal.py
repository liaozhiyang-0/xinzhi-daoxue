from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ImageRole = Literal[
    "TEXT_SCREENSHOT",
    "PROBLEM_STATEMENT",
    "CIRCUIT_DIAGRAM",
    "STUDENT_SOLUTION",
    "TABLE",
    "CHART",
    "WAVEFORM",
    "FORMULA",
    "DOCUMENT_PAGE",
    "REFERENCE_IMAGE",
    "GENERAL_IMAGE",
    "UNKNOWN",
]

RoleSource = Literal[
    "explicit_user",
    "user_prompt",
    "conversation",
    "multimodal_inference",
    "unknown",
]


class AttachmentRole(BaseModel):
    """Small, additive semantic metadata for one image attachment."""

    model_config = ConfigDict(extra="forbid")

    primary_role: ImageRole = "UNKNOWN"
    secondary_roles: list[ImageRole] = Field(default_factory=list, max_length=4)
    role_source: RoleSource = "unknown"
    confidence: float = Field(default=0.0, ge=0, le=1)


class MultimodalCapabilityHint(BaseModel):
    """Planner input, never a fixed Agent route."""

    model_config = ConfigDict(extra="forbid")

    intent: str = Field(default="UNKNOWN", min_length=1, max_length=64)
    possible_capabilities: list[str] = Field(default_factory=list, max_length=12)
    circuit_ir_requested: bool = False
    trigger_source: str = Field(default="default", max_length=80)
    reason_codes: list[str] = Field(default_factory=list, max_length=16)


class MultimodalObservation(BaseModel):
    """One bounded visual observation shared by downstream capabilities."""

    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(min_length=1, max_length=160)
    source: Literal["vision", "reused", "fallback"] = "vision"
    attachment_ids: list[str] = Field(default_factory=list, max_length=16)
    attachment_roles: dict[str, AttachmentRole] = Field(default_factory=dict)
    recognized_text: list[str] = Field(default_factory=list, max_length=40)
    summary: str = Field(default="", max_length=50_000)
    possible_capabilities: list[str] = Field(default_factory=list, max_length=12)
    confidence: float = Field(default=0.0, ge=0, le=1)
    partial: bool = False
    warnings: list[str] = Field(default_factory=list, max_length=16)


def role_payload(role: AttachmentRole) -> dict[str, Any]:
    """Return a JSON-safe role payload for untyped request options."""

    return role.model_dump(mode="json")
