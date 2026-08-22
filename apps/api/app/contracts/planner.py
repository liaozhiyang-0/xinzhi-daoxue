from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PlannerLineage(BaseModel):
    """Stable identities used to compare Planner and legacy execution facts."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    request_id: str = ""
    trace_id: str = ""
    route_revision: int = Field(default=0, ge=0)
    current_plan_id: str = ""
    current_plan_version: str = ""
    context_snapshot_id: str = ""
    registry_snapshot_id: str = ""
    source: str = "task_creation"


class PlannerBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_model_calls: int = Field(default=0, ge=0, le=1000)
    max_tool_calls: int = Field(default=0, ge=0, le=1000)
    max_subagent_runs: int = Field(default=0, ge=0, le=100)
    max_parallelism: int = Field(default=1, ge=1, le=32)


class CanonicalGoal(BaseModel):
    """Goal semantics independent from a Runtime execution implementation."""

    model_config = ConfigDict(extra="forbid")

    objective: str = Field(default="", max_length=8_000)
    task_family: str = ""
    course: str = ""
    intent: str = ""
    constraints: dict[str, Any] = Field(default_factory=dict, max_length=32)
    context_requirements: list[str] = Field(default_factory=list, max_length=32)


class CanonicalPlanNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1, max_length=120)
    node_type: Literal["agent", "tool", "skill", "retrieval", "verifier", "compose"]
    target_id: str = Field(min_length=1, max_length=160)
    depends_on: list[str] = Field(default_factory=list, max_length=32)
    parallel_group: str = Field(default="", max_length=80)
    timeout_ms: int = Field(default=30_000, ge=100, le=900_000)
    max_retries: int = Field(default=0, ge=0, le=5)
    optional: bool = False


class CanonicalPlan(BaseModel):
    """The single future plan vocabulary between planning and Runtime adapters."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1, max_length=120)
    version: str = Field(default="canonical-v1", min_length=1, max_length=64)
    goal: CanonicalGoal
    nodes: list[CanonicalPlanNode] = Field(min_length=1, max_length=100)
    capabilities: list[str] = Field(default_factory=list, max_length=32)
    selected_agents: list[str] = Field(default_factory=list, max_length=32)
    selected_skills: list[str] = Field(default_factory=list, max_length=32)
    selected_tools: list[str] = Field(default_factory=list, max_length=32)
    success_criteria: list[str] = Field(default_factory=list, max_length=32)
    budget: PlannerBudget = Field(default_factory=PlannerBudget)
    confidence: float = Field(default=0.0, ge=0, le=1)
    source: str = Field(default="planner", max_length=64)


class PlannerRouteProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    course: str
    intent: str
    route_status: str
    route_source: str
    route_revision: int = Field(default=0, ge=0)
    confidence: float = Field(default=0.0, ge=0, le=1)
    capability: str = ""
    fingerprint: str = Field(min_length=16, max_length=64)


class PlannerPlanShape(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = ""
    version: str = ""
    node_ids: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    fingerprint: str = Field(min_length=16, max_length=64)


class PlannerSnapshot(BaseModel):
    """Versioned, trace-safe Planner output shared by both task entrances."""

    model_config = ConfigDict(extra="forbid")

    planner_version: str = "planner-v1"
    mode: Literal["shadow", "takeover", "failed"] = "shadow"
    status: Literal["completed", "failed", "disabled"] = "completed"
    goal: str = Field(default="", max_length=8_000)
    objective: str = Field(default="", max_length=8_000)
    task_family: str = ""
    course: str = ""
    intent: str = ""
    candidate_capabilities: list[str] = Field(default_factory=list, max_length=32)
    selected_capability: str = ""
    selected_agents: list[str] = Field(default_factory=list, max_length=32)
    selected_skills: list[str] = Field(default_factory=list, max_length=32)
    selected_tools: list[str] = Field(default_factory=list, max_length=32)
    success_criteria: list[str] = Field(default_factory=list, max_length=32)
    constraints: dict[str, Any] = Field(default_factory=dict, max_length=32)
    budget: PlannerBudget = Field(default_factory=PlannerBudget)
    context_requirements: list[str] = Field(default_factory=list, max_length=32)
    canonical_plan: CanonicalPlan | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list, max_length=32)
    lineage: PlannerLineage
    current_route: PlannerRouteProjection
    planner_route: PlannerRouteProjection
    current_intent: str = ""
    planner_intent: str = ""
    current_capability: str = ""
    planner_capability: str = ""
    current_tools: list[str] = Field(default_factory=list, max_length=32)
    planner_tools: list[str] = Field(default_factory=list, max_length=32)
    current_skills: list[str] = Field(default_factory=list, max_length=32)
    planner_skills: list[str] = Field(default_factory=list, max_length=32)
    current_plan_shape: PlannerPlanShape
    planner_plan_shape: PlannerPlanShape
    route_match: bool = False
    plan_match: bool = False
    planner_confidence: float = Field(default=0.0, ge=0, le=1)
    planner_reason_codes: list[str] = Field(default_factory=list, max_length=32)
    latency_ms: int = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0)
    error_type: str = ""
    fallback_reason: str = ""
