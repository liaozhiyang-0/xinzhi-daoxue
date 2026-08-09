from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IntentComplexity = Literal["simple", "medium", "complex"]
IntentRouteMode = Literal["fast", "single_agent", "workflow", "clarify"]


class IntentRecognition(BaseModel):
    """Structured, provider-independent user intent recognition result."""

    model_config = ConfigDict(extra="forbid")

    task_family: str = Field(default="fallback", min_length=1, max_length=40)
    intent: str = Field(default="unknown", min_length=1, max_length=64)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    selected_tools: list[str] = Field(default_factory=list, max_length=20)
    selected_skills: list[str] = Field(default_factory=list, max_length=20)
    complexity: IntentComplexity = "simple"
    route_mode: IntentRouteMode = "fast"
    needs_retrieval: bool = False
    needs_external_retrieval: bool = False
    needs_subagents: bool = False
    parallelizable: bool = False
    confidence: float = Field(default=0.0, ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list, max_length=12)
    clarification_prompt: str = Field(default="", max_length=500)


class PlanNode(BaseModel):
    """A bounded node in a future tool/skill/sub-agent execution graph."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1, max_length=80)
    node_type: Literal["agent", "tool", "skill", "retrieval", "verifier", "compose"]
    target_id: str = Field(min_length=1, max_length=120)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    parallel_group: str = Field(default="", max_length=80)
    timeout_ms: int = Field(default=30000, ge=100, le=300000)
    max_retries: int = Field(default=0, ge=0, le=2)
    optional: bool = False


class IntentExecutionPlan(BaseModel):
    """Codex-like execution plan kept separate from the legacy agent plan."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1, max_length=100)
    version: str = "1"
    mode: IntentRouteMode = "fast"
    goal: str = Field(default="", max_length=500)
    nodes: list[PlanNode] = Field(default_factory=list, max_length=40)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    selected_tools: list[str] = Field(default_factory=list, max_length=20)
    selected_skills: list[str] = Field(default_factory=list, max_length=20)
    success_criteria: list[str] = Field(default_factory=list, max_length=12)
    fallback_targets: list[str] = Field(default_factory=list, max_length=8)
    max_parallelism: int = Field(default=1, ge=1, le=16)
    confidence: float = Field(default=0.0, ge=0, le=1)
