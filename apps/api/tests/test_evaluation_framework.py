from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, Intent
from app.core.config import Settings
from app.evaluation.cache import EvaluationCache
from app.evaluation.contracts import (
    EvaluationCase,
    EvaluationErrorType,
    EvaluationResult,
    FailureStage,
    SuiteReport,
)
from app.evaluation.loader import EvaluationCaseLoader
from app.evaluation.reporting import render_markdown, write_report
from app.evaluation.runner import EvaluationRunner
from app.evaluation.scorers import EvaluationScorer, normalize_text
from app.observability import ModelTracer
from app.tools import default_tool_registry
from fastapi import FastAPI
from pydantic import ValidationError

from scripts.run_evaluation import parse_args, validate_cases, validate_paid_guard

ROOT = Path(__file__).resolve().parents[3]


def make_case(**updates: object) -> EvaluationCase:
    value: dict[str, object] = {
        "case_id": "CASE_001",
        "title": "case",
        "course": "CT",
        "task_family": "ACADEMIC_SOLVING",
        "intent": "solve_problem",
        "difficulty": "easy",
        "input_type": "text",
        "message": "求x",
        "expected_agent": "ACADEMIC_PROBLEM_SOLVER",
        "expected_course_pack": "CT",
        "expected_execution_paths": ["FAST"],
    }
    value.update(updates)
    return EvaluationCase.model_validate(value)


def make_actual(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "task_status": "completed",
        "task_families": ["ACADEMIC_SOLVING"],
        "course": "CT",
        "intent": "solve_problem",
        "agent_id": "ACADEMIC_PROBLEM_SOLVER",
        "course_pack": "CT",
        "execution_path": "FAST",
        "status": "success",
        "answer": "x=2 V",
        "structured_result": {
            "course": "CT",
            "problem_summary": "求x",
            "intermediate_results": [{"x": "2 V"}],
        },
        "selected_tools": [],
        "tool_calls": [],
        "citations": [],
        "warnings": [],
        "assumptions": [],
        "remaining_risks": [],
    }
    value.update(updates)
    return value


def scorer() -> EvaluationScorer:
    return EvaluationScorer(default_tool_registry())


def score(case: EvaluationCase, actual: dict[str, object]) -> EvaluationResult:
    return scorer().score(
        case,
        actual,
        elapsed_ms=10,
        model_calls=[],
        trace_id="trace",
    )


def test_case_schema_defaults_and_rejects_invalid_path() -> None:
    assert make_case().expected_statuses == ["success", "partial"]
    with pytest.raises(ValidationError):
        make_case(expected_execution_paths=["EXPENSIVE"])


def test_case_schema_rejects_citation_count_when_citations_forbidden() -> None:
    with pytest.raises(ValidationError):
        make_case(expected_citations=False, min_citation_count=1)


def test_loader_reads_exactly_36_unique_cases() -> None:
    cases = EvaluationCaseLoader(ROOT / "evaluation" / "cases").load_all()
    assert len(cases) == 36
    assert len({item.case_id for item in cases}) == 36


def test_loader_filters_course_tag_case_and_limit() -> None:
    loader = EvaluationCaseLoader(ROOT / "evaluation" / "cases")
    cases = loader.load_all()
    assert len(loader.filter(cases, course="CT")) == 12
    assert loader.filter(cases, tags={"high_risk"})[0].case_id == "CT_CONTROLLED_001"
    assert loader.filter(cases, case_id="CT_KCL_001")[0].course == "CT"
    assert len(loader.filter(cases, max_cases=3)) == 3


def test_explicit_ss_course_is_preserved_by_formal_router() -> None:
    decision = TaskRouter(
        AgentRegistry(), Settings(app_env="test", rag_enabled=False, _env_file=None)
    ).route(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id="SS",
            intent=Intent.SOLVE_PROBLEM,
            canonical_input={"text": "判断系统是否线性"},
        )
    )
    assert decision.course_id == "SS"
    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"


def test_text_normalization_handles_width_case_and_math_symbols() -> None:
    assert normalize_text("Ａ×B − C") == "a*b - c"


def test_route_and_path_scorer_identifies_mismatch_stage() -> None:
    result = score(make_case(), make_actual(task_families=["KNOWLEDGE_QA"]))
    assert result.route_passed is False
    assert result.failure_stage == FailureStage.ROUTING
    assert EvaluationErrorType.ROUTE_MISMATCH in result.error_types


def test_keyword_step_and_forbidden_claim_scoring() -> None:
    case = make_case(
        required_keywords=["节点电压"],
        required_steps=["列KCL"],
        forbidden_claims=["忽略方向"],
    )
    result = score(case, make_actual(answer="节点电压；忽略方向"))
    assert result.missing_keywords == []
    assert result.missing_steps == ["列KCL"]
    assert result.forbidden_claims_found == ["忽略方向"]
    assert result.safety_passed is False


@pytest.mark.parametrize(
    ("expected", "actual", "passed"),
    [
        ("2 V", "2.0001 V", True),
        ("2+3j", "2.00001+3.00001j", True),
        ("10∠30deg", "8.660254+5j", True),
        ("1000 mV", "1 V", True),
        ("2 V", "3 V", False),
    ],
)
def test_numeric_scorer_supports_tolerance_complex_angle_and_units(
    expected: str, actual: str, passed: bool
) -> None:
    case = make_case(reference_values={"x": expected}, numeric_tolerance=0.001)
    observation = make_actual(
        structured_result={
            "course": "CT",
            "problem_summary": "求x",
            "intermediate_results": [{"x": actual}],
        }
    )
    result = score(case, observation)
    assert result.numeric_comparisons[0]["passed"] is passed


def test_tool_scorer_distinguishes_disabled_not_selected_and_forbidden() -> None:
    disabled = score(make_case(expected_tools=["boolean_simplifier"]), make_actual())
    assert disabled.tool_mismatches == [
        {"tool_id": "boolean_simplifier", "reason": "tool_disabled"}
    ]
    missing = score(make_case(expected_tools=["linear_equation_solver"]), make_actual())
    assert missing.tool_mismatches[0]["reason"] == "not_selected"
    forbidden = score(
        make_case(forbidden_tools=["calculator"]),
        make_actual(selected_tools=["calculator"]),
    )
    assert forbidden.tool_mismatches[0]["reason"] == "forbidden_tool"


def test_citation_scorer_checks_presence_and_minimum() -> None:
    case = make_case(expected_citations=True, min_citation_count=2)
    failed = score(case, make_actual(citations=["kb://one"]))
    passed = score(case, make_actual(citations=["kb://one", "kb://two"]))
    assert failed.citations_passed is False
    assert passed.citations_passed is True


def test_insufficient_information_scoring_requires_risk_and_conditional_answer() -> (
    None
):
    case = make_case(tags=["insufficient"], expected_statuses=["partial"])
    failed = score(case, make_actual(status="partial", answer="结果为10"))
    passed = score(
        case,
        make_actual(
            status="partial",
            answer="信息不足，无法唯一求解",
            remaining_risks=["缺少电阻"],
        ),
    )
    assert failed.answer_passed is False
    assert passed.answer_passed is True


def test_cache_key_save_load_and_failed_result_resume_metadata(tmp_path: Path) -> None:
    cache = EvaluationCache(tmp_path, fingerprint="one")
    key = cache.key(make_case(), mode="offline")
    result = score(make_case(), make_actual(task_families=[]))
    cache.save(key, result)
    loaded = cache.load(key)
    assert loaded is not None
    assert loaded.status == "failed"
    assert (
        EvaluationCache(tmp_path, fingerprint="two").key(make_case(), mode="offline")
        != key
    )


def test_markdown_and_json_report_generation(tmp_path: Path) -> None:
    case = make_case()
    result = score(case, make_actual())
    report = SuiteReport(
        mode="offline",
        started_at="start",
        completed_at="end",
        summary={
            "total": 1,
            "passed": 1,
            "failed": 0,
            "errors": 0,
            "timeouts": 0,
            "pass_rate": 1.0,
        },
        statistics={
            "by_course": {"CT": {"total": 1, "pass_rate": 1.0}},
            "routing_accuracy": 1.0,
            "model_calls_total": 0,
            "average_model_calls_per_case": 0.0,
            "average_elapsed_ms": 10,
            "p50_elapsed_ms": 10,
            "p95_elapsed_ms": 10,
            "fallback_rate": 0.0,
            "timeout_rate": 0.0,
            "high_risk_conflicts": 0,
        },
        results=[result],
    )
    json_path, markdown_path = write_report(report, tmp_path)
    assert json_path.is_file()
    assert "总体通过率" in markdown_path.read_text(encoding="utf-8")
    assert "完整模型回答" not in render_markdown(report)


def test_live_mode_without_explicit_paid_confirmation_is_blocked() -> None:
    args = parse_args(["--live"])
    with pytest.raises(ValueError, match="confirm-paid"):
        validate_paid_guard(args)
    validate_paid_guard(parse_args(["--live", "--confirm-paid"]))


def test_live_default_limit_is_not_silently_unbounded() -> None:
    args = parse_args(["--live", "--confirm-paid"])
    assert args.max_cases is None
    assert args.live is True
    selected, _summary = validate_cases(args)
    assert len(selected) == 3


def fake_task(*, answer: str = "x=2 V") -> dict[str, Any]:
    return {
        "status": "completed",
        "route_status": "selected",
        "route_reason": "evaluation",
        "agent_id": "ACADEMIC_PROBLEM_SOLVER",
        "course_id": "CT",
        "intent": "solve_problem",
        "input_content": {
            "options": {"_routing": {"agent_id": "ACADEMIC_PROBLEM_SOLVER"}}
        },
        "result_content": {
            "answer": answer,
            "structured_result": {
                "status": "success",
                "course": "CT",
                "problem_summary": "求x",
                "execution_path": "FAST",
                "intermediate_results": [{"x": "2 V"}],
                "solution_steps": [],
                "tool_verification": [],
            },
            "citations": [],
            "warnings": [],
            "assumptions": [],
            "remaining_risks": [],
        },
    }


def runner_without_lifespan(
    tmp_path: Path, *, rerun_failed: bool = False
) -> EvaluationRunner:
    app = FastAPI()
    app.state.model_tracer = ModelTracer()
    app.state.tool_registry = default_tool_registry()
    app.state.agent_registry = AgentRegistry()
    runner = EvaluationRunner(
        app,
        mode="offline",
        cache=EvaluationCache(tmp_path, fingerprint="test"),
        report_root=tmp_path,
        rerun_failed=rerun_failed,
    )
    runner.scorer = EvaluationScorer(app.state.tool_registry)
    return runner


@pytest.mark.asyncio
async def test_runner_uses_cached_result_without_reexecuting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = runner_without_lifespan(tmp_path)
    calls = 0

    async def execute(_case: EvaluationCase, _trace_id: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return fake_task()

    monkeypatch.setattr(runner, "_execute", execute)
    first = await runner.run_case(make_case())
    second = await runner.run_case(make_case())
    assert first.status == "passed"
    assert second.status == "passed"
    assert "result_loaded_from_cache" in second.warnings
    assert calls == 1


@pytest.mark.asyncio
async def test_runner_rerun_failed_reexecutes_cached_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed_case = make_case(required_keywords=["missing"])
    first_runner = runner_without_lifespan(tmp_path)

    async def first_execute(_case: EvaluationCase, _trace_id: str) -> dict[str, Any]:
        return fake_task(answer="no keyword")

    monkeypatch.setattr(first_runner, "_execute", first_execute)
    assert (await first_runner.run_case(failed_case)).status == "failed"
    rerun = runner_without_lifespan(tmp_path, rerun_failed=True)
    calls = 0

    async def second_execute(_case: EvaluationCase, _trace_id: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return fake_task(answer="missing")

    monkeypatch.setattr(rerun, "_execute", second_execute)
    assert (await rerun.run_case(failed_case)).status == "passed"
    assert calls == 1
