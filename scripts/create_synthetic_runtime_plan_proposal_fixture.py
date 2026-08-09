"""Create a provider-free adaptive plan proposal suite for CI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.runtime import (  # noqa: E402
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    RuntimeDecision,
    RuntimeNode,
    RuntimeNodeState,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimePlanBudgetImpact,
    RuntimePlanProposal,
    RuntimePlanProposalEvaluationCase,
    RuntimePlanProposalSemanticExpectation,
    RuntimePlanProposalStatus,
    RuntimePlanProposalSuite,
)


def build_fixture() -> RuntimePlanProposalSuite:
    base_run = AgentRun(
        run_id="synthetic-plan-proposal-run",
        task_id="synthetic-plan-proposal-task",
        goal="synthetic adaptive plan proposal",
        plan=AgentRunPlan(
            plan_id="synthetic-adaptive-plan",
            version="1",
            goal="synthetic adaptive plan proposal",
            nodes=[
                RuntimeNode(
                    node_id="verify",
                    node_type="verification",
                    handler_id="runtime.verify",
                )
            ],
        ),
    )
    failed_verification = RuntimeObservation(
        node_id="verify",
        terminal_status=RuntimeNodeStatus.PARTIAL,
        facts={"passed": False, "replan_required": True},
    )
    base_run.nodes["verify"] = RuntimeNodeState(
        node_id="verify",
        status=RuntimeNodeStatus.PARTIAL,
        observation=failed_verification,
    )
    base_run.observations.append(failed_verification)
    base_run.last_decision = RuntimeDecision(
        action=DecisionAction.REPLAN,
        reason_codes=["verification_requires_recovery"],
    )
    proposed_plan = base_run.plan.model_copy(
        update={
            "version": "2",
            "nodes": [
                *base_run.plan.nodes,
                RuntimeNode(
                    node_id="execute.recovery",
                    node_type="provider",
                    handler_id="provider.recovery",
                    depends_on=["verify"],
                ),
            ],
        }
    )
    proposal = RuntimePlanProposal(
        proposal_id="synthetic-plan-proposal",
        task_id=base_run.task_id,
        run_id=base_run.run_id,
        base_iteration=0,
        target_iteration=1,
        base_state_version=1,
        state_version=2,
        base_plan_id=base_run.plan.plan_id,
        base_plan_version=base_run.plan.version,
        proposed_plan=proposed_plan,
        reason_codes=["verification_requires_recovery"],
        rationale="Synthetic verification failure requires a recovery action.",
        affected_node_ids=["execute.recovery"],
        budget_impact=RuntimePlanBudgetImpact(model_calls=1),
        status=RuntimePlanProposalStatus.PENDING,
    )
    return RuntimePlanProposalSuite(
        suite_id="runtime_plan_proposals_ci_synthetic",
        suite_version="2",
        require_semantic_alignment=True,
        cases=[
            RuntimePlanProposalEvaluationCase(
                case_id="synthetic-recovery",
                base_run=base_run,
                proposal=proposal,
                semantic_expectation=RuntimePlanProposalSemanticExpectation(
                    verification_node_ids=["verify"],
                    verification_reason_codes=["verification_requires_recovery"],
                ),
            )
        ],
    )


def main(output_path: str) -> int:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_fixture().model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: python scripts/create_synthetic_runtime_plan_proposal_fixture.py "
            "OUTPUT.json"
        )
    raise SystemExit(main(sys.argv[1]))
