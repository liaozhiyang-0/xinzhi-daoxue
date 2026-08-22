from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.agent import utc_now


class RuntimeRunStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RuntimeLaunchSnapshot(BaseModel):
    """Immutable launch decision carried by every durable Runtime checkpoint."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1, max_length=64)
    mode: str = Field(min_length=1, max_length=32)
    source: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=256)
    explicit_opt_in: bool = False


class RuntimeCompatibilitySnapshot(BaseModel):
    """Auditable summary of the legacy envelope prepared for a Runtime Run."""

    model_config = ConfigDict(extra="forbid")

    preparation_version: str = Field(default="1", max_length=16)
    preparation_status: str = Field(min_length=1, max_length=32)
    agent_id: str = Field(min_length=1, max_length=64)
    route_source: str = Field(default="", max_length=64)
    route_status: str = Field(default="", max_length=32)
    route_revision: int = Field(default=0, ge=0)
    route_confidence: float = Field(default=0, ge=0, le=1)
    route_reason: str = Field(default="", max_length=512)
    context_status: str = Field(default="not_configured", max_length=32)
    context_cache_status: str = Field(default="none", max_length=32)
    context_cache_backend: str = Field(default="none", max_length=32)
    context_source_message_ids: list[str] = Field(
        default_factory=list, max_length=200
    )
    context_trimmed: bool = False
    context_estimated_tokens: int = Field(default=0, ge=0)
    execution_plan_agent_id: str = Field(default="", max_length=64)
    execution_plan_provider_type: str = Field(default="", max_length=32)
    execution_plan_route_status: str = Field(default="", max_length=32)
    execution_plan_input_mode: str = Field(default="", max_length=32)
    execution_plan_context_budget: int = Field(default=0, ge=0)
    prepared_at: datetime = Field(default_factory=utc_now)


class RuntimeNodeStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class RuntimeNodeActivation(StrEnum):
    """Declare when a node becomes executable after its dependencies settle."""

    ALL_SUCCEEDED = "all_succeeded"
    ANY_FAILED = "any_failed"
    ALWAYS = "always"


class RuntimeEffectStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


class DecisionAction(StrEnum):
    EXECUTE = "execute"
    REPLAN = "replan"
    ASK_USER = "ask_user"
    REQUEST_APPROVAL = "request_approval"
    PAUSE = "pause"
    FINISH = "finish"
    FAIL = "fail"


class RuntimePlanProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


class RuntimePlanBudgetImpact(BaseModel):
    """Conservative upper-bound cost declared by a proposed plan."""

    model_config = ConfigDict(extra="forbid")

    model_calls: int = Field(default=0, ge=0, le=1000)
    tool_calls: int = Field(default=0, ge=0, le=1000)
    subagent_runs: int = Field(default=0, ge=0, le=100)

    @classmethod
    def from_plan(cls, plan: AgentRunPlan) -> RuntimePlanBudgetImpact:
        model_calls = 0
        tool_calls = 0
        subagent_runs = 0
        for node in plan.nodes:
            normalized = node.node_type.casefold()
            if normalized in {"agent", "model", "provider", "workflow"}:
                model_calls += 1
            elif normalized in {"subagent", "sub_agent"}:
                subagent_runs += 1
            elif normalized not in {"none", "control", "verification"}:
                tool_calls += 1
        return cls(
            model_calls=model_calls,
            tool_calls=tool_calls,
            subagent_runs=subagent_runs,
        )


class RuntimeGoal(BaseModel):
    """Structured objective carried by every executable Runtime plan."""

    model_config = ConfigDict(extra="forbid")

    objective: str = Field(min_length=1, max_length=8_000)
    success_criteria: list[str] = Field(default_factory=list, max_length=32)
    constraints: dict[str, Any] = Field(default_factory=dict)
    required_capabilities: list[str] = Field(default_factory=list, max_length=32)
    # Optional explicit execution phases. Each inner list is an independent
    # batch; phases remain ordered. An empty value preserves the historical
    # sequential plan compiler behavior.
    parallel_groups: list[list[str]] = Field(default_factory=list, max_length=16)
    context: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(default="request", max_length=64)


class RuntimePlanProposal(BaseModel):
    """Versioned, reviewable plan replacement awaiting an explicit decision."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(min_length=1, max_length=120)
    task_id: str = Field(min_length=1, max_length=120)
    run_id: str = Field(min_length=1, max_length=120)
    base_iteration: int = Field(ge=0)
    target_iteration: int = Field(ge=1)
    base_state_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    base_plan_id: str = Field(min_length=1, max_length=120)
    base_plan_version: str = Field(min_length=1, max_length=32)
    proposed_plan: AgentRunPlan
    reason_codes: list[str] = Field(min_length=1, max_length=16)
    rationale: str = Field(min_length=1, max_length=4_000)
    affected_node_ids: list[str] = Field(default_factory=list, max_length=100)
    budget_impact: RuntimePlanBudgetImpact
    approval_required: bool = True
    status: RuntimePlanProposalStatus = RuntimePlanProposalStatus.PENDING
    decision_reason: str = Field(default="", max_length=2_000)
    created_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None
    applied_at: datetime | None = None


class RuntimeBudget(BaseModel):
    """Hard limits for one run; the executor must enforce these limits."""

    model_config = ConfigDict(extra="forbid")

    max_iterations: int = Field(default=3, ge=1, le=100)
    max_model_calls: int = Field(default=8, ge=0, le=1000)
    max_tool_calls: int = Field(default=16, ge=0, le=1000)
    max_subagent_runs: int = Field(default=4, ge=0, le=100)
    deadline: datetime | None = None
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    subagent_runs: int = Field(default=0, ge=0)
    child_consumption: dict[str, dict[str, int]] = Field(default_factory=dict)

    def can_start_iteration(self, now: datetime | None = None) -> bool:
        current = now or utc_now()
        return self.deadline is None or current < self.deadline

    def can_call_model(self) -> bool:
        return self.model_calls < self.max_model_calls

    def can_call_tool(self) -> bool:
        return self.tool_calls < self.max_tool_calls

    def can_spawn_subagent(self) -> bool:
        return self.subagent_runs < self.max_subagent_runs

    def allocate_child(self) -> RuntimeBudget:
        """Allocate the remaining aggregate budget to a direct child Run."""

        return RuntimeBudget(
            max_iterations=self.max_iterations,
            max_model_calls=max(0, self.max_model_calls - self.model_calls),
            max_tool_calls=max(0, self.max_tool_calls - self.tool_calls),
            max_subagent_runs=max(0, self.max_subagent_runs - self.subagent_runs),
            deadline=self.deadline,
        )

    def absorb_child(self, child_run_id: str, child_budget: RuntimeBudget) -> None:
        """Account a child Run exactly once in the parent's aggregate budget."""

        if child_run_id in self.child_consumption:
            return
        model_calls = child_budget.model_calls
        tool_calls = child_budget.tool_calls
        subagent_runs = child_budget.subagent_runs
        if self.model_calls + model_calls > self.max_model_calls:
            raise ValueError("child_model_call_budget_exceeded")
        if self.tool_calls + tool_calls > self.max_tool_calls:
            raise ValueError("child_tool_call_budget_exceeded")
        if self.subagent_runs + subagent_runs > self.max_subagent_runs:
            raise ValueError("child_subagent_budget_exceeded")
        self.model_calls += model_calls
        self.tool_calls += tool_calls
        self.subagent_runs += subagent_runs
        self.child_consumption[child_run_id] = {
            "model_calls": model_calls,
            "tool_calls": tool_calls,
            "subagent_runs": subagent_runs,
        }

    def reserve(self, node_type: str) -> str:
        """Consume one call budget for a node before invoking its handler."""

        normalized = node_type.casefold()
        if normalized in {"agent", "model", "provider", "workflow"}:
            if not self.can_call_model():
                raise ValueError("model_call_budget_exceeded")
            self.model_calls += 1
            return "model"
        if normalized in {"subagent", "sub_agent"}:
            if not self.can_spawn_subagent():
                raise ValueError("subagent_budget_exceeded")
            self.subagent_runs += 1
            return "subagent"
        if normalized in {"none", "control", "verification"}:
            return "none"
        if not self.can_call_tool():
            raise ValueError("tool_call_budget_exceeded")
        self.tool_calls += 1
        return "tool"


class RuntimeNode(BaseModel):
    """A declarative node that can be dispatched by PlanExecutor."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1, max_length=100)
    node_type: str = Field(min_length=1, max_length=32)
    handler_id: str = Field(min_length=1, max_length=160)
    target_id: str = Field(default="", max_length=160)
    depends_on: list[str] = Field(default_factory=list, max_length=32)
    activation: RuntimeNodeActivation = RuntimeNodeActivation.ALL_SUCCEEDED
    recovery_for: list[str] = Field(default_factory=list, max_length=32)
    parallel_group: str = Field(default="", max_length=80)
    timeout_ms: int = Field(default=30_000, ge=100, le=900_000)
    max_retries: int = Field(default=0, ge=0, le=5)
    optional: bool = False
    input_artifact_ids: list[str] = Field(default_factory=list, max_length=100)
    skill_id: str = Field(default="", max_length=128)
    skill_version: str = Field(default="", max_length=32)
    skill_binding_id: str = Field(default="", max_length=160)


class AgentRunPlan(BaseModel):
    """Validated plan snapshot; it is immutable once a run starts."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1, max_length=120)
    version: str = Field(default="1", min_length=1, max_length=32)
    goal: str = Field(min_length=1, max_length=8_000)
    goal_contract: RuntimeGoal | None = None
    nodes: list[RuntimeNode] = Field(min_length=1, max_length=100)
    success_criteria: list[str] = Field(default_factory=list, max_length=32)
    max_parallelism: int = Field(default=1, ge=1, le=32)

    @model_validator(mode="after")
    def validate_graph(self) -> AgentRunPlan:
        if self.goal_contract is None:
            self.goal_contract = RuntimeGoal(
                objective=self.goal,
                success_criteria=list(self.success_criteria),
            )
        elif self.goal_contract.objective != self.goal:
            raise ValueError("runtime goal contract objective differs from plan goal")
        if not self.success_criteria and self.goal_contract.success_criteria:
            self.success_criteria = list(self.goal_contract.success_criteria)
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("runtime plan contains duplicate node_id")
        known = set(node_ids)
        for node in self.nodes:
            unknown = set(node.depends_on) - known
            if unknown:
                raise ValueError(
                    f"runtime plan node {node.node_id} depends on unknown nodes: "
                    f"{sorted(unknown)}"
                )
            if node.node_id in node.depends_on:
                raise ValueError(
                    "runtime plan node cannot depend on itself: "
                    f"{node.node_id}"
                )
            if (
                node.activation == RuntimeNodeActivation.ANY_FAILED
                and not node.depends_on
            ):
                raise ValueError(
                    "any_failed runtime node requires at least one dependency"
                )
            invalid_recovery = set(node.recovery_for) - set(node.depends_on)
            if invalid_recovery:
                raise ValueError(
                    f"runtime plan node {node.node_id} recovers non-dependencies: "
                    f"{sorted(invalid_recovery)}"
                )
            if (
                node.recovery_for
                and node.activation != RuntimeNodeActivation.ANY_FAILED
            ):
                raise ValueError(
                    "runtime recovery nodes must use any_failed activation"
                )

        # A small deterministic topological check prevents plans from entering
        # the executor with a cycle.  Execution ordering is still decided by
        # RuntimeStateMachine.ready_nodes().
        remaining = {node.node_id: set(node.depends_on) for node in self.nodes}
        resolved: set[str] = set()
        while remaining:
            ready = {
                node_id
                for node_id, dependencies in remaining.items()
                if dependencies <= resolved
            }
            if not ready:
                raise ValueError("runtime plan contains a dependency cycle")
            resolved.update(ready)
            for node_id in ready:
                remaining.pop(node_id)
        return self


class RuntimeObservation(BaseModel):
    """Bounded facts returned by a node; no hidden chain-of-thought is stored."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1, max_length=100)
    terminal_status: RuntimeNodeStatus = RuntimeNodeStatus.SUCCEEDED
    facts: dict[str, Any] = Field(default_factory=dict)
    artifact_ids: list[str] = Field(default_factory=list, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=32)
    errors: list[str] = Field(default_factory=list, max_length=32)
    confidence: float | None = Field(default=None, ge=0, le=1)
    skill_id: str = Field(default="", max_length=128)
    skill_version: str = Field(default="", max_length=32)
    skill_binding_id: str = Field(default="", max_length=160)


class RuntimeDecision(BaseModel):
    """Structured controller decision constrained to registered runtime actions."""

    model_config = ConfigDict(extra="forbid")

    action: DecisionAction
    node_ids: list[str] = Field(default_factory=list, max_length=32)
    reason_codes: list[str] = Field(default_factory=list, max_length=16)
    user_prompt: str = Field(default="", max_length=2_000)
    approval_scope: str = Field(default="", max_length=200)
    confidence: float | None = Field(default=None, ge=0, le=1)


class RuntimeNodeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    status: RuntimeNodeStatus = RuntimeNodeStatus.PENDING
    attempt: int = Field(default=0, ge=0)
    execution_key: str = Field(default="", max_length=240)
    reconciliation_id: str = Field(default="", max_length=240)
    # Durable reservation marker for a safe replay whose original attempt
    # already consumed the run budget. It is intentionally separate from
    # error_code so operator/debug surfaces only show actual failures.
    budget_reservation: str = Field(default="", max_length=32)
    provider_trace_id: str = Field(default="", max_length=128)
    effect_status: RuntimeEffectStatus = RuntimeEffectStatus.NOT_STARTED
    observation: RuntimeObservation | None = None
    error_code: str = ""
    skill_id: str = Field(default="", max_length=128)
    skill_version: str = Field(default="", max_length=32)
    skill_binding_id: str = Field(default="", max_length=160)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentRun(BaseModel):
    """Serializable run state used by the future durable repository."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=120)
    task_id: str = Field(min_length=1, max_length=120)
    run_kind: str = Field(default="runtime", min_length=1, max_length=32)
    parent_run_id: str = Field(default="", max_length=64)
    parent_node_id: str = Field(default="", max_length=100)
    goal: str = Field(min_length=1, max_length=8_000)
    goal_contract: RuntimeGoal | None = None
    status: RuntimeRunStatus = RuntimeRunStatus.CREATED
    plan: AgentRunPlan
    request_snapshot: dict[str, Any] = Field(default_factory=dict)
    launch_decision: RuntimeLaunchSnapshot | None = None
    compatibility_snapshot: RuntimeCompatibilitySnapshot | None = None
    nodes: dict[str, RuntimeNodeState] = Field(default_factory=dict)
    iteration: int = Field(default=0, ge=0)
    state_version: int = Field(default=1, ge=1)
    budget: RuntimeBudget = Field(default_factory=RuntimeBudget)
    observations: list[RuntimeObservation] = Field(default_factory=list, max_length=500)
    # Durable controller trace.  The latest decision remains available for
    # compatibility, while these bounded histories make a resumed Run
    # inspectable without storing hidden chain-of-thought.
    decision_history: list[RuntimeDecision] = Field(
        default_factory=list, max_length=500
    )
    verification_history: list[RuntimeObservation] = Field(
        default_factory=list, max_length=500
    )
    last_decision: RuntimeDecision | None = None
    control_request: str = Field(default="", max_length=32)
    control_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def initialize_nodes(self) -> AgentRun:
        if self.goal_contract is None:
            self.goal_contract = self.plan.goal_contract or RuntimeGoal(
                objective=self.goal,
                success_criteria=list(self.plan.success_criteria),
            )
        if self.goal_contract.objective != self.goal:
            # Older compatibility runs stored a Task-level goal separately
            # from the plan goal. Normalize the durable contract on restore
            # instead of rejecting those valid pre-contract checkpoints.
            self.goal_contract = self.goal_contract.model_copy(
                update={"objective": self.goal}
            )
        expected_node_ids = [node.node_id for node in self.plan.nodes]
        expected = set(expected_node_ids)
        if not self.nodes:
            self.nodes = {
                node.node_id: RuntimeNodeState(
                    node_id=node.node_id,
                    skill_id=node.skill_id,
                    skill_version=node.skill_version,
                    skill_binding_id=node.skill_binding_id,
                )
                for node in self.plan.nodes
            }
        elif set(self.nodes) != expected:
            raise ValueError("run node state does not match its plan")
        else:
            for node in self.plan.nodes:
                state = self.nodes[node.node_id]
                state.skill_id = state.skill_id or node.skill_id
                state.skill_version = state.skill_version or node.skill_version
                state.skill_binding_id = (
                    state.skill_binding_id or node.skill_binding_id
                )
        return self
