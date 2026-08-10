from __future__ import annotations

from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeNode,
    RuntimeNodeState,
    RuntimeNodeStatus,
    RuntimeRunStatus,
    SolverParityPair,
    SolverParitySuite,
    SolverParityThresholds,
    evaluate_solver_parity_suite,
)


def _checkpoints() -> list[dict[str, object]]:
    run = AgentRun(
        run_id="run-parity",
        task_id="task-parity",
        goal="solve",
        plan=AgentRunPlan(
            plan_id="solver-parity",
            goal="solve",
            nodes=[
                RuntimeNode(
                    node_id="solver.observe",
                    node_type="verification",
                    handler_id="academic.solver.observe",
                ),
                RuntimeNode(
                    node_id="solver.execute",
                    node_type="provider",
                    handler_id="academic.solver.execute",
                    depends_on=["solver.observe"],
                ),
                RuntimeNode(
                    node_id="solver.verify",
                    node_type="verification",
                    handler_id="academic.solver.verify",
                    depends_on=["solver.execute"],
                ),
            ],
        ),
    )
    initial = run.model_dump(mode="json")
    for node_id in run.nodes:
        run.nodes[node_id] = RuntimeNodeState(
            node_id=node_id,
            status=RuntimeNodeStatus.SUCCEEDED,
        )
    run.status = RuntimeRunStatus.COMPLETED
    run.state_version = 2
    completed = run.model_dump(mode="json")
    return [
        {"sequence": 1, "state_version": 1, "state_data": initial},
        {"sequence": 2, "state_version": 2, "state_data": completed},
    ]


def _payload(
    *, status: str = "completed", latency_ms: int = 100, model_calls: int = 2
) -> dict[str, object]:
    return {
        "status": status,
        "provider": "local_graph",
        "result_content": {
            "answer": "The equivalent resistance is 10 ohms.",
            "metrics": {
                "latency_ms": latency_ms,
                "model_calls": model_calls,
            },
        },
    }


def _pair(
    case_id: str, *, runtime: dict[str, object] | None = None
) -> SolverParityPair:
    return SolverParityPair(
        case_id=case_id,
        legacy_payload=_payload(),
        runtime_payload=runtime or _payload(),
        runtime_checkpoints=_checkpoints(),
        required_handler_ids={
            "academic.solver.observe",
            "academic.solver.execute",
            "academic.solver.verify",
        },
    )


def test_solver_parity_suite_allows_canary_when_pairs_meet_thresholds() -> None:
    report = evaluate_solver_parity_suite(
        SolverParitySuite(
            suite_id="solver-parity-test",
            thresholds=SolverParityThresholds(min_pairs=2),
            pairs=[_pair("ct-text"), _pair("ct-rag")],
        )
    )

    assert report.canary_eligible is True
    assert report.pair_count == 2
    assert report.passed_pair_count == 2
    assert report.failed_checks == []
    assert report.trace_invalid_rate == 0


def test_solver_parity_suite_blocks_canary_on_trace_and_operational_regression() -> (
    None
):
    failed = _payload(status="failed", latency_ms=250, model_calls=5)
    failed_pair = _pair("ct-failure", runtime=failed).model_copy(
        update={"runtime_checkpoints": []}
    )
    report = evaluate_solver_parity_suite(
        SolverParitySuite(
            suite_id="solver-parity-failure",
            thresholds=SolverParityThresholds(
                min_pairs=1,
                max_latency_regression_ratio=0.5,
                max_model_call_regression_ratio=0.5,
            ),
            pairs=[failed_pair],
        )
    )

    assert report.canary_eligible is False
    assert "status_mismatch_rate_above_threshold" in report.failed_checks
    assert "trace_invalid_rate_above_threshold" in report.failed_checks
    assert "latency_regression_above_threshold" in report.failed_checks
    assert "model_call_regression_above_threshold" in report.failed_checks


def test_solver_parity_rejects_single_latency_outlier_hidden_by_aggregate() -> None:
    required_handlers = {
        "academic.solver.observe",
        "academic.solver.execute",
        "academic.solver.verify",
    }
    report = evaluate_solver_parity_suite(
        SolverParitySuite(
            suite_id="solver-parity-outlier",
            thresholds=SolverParityThresholds(
                max_latency_regression_ratio=0.5,
                max_single_pair_latency_regression_ratio=0.5,
            ),
            pairs=[
                _pair("slow-runtime", runtime=_payload(latency_ms=200)),
                SolverParityPair(
                    case_id="fast-runtime",
                    legacy_payload=_payload(latency_ms=1_000),
                    runtime_payload=_payload(latency_ms=100),
                    runtime_checkpoints=_checkpoints(),
                    required_handler_ids=required_handlers,
                ),
            ],
        )
    )

    assert report.latency_regression_ratio == 0
    assert report.single_pair_latency_regression_count == 1
    assert report.canary_eligible is False
    assert "single_pair_latency_regression_above_threshold" in report.failed_checks
    assert report.results[0].passed is False
