from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.runtime import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    PlanExecutor,
    RuntimeController,
    RuntimeDecision,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
    RuntimeStateMachine,
    build_runtime_observability,
)


def _plan() -> AgentRunPlan:
    return AgentRunPlan(
        plan_id="observability-plan",
        goal="observe decide verify",
        nodes=[
            RuntimeNode(
                node_id="retrieve",
                node_type="tool",
                handler_id="retrieve.handler",
            ),
            RuntimeNode(
                node_id="review",
                node_type="agent",
                handler_id="review.handler",
                depends_on=["retrieve"],
            ),
        ],
    )


def test_decisions_and_verifications_survive_checkpoint_round_trip() -> None:
    run = AgentRun(
        run_id="observability-round-trip",
        task_id="observability-task",
        goal="observe decide verify",
        plan=_plan(),
    )
    decision = RuntimeDecision(
        action=DecisionAction.EXECUTE,
        node_ids=["retrieve"],
        reason_codes=["start_retrieval"],
    )
    RuntimeStateMachine.apply_decision(run, decision)
    verification = RuntimeObservation(
        node_id="verification",
        facts={"retrieval_status": "succeeded"},
    )
    RuntimeStateMachine.record_verification(run, verification)

    restored = AgentRun.model_validate(run.model_dump(mode="json"))

    assert restored.last_decision == decision
    assert restored.decision_history == [decision]
    assert restored.verification_history == [verification]
    # A checkpoint written by an older Runtime must still restore safely.
    legacy_payload = run.model_dump(mode="json")
    legacy_payload.pop("decision_history")
    legacy_payload.pop("verification_history")
    legacy_restored = AgentRun.model_validate(legacy_payload)
    assert legacy_restored.decision_history == []
    assert legacy_restored.verification_history == []


def test_controller_projection_contains_node_level_observe_decide_verify() -> None:
    run = AgentRun(
        run_id="observability-controller",
        task_id="observability-task",
        goal="observe decide verify",
        plan=_plan(),
    )
    decisions = iter(
        [
            RuntimeDecision(
                action=DecisionAction.EXECUTE,
                node_ids=["retrieve"],
                reason_codes=["retrieve_first"],
            ),
            RuntimeDecision(
                action=DecisionAction.EXECUTE,
                node_ids=["review"],
                reason_codes=["review_result"],
            ),
        ]
    )

    def decide(_run: AgentRun) -> RuntimeDecision:
        return next(decisions)

    def verify(current: AgentRun) -> RuntimeObservation:
        return RuntimeObservation(
            node_id="verification",
            facts={"iteration_status": current.status.value},
        )

    def retrieve(_run: AgentRun, _node: RuntimeNode) -> RuntimeObservation:
        return RuntimeObservation(node_id="retrieve", facts={"count": 1})

    def review(_run: AgentRun, _node: RuntimeNode) -> RuntimeObservation:
        return RuntimeObservation(node_id="review", facts={"approved": True})

    asyncio.run(
        RuntimeController(
            PlanExecutor(
                {
                    "retrieve.handler": retrieve,
                    "review.handler": review,
                }
            ),
            decide,
            verifier=verify,
        ).run(run)
    )

    projection = build_runtime_observability(run)
    assert run.status == RuntimeRunStatus.COMPLETED
    assert [item["action"] for item in projection["decisions"]] == [
        "execute",
        "execute",
    ]
    assert len(projection["observations"]) == 2
    assert len(projection["verifications"]) == 2
    retrieve_projection = next(
        item for item in projection["nodes"] if item["node_id"] == "retrieve"
    )
    assert retrieve_projection["observation"]["facts"] == {"count": 1}
    assert retrieve_projection["decisions"][0]["reason_codes"] == [
        "retrieve_first"
    ]
    assert retrieve_projection["verifications"] == []


def test_projection_recovers_legacy_last_decision_and_verification_node() -> None:
    run = AgentRun(
        run_id="observability-legacy",
        task_id="observability-task",
        goal="observe decide verify",
        plan=AgentRunPlan(
            plan_id="legacy-plan",
            goal="observe decide verify",
            nodes=[
                RuntimeNode(
                    node_id="verify",
                    node_type="verification",
                    handler_id="verify.handler",
                )
            ],
        ),
        last_decision=RuntimeDecision(
            action=DecisionAction.EXECUTE,
            node_ids=["verify"],
        ),
    )
    RuntimeStateMachine.mark_ready(run)
    RuntimeStateMachine.start_node(run, "verify")
    RuntimeStateMachine.complete_node(
        run,
        "verify",
        status=RuntimeNodeStatus.SUCCEEDED,
        observation=RuntimeObservation(
            node_id="verify", facts={"phase": "verify", "passed": True}
        ),
    )

    projection = build_runtime_observability(run)

    assert len(projection["decisions"]) == 1
    assert projection["verifications"][0]["facts"]["passed"] is True


def test_projection_includes_durable_run_and_node_timings() -> None:
    run = AgentRun(
        run_id="observability-timing",
        task_id="observability-task",
        goal="observe timing",
        plan=_plan(),
    )
    started_at = datetime(2026, 8, 10, tzinfo=UTC)
    run.started_at = started_at
    run.completed_at = started_at + timedelta(milliseconds=450)
    retrieve = run.nodes["retrieve"]
    retrieve.started_at = started_at
    retrieve.completed_at = started_at + timedelta(milliseconds=120)
    retrieve.status = RuntimeNodeStatus.SUCCEEDED
    review = run.nodes["review"]
    review.started_at = started_at + timedelta(milliseconds=125)
    review.completed_at = started_at + timedelta(milliseconds=375)
    review.status = RuntimeNodeStatus.SUCCEEDED

    projection = build_runtime_observability(run)

    assert projection["timing"] == {
        "run_started_at": "2026-08-10T00:00:00+00:00",
        "run_completed_at": "2026-08-10T00:00:00.450000+00:00",
        "run_elapsed_ms": 450,
        "completed_node_elapsed_ms": 370,
        "active_node_wall_ms": 370,
        "runtime_control_overhead_ms": 80,
        "slowest_completed_node_elapsed_ms": 250,
    }
    nodes = {item["node_id"]: item for item in projection["nodes"]}
    assert nodes["retrieve"]["elapsed_ms"] == 120
    assert nodes["review"]["elapsed_ms"] == 250


def test_projection_merges_overlapping_node_intervals_for_control_overhead() -> None:
    run = AgentRun(
        run_id="observability-parallel-timing",
        task_id="observability-task",
        goal="observe parallel timing",
        plan=_plan(),
    )
    started_at = datetime(2026, 8, 10, tzinfo=UTC)
    run.started_at = started_at
    run.completed_at = started_at + timedelta(milliseconds=500)
    retrieve = run.nodes["retrieve"]
    retrieve.started_at = started_at
    retrieve.completed_at = started_at + timedelta(milliseconds=300)
    retrieve.status = RuntimeNodeStatus.SUCCEEDED
    review = run.nodes["review"]
    review.started_at = started_at + timedelta(milliseconds=100)
    review.completed_at = started_at + timedelta(milliseconds=400)
    review.status = RuntimeNodeStatus.SUCCEEDED

    timing = build_runtime_observability(run)["timing"]

    assert timing["completed_node_elapsed_ms"] == 600
    assert timing["active_node_wall_ms"] == 400
    assert timing["runtime_control_overhead_ms"] == 100
