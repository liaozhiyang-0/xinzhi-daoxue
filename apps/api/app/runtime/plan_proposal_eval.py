"""Provider-free quality checks for adaptive Runtime plan proposals."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.runtime.contracts import (
    AgentRun,
    RuntimeNodeStatus,
    RuntimePlanBudgetImpact,
    RuntimePlanProposal,
)

ACTIONABLE_NODE_TYPES = frozenset(
    {"agent", "model", "provider", "subagent", "sub_agent", "tool", "workflow"}
)


class RuntimePlanProposalSemanticExpectation(BaseModel):
    """Trace-authored evidence describing the failure a proposal must address."""

    model_config = ConfigDict(extra="forbid")

    verification_node_ids: list[str] = Field(
        min_length=1, max_length=32
    )
    verification_reason_codes: list[str] = Field(
        min_length=1, max_length=16
    )
    minimum_action_nodes: int = Field(default=1, ge=1, le=32)


class RuntimePlanProposalEvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=120)
    base_run: AgentRun
    proposal: RuntimePlanProposal
    require_approval: bool = True
    semantic_expectation: RuntimePlanProposalSemanticExpectation | None = None


class RuntimePlanProposalEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    passed: bool
    proposal_id: str
    failed_checks: list[str] = Field(default_factory=list)
    semantic_failures: list[str] = Field(default_factory=list)


class RuntimePlanProposalSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_id: str = Field(min_length=1, max_length=120)
    suite_version: str = Field(default="1", min_length=1, max_length=32)
    cases: list[RuntimePlanProposalEvaluationCase] = Field(
        min_length=1, max_length=1_000
    )
    require_semantic_alignment: bool = False


class RuntimePlanProposalSuiteReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_id: str
    suite_version: str
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    canary_eligible: bool
    semantic_gate_required: bool = False
    results: list[RuntimePlanProposalEvaluationResult]


def evaluate_runtime_plan_proposal(
    case: RuntimePlanProposalEvaluationCase,
    *,
    require_semantic_alignment: bool = False,
) -> RuntimePlanProposalEvaluationResult:
    base = case.base_run
    proposal = case.proposal
    failures: list[str] = []
    if proposal.run_id != base.run_id:
        failures.append("run_id_mismatch")
    if proposal.task_id != base.task_id:
        failures.append("task_id_mismatch")
    if proposal.base_plan_id != base.plan.plan_id:
        failures.append("base_plan_id_mismatch")
    if proposal.base_plan_version != base.plan.version:
        failures.append("base_plan_version_mismatch")
    if proposal.base_iteration != base.iteration:
        failures.append("base_iteration_mismatch")
    if proposal.target_iteration <= proposal.base_iteration:
        failures.append("target_iteration_not_ahead")
    if proposal.target_iteration >= base.budget.max_iterations:
        failures.append("target_iteration_budget_exceeded")
    if proposal.base_state_version < 1 or proposal.state_version < 1:
        failures.append("state_version_invalid")
    if proposal.state_version < proposal.base_state_version:
        failures.append("proposal_state_version_regressed")
    if any(
        state.status.value == "running" for state in base.nodes.values()
    ):
        failures.append("base_run_has_inflight_node")
    if not proposal.reason_codes:
        failures.append("reason_codes_required")
    if not proposal.rationale.strip():
        failures.append("rationale_required")
    expected_affected = _affected_nodes(base.plan, proposal.proposed_plan)
    if sorted(proposal.affected_node_ids) != expected_affected:
        failures.append("affected_nodes_incorrect")
    expected_budget = RuntimePlanBudgetImpact.from_plan(
        proposal.proposed_plan
    )
    if proposal.budget_impact != expected_budget:
        failures.append("budget_impact_not_conservative")
    remaining = (
        base.budget.max_model_calls - base.budget.model_calls,
        base.budget.max_tool_calls - base.budget.tool_calls,
        base.budget.max_subagent_runs - base.budget.subagent_runs,
    )
    requested = (
        proposal.budget_impact.model_calls,
        proposal.budget_impact.tool_calls,
        proposal.budget_impact.subagent_runs,
    )
    if any(
        value > limit for value, limit in zip(requested, remaining, strict=True)
    ):
        failures.append("budget_impact_exceeds_remaining_budget")
    if case.require_approval and not proposal.approval_required:
        failures.append("approval_policy_missing")
    if proposal.status.value not in {"pending", "approved", "applied"}:
        failures.append("proposal_status_not_applicable")
    semantic_failures: list[str] = []
    if require_semantic_alignment and case.semantic_expectation is None:
        semantic_failures.append("semantic_expectation_missing")
    elif case.semantic_expectation is not None:
        semantic_failures = _evaluate_semantic_alignment(
            base,
            proposal,
            case.semantic_expectation,
        )
    failures.extend(semantic_failures)
    return RuntimePlanProposalEvaluationResult(
        case_id=case.case_id,
        passed=not failures,
        proposal_id=proposal.proposal_id,
        failed_checks=failures,
        semantic_failures=semantic_failures,
    )


def evaluate_runtime_plan_proposal_suite(
    suite: RuntimePlanProposalSuite | Mapping[str, Any],
) -> RuntimePlanProposalSuiteReport:
    validated = (
        suite
        if isinstance(suite, RuntimePlanProposalSuite)
        else RuntimePlanProposalSuite.model_validate(suite)
    )
    results = [
        evaluate_runtime_plan_proposal(
            case,
            require_semantic_alignment=validated.require_semantic_alignment,
        )
        for case in validated.cases
    ]
    passed = sum(result.passed for result in results)
    return RuntimePlanProposalSuiteReport(
        suite_id=validated.suite_id,
        suite_version=validated.suite_version,
        total_cases=len(results),
        passed_cases=passed,
        failed_cases=len(results) - passed,
        canary_eligible=bool(results) and passed == len(results),
        semantic_gate_required=validated.require_semantic_alignment,
        results=results,
    )


def _evaluate_semantic_alignment(
    base: AgentRun,
    proposal: RuntimePlanProposal,
    expectation: RuntimePlanProposalSemanticExpectation,
) -> list[str]:
    failures: list[str] = []
    verification_ids = set(expectation.verification_node_ids)
    if not verification_ids:
        failures.append("semantic_verification_nodes_missing")
    if not expectation.verification_reason_codes:
        failures.append("semantic_reason_codes_missing")

    for node_id in sorted(verification_ids):
        state = base.nodes.get(node_id)
        if state is None:
            failures.append(f"verification_node_not_in_base_run:{node_id}")
            continue
        observation_facts = state.observation.facts if state.observation else {}
        failed_observation = (
            state.status
            in {RuntimeNodeStatus.FAILED, RuntimeNodeStatus.PARTIAL}
            or state.error_code != ""
            or observation_facts.get("passed") is False
            or observation_facts.get("replan_required") is True
        )
        if not failed_observation:
            failures.append(f"verification_failure_not_observed:{node_id}")

    if not set(proposal.reason_codes).intersection(
        expectation.verification_reason_codes
    ):
        failures.append("proposal_reason_not_aligned_with_verification")

    action_addresses_failure = any(
        verification_ids.intersection(node.depends_on)
        for node in proposal.proposed_plan.nodes
        if node.node_type.casefold() in ACTIONABLE_NODE_TYPES
    )
    if not (
        verification_ids.intersection(proposal.affected_node_ids)
        or action_addresses_failure
    ):
        failures.append("proposal_does_not_touch_verification_node")

    action_nodes = [
        node
        for node in proposal.proposed_plan.nodes
        if node.node_type.casefold() in ACTIONABLE_NODE_TYPES
    ]
    if len(action_nodes) < expectation.minimum_action_nodes:
        failures.append("proposal_action_nodes_insufficient")
    return failures


def _affected_nodes(previous: Any, proposed: Any) -> list[str]:
    previous_by_id = {node.node_id: node for node in previous.nodes}
    proposed_by_id = {node.node_id: node for node in proposed.nodes}
    changed = {
        node_id
        for node_id in previous_by_id.keys() | proposed_by_id.keys()
        if (
            previous_by_id.get(node_id) is None
            or proposed_by_id.get(node_id) is None
            or previous_by_id[node_id].model_dump(mode="json")
            != proposed_by_id[node_id].model_dump(mode="json")
        )
    }
    return sorted(changed)
