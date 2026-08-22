from __future__ import annotations

from typing import Any

from app.evaluation.contracts import (
    EvaluationCase,
    EvaluationErrorType,
    EvaluationResult,
    FailureStage,
    SuiteReport,
)
from app.evaluation.loop import (
    EvaluationRecord,
    EvaluationRecordAdapter,
    FailureAttributor,
    FailurePatternAggregator,
    ImprovementProposalService,
    LoopFailureStage,
    OfflineReplayService,
    PromotionGovernance,
)


def _case(case_id: str, *, source_type: str = "synthetic") -> EvaluationCase:
    return EvaluationCase(
        case_id=case_id,
        title=case_id,
        course="CT",
        task_family="ACADEMIC_SOLVING",
        intent="solve_problem",
        message="受保护的题目内容不应进入 loop record",
        expected_agent="ACADEMIC_PROBLEM_SOLVER",
        problem_type="kcl",
        provenance={"source_type": source_type},
    )


def _result(
    case_id: str,
    *,
    score: float,
    status: str = "failed",
    failure_stage: FailureStage | None = FailureStage.ROUTING,
    error_types: list[EvaluationErrorType] | None = None,
    actual: dict[str, Any] | None = None,
) -> EvaluationResult:
    return EvaluationResult(
        case_id=case_id,
        status=status,  # type: ignore[arg-type]
        route_passed=status == "passed",
        course_passed=True,
        agent_passed=status == "passed",
        structure_passed=True,
        execution_path_passed=True,
        tools_passed=True,
        answer_passed=status == "passed",
        citations_passed=True,
        safety_passed=True,
        total_score=score,
        expected={"course": "CT", "agent_id": "ACADEMIC_PROBLEM_SOLVER"},
        actual=actual
        or {
            "course": "CT",
            "planner_version": "planner.v1",
            "skill_ids": ["CT.KCL"],
            "answer": "secret answer",
            "metrics": {"cost": 0.1},
        },
        failure_stage=failure_stage,
        error_types=error_types or [EvaluationErrorType.ROUTE_MISMATCH],
        elapsed_ms=100,
        trace_id=f"trace-{case_id}",
    )


def _report(results: list[EvaluationResult], mode: str = "offline") -> SuiteReport:
    return SuiteReport(
        mode=mode,  # type: ignore[arg-type]
        started_at="2026-08-23T00:00:00+00:00",
        completed_at="2026-08-23T00:01:00+00:00",
        summary={
            "total": len(results),
            "passed": sum(item.status == "passed" for item in results),
            "failed": sum(item.status == "failed" for item in results),
            "errors": 0,
            "timeouts": 0,
            "cached": 0,
        },
        statistics={},
        results=results,
    )


def _record(case_id: str, score: float, *, status: str = "passed") -> EvaluationRecord:
    return EvaluationRecord(
        suite_id="suite",
        case_id=case_id,
        evidence_level="offline_real_case",
        task_family="ACADEMIC_SOLVING",
        course="CT",
        capability="kcl",
        expected_outcome={"course": "CT"},
        actual_outcome={"skill_ids": ["CT.KCL"], "selected_tools": ["calculator"]},
        score_dimensions={"safety": 100, "correctness": score},
        overall_score=score,
        status=status,  # type: ignore[arg-type]
        planner_version="planner.v1",
        plan_version="plan.v1",
        model_provider_version="mock:v1",
        reflection_version="reflection.v1",
        latency_ms=100,
        tokens=10,
        cost=0.1,
        reproducible=True,
    )


def test_adapter_is_authoritative_and_redacts_raw_answer() -> None:
    report = _report([_result("case-1", score=40)])
    record = EvaluationRecordAdapter.from_suite_report(
        report, [_case("case-1")], suite_id="full-suite"
    )[0]

    assert record.suite_id == "full-suite"
    assert record.run_id == ""
    assert "answer" not in record.actual_outcome
    failure = FailureAttributor().attribute(record)
    assert failure is not None
    assert failure.stage == LoopFailureStage.ROUTING
    assert failure.owner_component == "router"
    assert failure.evidence_refs == ["trace-case-1", record.evaluation_id]


def test_failure_patterns_require_reproducible_non_transient_evidence() -> None:
    failures = [
        FailureAttributor().attribute(_record("case-1", 40, status="failed")),
        FailureAttributor().attribute(_record("case-2", 30, status="failed")),
    ]
    assert all(item is not None for item in failures)
    patterns = FailurePatternAggregator().aggregate(
        [item for item in failures if item is not None]
    )
    assert len(patterns) == 1
    assert patterns[0].occurrence_count == 2
    assert patterns[0].generalizable is True
    assert patterns[0].aggregation_eligible is True


def test_replay_compares_same_cases_and_blocks_critical_regression() -> None:
    baseline = [_record("case-1", 40, status="failed"), _record("case-2", 100)]
    candidate = [_record("case-1", 80), _record("case-2", 100)]
    pattern = FailurePatternAggregator().aggregate(
        [FailureAttributor().attribute(baseline[0])]  # type: ignore[list-item]
    )[0]
    proposal = ImprovementProposalService.create(
        pattern,
        proposal_type="verification_rule",
        target_component="verification",
        target_version="v2",
        problem_statement="route evidence is incomplete",
        proposed_change="add a route evidence assertion",
        expected_effect="reduce route failures",
        success_metrics={"failure_rate": 0},
        risk="false positives",
        estimated_cost=1,
        required_cases=["case-1", "case-2"],
        rollback_plan="disable the candidate rule",
    )
    replay = OfflineReplayService().compare(
        proposal,
        baseline,
        candidate,
        baseline_id="baseline-v1",
        candidate_id="candidate-v2",
    )
    assert replay.gate_passed is True
    assert replay.improved == 1
    assert replay.critical_regressions == []

    bad_candidate = [_record("case-1", 80), _record("case-2", 10, status="failed")]
    bad = OfflineReplayService().compare(
        proposal,
        baseline,
        bad_candidate,
        baseline_id="baseline-v1",
        candidate_id="candidate-bad",
    )
    assert bad.gate_passed is False
    assert "case-2" in bad.critical_regressions


def test_promotion_is_governed_and_only_emits_experience_candidate() -> None:
    baseline = [_record("case-1", 40, status="failed"), _record("case-2", 100)]
    candidate = [_record("case-1", 80), _record("case-2", 100)]
    failure = FailureAttributor().attribute(baseline[0])
    assert failure is not None
    pattern = FailurePatternAggregator().aggregate([failure])[0]
    pattern = pattern.model_copy(
        update={
            "occurrence_count": 2,
            "generalizable": True,
            "aggregation_eligible": True,
        }
    )
    proposal = ImprovementProposalService.create(
        pattern,
        proposal_type="verification_rule",
        target_component="verification",
        target_version="v2",
        problem_statement="repeated route evidence gap",
        proposed_change="add an evidence assertion",
        expected_effect="improve route correctness",
        success_metrics={"score_delta": ">=0"},
        risk="false positive",
        estimated_cost=1,
        required_cases=["case-1", "case-2"],
        rollback_plan="disable v2",
    )
    for status in ("reviewed", "replay_ready", "validated"):
        proposal = ImprovementProposalService.transition(proposal, status)  # type: ignore[arg-type]
    replay = OfflineReplayService().compare(
        proposal, baseline, candidate, baseline_id="b", candidate_id="c"
    )
    decision = PromotionGovernance().decide(proposal, replay, reviewer="human")
    assert decision.status == "approve"
    assert decision.eligible_targets == ["experience_candidate"]
    experience = PromotionGovernance.to_experience_candidate(
        proposal, pattern, decision
    )
    assert experience.lifecycle_status.value == "candidate"
    assert experience.scope.value == "global_deidentified"
