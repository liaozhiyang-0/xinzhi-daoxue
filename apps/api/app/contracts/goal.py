from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.agent import AttachmentRef, UserRole
from app.contracts.planner import PlannerBudget


class GoalContract(BaseModel):
    """Normalized user goal shared by every ingress before planning.

    This contract contains request meaning and constraints only.  It must not
    contain a final Agent route or a Runtime implementation choice.
    """

    model_config = ConfigDict(extra="forbid")

    goal_id: str = Field(min_length=1, max_length=120)
    normalized_goal: str = Field(default="", max_length=8_000)
    user_role: UserRole = UserRole.STUDENT
    course_context: str = Field(default="AUTO", max_length=32)
    task_family_hint: str = Field(default="", max_length=64)
    input_modalities: list[str] = Field(default_factory=list, max_length=8)
    constraints: dict[str, Any] = Field(default_factory=dict, max_length=32)
    desired_output: list[str] = Field(default_factory=list, max_length=32)
    evidence_requirements: list[str] = Field(default_factory=list, max_length=32)
    risk_level: str = Field(default="low", max_length=16)
    budget: PlannerBudget = Field(default_factory=PlannerBudget)
    attachment_refs: list[AttachmentRef] = Field(default_factory=list, max_length=16)
    multimodal_intent: str = Field(default="UNKNOWN", max_length=64)
    multimodal_capability_hint: dict[str, Any] = Field(
        default_factory=dict, max_length=16
    )
    session_context_ref: str = Field(default="", max_length=160)
    scenario_hint: str = Field(default="", max_length=64)
