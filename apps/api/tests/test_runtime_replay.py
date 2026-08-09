from __future__ import annotations

from datetime import UTC, datetime

from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeCanaryEvidence,
    RuntimeCanaryPair,
    RuntimeCanarySuite,
    RuntimeCanaryThresholds,
    RuntimeCheckpointRecord,
    RuntimeEvaluationCase,
    RuntimeLaunchSnapshot,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeRunStatus,
    RuntimeStateMachine,
    audit_checkpoint_trace,
    build_runtime_legacy_diff,
    build_runtime_parity_snapshot,
    evaluate_runtime_canary_suite,
    evaluate_runtime_run,
)


def test_runtime_checkpoint_trace_is_auditable_and_reproducible() -> None:
    run = AgentRun(
        run_id="run-replay",
        task_id="task-replay",
        goal="replay",
        plan=AgentRunPlan(
            plan_id="plan-replay",
            goal="replay",
            nodes=[
                RuntimeNode(
                    node_id="step",
                    node_type="tool",
                    handler_id="tool.step",
                )
            ],
        ),
    )
    first = RuntimeCheckpointRecord(
        sequence=1,
        state_version=1,
        state_data=run.model_dump(mode="json"),
    )
    RuntimeStateMachine.mark_ready(run)
    RuntimeStateMachine.start_node(run, "step")
    RuntimeStateMachine.complete_node(
        run,
        "step",
        status=RuntimeNodeStatus.SUCCEEDED,
    )
    completed = run.model_copy(update={"state_version": 2})
    second = RuntimeCheckpointRecord(
        sequence=2,
        state_version=2,
        state_data=completed.model_dump(mode="json"),
    )

    audit = audit_checkpoint_trace([second, first])
    assert audit.valid is True
    assert audit.run_id == "run-replay"
    assert audit.checkpoint_count == 2
    assert audit.final_status == "completed"
    assert audit.first_event_sequence == 0
    assert audit.last_event_sequence == 0

    evaluation = evaluate_runtime_run(
        completed,
        RuntimeEvaluationCase(
            case_version="1",
            case_id="replay-case",
            expected_status=RuntimeRunStatus.COMPLETED,
            required_node_statuses={"step": RuntimeNodeStatus.SUCCEEDED},
            required_handler_ids={"tool.step"},
        ),
        checkpoint_count=audit.checkpoint_count,
    )
    assert evaluation.passed is True
    assert evaluation.failed_checks == []


def test_runtime_checkpoint_trace_rejects_gaps_and_version_mismatch() -> None:
    run = AgentRun(
        run_id="run-invalid-replay",
        task_id="task-invalid-replay",
        goal="replay",
        plan=AgentRunPlan(
            plan_id="plan-invalid-replay",
            goal="replay",
            nodes=[
                RuntimeNode(
                    node_id="step",
                    node_type="tool",
                    handler_id="tool.step",
                )
            ],
        ),
    )
    audit = audit_checkpoint_trace(
        [
            RuntimeCheckpointRecord(
                sequence=2,
                state_version=2,
                state_data=run.model_dump(mode="json"),
            )
        ]
    )
    assert audit.valid is False
    assert "checkpoint_sequence_gap:1->2" in audit.errors
    assert "checkpoint_state_version_mismatch" in audit.errors


def test_runtime_checkpoint_trace_rejects_event_sequence_regression() -> None:
    run = AgentRun(
        run_id="run-event-order",
        task_id="task-event-order",
        goal="replay event order",
        plan=AgentRunPlan(
            plan_id="plan-event-order",
            goal="replay event order",
            nodes=[
                RuntimeNode(
                    node_id="step",
                    node_type="tool",
                    handler_id="tool.step",
                )
            ],
        ),
    )

    audit = audit_checkpoint_trace(
        [
            RuntimeCheckpointRecord(
                sequence=1,
                state_version=1,
                event_sequence=8,
                state_data=run.model_dump(mode="json"),
            ),
            RuntimeCheckpointRecord(
                sequence=2,
                state_version=2,
                event_sequence=7,
                state_data=run.model_copy(
                    update={"state_version": 2}
                ).model_dump(mode="json"),
            ),
        ]
    )

    assert audit.valid is False
    assert "checkpoint_event_sequence_regressed" in audit.errors
    assert audit.first_event_sequence == 8
    assert audit.last_event_sequence == 7


def test_runtime_legacy_diff_reports_structural_parity_without_semantic_claims(
) -> None:
    legacy = {
        "status": "completed",
        "provider": "local_agent",
        "result_content": {
            "answer": "legacy answer",
            "structured_result": {"summary": "ok", "citations": []},
        },
        "artifact_ids": ["artifact-1"],
    }
    runtime = {
        "status": "completed",
        "provider": "local_agent",
        "result_content": {
            "answer": "runtime answer",
            "structured_result": {"summary": "ok", "evidence": []},
        },
        "artifact_ids": ["artifact-1", "artifact-2"],
        "run_id": "run-parity",
        "nodes": {
            "general.execute": {"status": "succeeded"},
        },
    }

    snapshot = build_runtime_parity_snapshot(runtime, source="runtime")
    report = build_runtime_legacy_diff(legacy, runtime)

    assert snapshot.runtime_run_id == "run-parity"
    assert snapshot.runtime_node_statuses == {
        "general.execute": "succeeded"
    }
    assert report.status_match is True
    assert report.answer_presence_match is True
    assert report.provider_match is True
    assert report.artifact_count_delta == 1
    assert report.structured_result_keys_added == ["evidence"]
    assert report.structured_result_keys_removed == ["citations"]
    assert report.canary_eligible is False
    assert report.semantic_equivalence == "not_evaluated"
    assert report.warnings


def test_runtime_canary_aggregate_reports_operational_and_recovery_metrics() -> None:
    run = AgentRun(
        run_id="run-canary",
        task_id="task-canary",
        goal="canary",
        plan=AgentRunPlan(
            plan_id="plan-canary",
            goal="canary",
            nodes=[
                RuntimeNode(
                    node_id="execute",
                    node_type="provider",
                    handler_id="provider.execute",
                )
            ],
        ),
    )
    RuntimeStateMachine.mark_ready(run)
    RuntimeStateMachine.start_node(run, "execute")
    RuntimeStateMachine.complete_node(
        run,
        "execute",
        status=RuntimeNodeStatus.SUCCEEDED,
    )
    run.state_version = 2
    trace = [
        RuntimeCheckpointRecord(
            sequence=1,
            state_version=1,
            state_data=AgentRun(
                run_id="run-canary",
                task_id="task-canary",
                goal="canary",
                plan=run.plan,
            ).model_dump(mode="json"),
        ).model_dump(mode="json"),
        RuntimeCheckpointRecord(
            sequence=2,
            state_version=2,
            state_data=run.model_dump(mode="json"),
        ).model_dump(mode="json"),
    ]
    legacy = {
        "status": "completed",
        "provider": "local_agent",
        "answer": "same shape",
        "metrics_data": {"latency_ms": 100, "model_calls": 2},
    }
    runtime = {
        "status": "completed",
        "provider": "local_agent",
        "answer": "same shape",
        "metrics_data": {"latency_ms": 120, "model_calls": 2},
        "runtime": {
            "nodes": [
                {
                    "error_code": "in_flight_execution_requires_reconciliation"
                }
            ]
        },
        "events": [
            {
                "type": "agent.progress",
                "data": {"status": "reconciled"},
            }
        ],
    }
    suite = RuntimeCanarySuite(
        suite_id="runtime-canary-test",
        thresholds=RuntimeCanaryThresholds(
            min_pairs=1,
            max_latency_regression_ratio=0.5,
        ),
        pairs=[
            RuntimeCanaryPair(
                case_id="case-1",
                legacy_payload=legacy,
                runtime_payload=runtime,
                runtime_checkpoints=trace,
            )
        ],
    )

    report = evaluate_runtime_canary_suite(suite)

    assert report.canary_eligible is True
    assert report.status_mismatch_rate == 0
    assert report.latency_regression_ratio == 0.2
    assert report.recovery_required_count == 1
    assert report.reconciled_count == 1
    assert report.unreconciled_recovery_count == 0
    assert report.release_eligible is False


def test_runtime_canary_release_requires_authorized_redacted_evidence() -> None:
    checkpoint_run = AgentRun(
        run_id="run-authorized",
        task_id="task-authorized",
        goal="authorized canary",
        plan=AgentRunPlan(
            plan_id="plan-authorized",
            version="general-qa-v1",
            goal="authorized canary",
            nodes=[
                RuntimeNode(
                    node_id="final",
                    node_type="terminal",
                    handler_id="runtime.final",
                )
            ],
        ),
        launch_decision=RuntimeLaunchSnapshot(
            agent_id="GENERAL_QUESTION_V1",
            mode="canary",
            source="test",
            reason="authorized paired trace test",
        ),
    )
    suite = RuntimeCanarySuite(
        suite_id="runtime-canary-authorized",
        evidence=RuntimeCanaryEvidence(
            kind="authorized_paired",
            agent_id="GENERAL_QUESTION_V1",
            agent_version="1.0",
            runtime_plan_version="general-qa-v1",
            authorization_ref="change-123",
            captured_at=datetime(2026, 8, 9, tzinfo=UTC),
            redaction_status="redacted",
        ),
        pairs=[
            RuntimeCanaryPair(
                case_id="case-authorized",
                legacy_payload={
                    "agent_id": "GENERAL_QUESTION_V1",
                    "status": "completed",
                    "answer": "same",
                },
                runtime_payload={
                    "agent_id": "GENERAL_QUESTION_V1",
                    "status": "completed",
                    "answer": "same",
                },
                runtime_checkpoints=[
                    RuntimeCheckpointRecord(
                        sequence=1,
                        state_version=1,
                        state_data=checkpoint_run.model_dump(mode="json"),
                    ).model_dump(mode="json")
                ],
            )
        ],
    )

    report = evaluate_runtime_canary_suite(suite)

    assert report.canary_eligible is True
    assert report.release_eligible is True
