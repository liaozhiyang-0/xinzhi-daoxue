from __future__ import annotations

import asyncio
import hashlib
import json
from io import BytesIO
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
from app.evaluation.reporting import (
    build_evaluation_run_metadata,
    build_statistics,
    evaluation_case_attachment_manifest,
    evaluation_case_catalog_content_sha256,
    evaluation_case_source_files_sha256,
    render_markdown,
    write_report,
)
from app.evaluation.runner import EvaluationRunner, evaluation_timeout_decision
from app.evaluation.scorers import EvaluationScorer, normalize_text
from app.observability import ModelTracer
from app.repositories import FileRepository
from app.tools import default_tool_registry
from fastapi import FastAPI
from PIL import Image
from pydantic import ValidationError
from pypdf import PdfWriter

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


def test_loader_reads_unique_cases() -> None:
    cases = EvaluationCaseLoader(ROOT / "evaluation" / "cases").load_all()
    assert len(cases) >= 73
    assert len({item.case_id for item in cases}) == len(cases)


def test_loader_filters_course_tag_case_and_limit() -> None:
    loader = EvaluationCaseLoader(ROOT / "evaluation" / "cases")
    cases = loader.load_all()
    assert len(loader.filter(cases, course="CT")) >= 44
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


def test_boundary_keyword_scoring_accepts_controlled_insufficient_synonyms() -> None:
    case = make_case(required_keywords=["缺少"])

    result = score(
        case,
        make_actual(answer="信息缺失，题目未提供唯一求解所需的参数。"),
    )

    assert result.missing_keywords == []
    assert result.answer_passed is True


def test_forbidden_claim_scoring_ignores_prompt_echo_and_explicit_rejection() -> None:
    case = make_case(forbidden_claims=["I1=I2"])
    rejection = score(
        case,
        make_actual(
            answer="条件不足，不能推出 I1=I2。",
            structured_result={
                "course": "CT",
                "problem_summary": "即使支路不同，也请证明 I1=I2。",
            },
        ),
    )
    assertion = score(case, make_actual(answer="由题意可得 I1=I2。"))

    assert rejection.forbidden_claims_found == []
    assert rejection.safety_passed is True
    assert assertion.forbidden_claims_found == ["I1=I2"]
    assert assertion.safety_passed is False


def test_teaching_hint_scoring_accepts_only_more_conservative_disclosure() -> None:
    case = make_case(expected_hint_level="H1")
    conservative = score(
        case,
        make_actual(expected_hint_level="H0"),
    )
    over_disclosed = score(
        case,
        make_actual(expected_hint_level="H2"),
    )

    assert conservative.status == "passed"
    assert "conservative_hint_level:H0<expected:H1" in conservative.warnings
    assert over_disclosed.status == "failed"
    assert (
        EvaluationErrorType.TEACHING_FOUNDATION_MISMATCH in over_disclosed.error_types
    )


def test_evaluation_timeout_decision_only_extends_complex_cases() -> None:
    assert evaluation_timeout_decision(make_case()) == (180, [])
    assert evaluation_timeout_decision(make_case(timeout_seconds=75)) == (
        75,
        ["explicit_case_timeout"],
    )

    visual_timeout, visual_signals = evaluation_timeout_decision(
        make_case(input_type="text_and_image", file_refs=[{"path": "question.png"}])
    )
    long_timeout, long_signals = evaluation_timeout_decision(
        make_case(message="综合分析题。" * 100)
    )

    assert visual_timeout == 240
    assert "visual_input" in visual_signals
    assert long_timeout == 240
    assert "long_problem_text" in long_signals


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


def test_evaluation_run_metadata_is_reproducible_and_safe() -> None:
    cases = [make_case(case_id="CASE_002"), make_case(case_id="CASE_001")]

    metadata = build_evaluation_run_metadata(
        cases,
        run_id="eval_run_test",
        implementation_fingerprint="fingerprint-test",
        filters={"mode": "offline", "tags": []},
        case_catalog_sha256="catalog-test",
        case_catalog_content_sha256="content-test",
        case_source_files_sha256="source-test",
        case_attachment_manifest_sha256="attachment-test",
        case_attachment_count=2,
    )

    assert metadata.run_id == "eval_run_test"
    assert metadata.case_count == 2
    assert metadata.case_ids_sha256 == hashlib.sha256(b"CASE_001\nCASE_002").hexdigest()
    assert metadata.implementation_fingerprint == "fingerprint-test"
    assert metadata.case_catalog_sha256 == "catalog-test"
    assert metadata.case_catalog_content_sha256 == "content-test"
    assert metadata.case_catalog_content_version == (
        "canonical_evaluation_case_payloads.v1"
    )
    assert metadata.case_source_files_sha256 == "source-test"
    assert metadata.case_source_files_version == "evaluation_case_source_files.v1"
    assert metadata.case_attachment_manifest_sha256 == "attachment-test"
    assert metadata.case_attachment_manifest_version == (
        "evaluation_case_attachments.v1"
    )
    assert metadata.case_attachment_count == 2
    assert metadata.filters_sha256
    assert metadata.raw_prompts_stored is False
    assert "prompt" not in metadata.model_dump()
    assert "answer" not in metadata.model_dump()


def test_case_catalog_content_fingerprint_is_order_independent_and_sensitive() -> None:
    first = make_case(case_id="CASE_001")
    second = make_case(case_id="CASE_002")
    changed = first.model_copy(update={"message": "changed content"})

    original = evaluation_case_catalog_content_sha256([first, second])
    reordered = evaluation_case_catalog_content_sha256([second, first])
    modified = evaluation_case_catalog_content_sha256([changed, second])

    assert len(original) == 64
    assert original == reordered
    assert original != modified


def test_case_source_files_fingerprint_tracks_paths_and_bytes(tmp_path: Path) -> None:
    first = tmp_path / "a.yaml"
    second = tmp_path / "nested" / "b.json"
    second.parent.mkdir()
    first.write_text("cases: []\n", encoding="utf-8")
    second.write_text('{"cases": []}\n', encoding="utf-8")

    original = evaluation_case_source_files_sha256(tmp_path)
    second.rename(tmp_path / "nested" / "renamed.json")
    renamed = evaluation_case_source_files_sha256(tmp_path)
    assert original != renamed

    renamed_path = tmp_path / "nested" / "renamed.json"
    renamed_path.write_text('{"cases": [{"case_id": "changed"}]}\n', encoding="utf-8")
    modified = evaluation_case_source_files_sha256(tmp_path)

    assert len(original) == 64
    assert renamed != modified


def test_case_attachment_manifest_is_root_limited_and_byte_sensitive(
    tmp_path: Path,
) -> None:
    image = tmp_path / "diagram.png"
    pdf = tmp_path / "nested" / "lesson.pdf"
    pdf.parent.mkdir()
    image.write_bytes(b"png-like-content")
    pdf.write_bytes(b"pdf-like-content")
    first_cases = [
        make_case(
            case_id="CASE_002",
            input_type="text_and_image",
            file_refs=[{"path": "nested/lesson.pdf"}],
        ),
        make_case(
            case_id="CASE_001",
            input_type="text_and_image",
            file_refs=[{"path": "diagram.png"}],
        ),
    ]

    original, count = evaluation_case_attachment_manifest(first_cases, tmp_path)
    reordered, reordered_count = evaluation_case_attachment_manifest(
        list(reversed(first_cases)), tmp_path
    )
    assert len(original) == 64
    assert count == reordered_count == 2
    assert original == reordered

    image.write_bytes(b"changed-image")
    changed, _ = evaluation_case_attachment_manifest(first_cases, tmp_path)
    assert original != changed

    unsafe = make_case(file_refs=[{"path": "../diagram.png"}])
    with pytest.raises(ValueError, match="case root"):
        evaluation_case_attachment_manifest([unsafe], tmp_path)

    unsupported = make_case(file_refs=[{"path": "diagram.txt"}])
    (tmp_path / "diagram.txt").write_text("not an attachment", encoding="utf-8")
    with pytest.raises(ValueError, match="image or PDF"):
        evaluation_case_attachment_manifest([unsupported], tmp_path)


def test_report_separates_execution_success_from_answer_quality_failure() -> None:
    case = make_case()
    result = score(case, make_actual())
    result.actual["answer_evaluation"] = {
        "passed": False,
        "score": 0.4,
        "verdict": "incorrect",
        "reason": "关键数值与参考答案不一致。",
    }
    statistics = build_statistics([case], [result])
    report = SuiteReport(
        mode="live",
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
        statistics=statistics,
        results=[result],
    )

    markdown = render_markdown(report)
    assert statistics["answer_judge_total"] == 1
    assert statistics["answer_judge_passed"] == 0
    assert statistics["answer_judge_pass_rate"] == 0.0
    assert "答案质量判定：0 / 1 通过" in markdown
    assert "## 5. 答案质量未通过" in markdown
    assert "CASE_001" in markdown
    assert "关键数值与参考答案不一致" in markdown
    assert "本次没有运行级评分失败" in markdown


def test_report_uses_case_level_fallback_rate_and_keeps_call_rate() -> None:
    first_case = make_case()
    second_case = make_case(case_id="CASE_002")
    first_result = score(first_case, make_actual())
    second_result = score(second_case, make_actual())
    first_result.model_calls = [
        {"model": "primary", "fallback_used": False},
        {"model": "fallback", "fallback_used": True},
    ]
    first_result.actual["fallback_used"] = True
    second_result.model_calls = [
        {"model": "primary", "fallback_used": False},
    ]

    statistics = build_statistics(
        [first_case, second_case],
        [first_result, second_result],
    )

    assert statistics["fallback_case_count"] == 1
    assert statistics["fallback_rate"] == 0.5
    assert statistics["fallback_model_call_rate"] == pytest.approx(1 / 3)


def test_live_mode_without_explicit_paid_confirmation_is_blocked() -> None:
    args = parse_args(["--live"])
    with pytest.raises(ValueError, match="confirm-paid"):
        validate_paid_guard(args)
    validate_paid_guard(parse_args(["--live", "--confirm-paid"]))


def test_live_default_limit_is_not_silently_unbounded() -> None:
    args = parse_args(["--live", "--confirm-paid"])
    assert args.max_cases is None
    assert args.live is True
    selected, summary = validate_cases(args)
    assert len(selected) == 3
    assert len(str(summary["case_catalog_sha256"])) == 64
    assert len(str(summary["case_catalog_content_sha256"])) == 64
    assert len(str(summary["case_source_files_sha256"])) == 64
    assert len(str(summary["case_attachment_manifest_sha256"])) == 64
    assert summary["case_attachment_count"] == 0


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
async def test_runner_suite_writes_complete_run_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = runner_without_lifespan(tmp_path)
    cases = [make_case(case_id="CASE_002"), make_case(case_id="CASE_001")]

    async def run_case(_case: EvaluationCase) -> EvaluationResult:
        return score(_case, make_actual())

    monkeypatch.setattr(runner, "run_case", run_case)
    report = await runner.run_suite(
        cases,
        filters={"mode": "offline"},
        case_catalog_sha256="catalog-test",
        case_catalog_content_sha256="content-test",
        case_source_files_sha256="source-test",
        case_attachment_manifest_sha256="attachment-test",
        case_attachment_count=0,
    )

    assert report.run_metadata.run_id.startswith("eval_run_")
    assert report.run_metadata.case_count == 2
    assert (
        report.run_metadata.case_ids_sha256
        == hashlib.sha256(b"CASE_001\nCASE_002").hexdigest()
    )
    assert report.run_metadata.implementation_fingerprint == "test"
    assert report.run_metadata.case_catalog_sha256 == "catalog-test"
    assert report.run_metadata.case_catalog_content_sha256 == "content-test"
    assert report.run_metadata.case_source_files_sha256 == "source-test"
    assert report.run_metadata.case_attachment_manifest_sha256 == "attachment-test"
    assert report.run_metadata.case_attachment_count == 0
    assert report.run_metadata.filters_sha256
    assert report.run_metadata.raw_prompts_stored is False
    persisted = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert persisted["run_metadata"]["run_id"] == report.run_metadata.run_id
    assert persisted["run_metadata"]["raw_prompts_stored"] is False


@pytest.mark.asyncio
async def test_runner_adapts_root_relative_files_to_attachment_refs(
    tmp_path: Path,
) -> None:
    image = tmp_path / "diagram.png"
    pdf = tmp_path / "lesson.pdf"
    image.write_bytes(b"image-bytes")
    pdf.write_bytes(b"pdf-bytes")
    runner = runner_without_lifespan(tmp_path)
    runner._case_attachment_root = tmp_path

    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self.payload

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def post(self, url: str, **kwargs: object) -> FakeResponse:
            self.calls.append({"url": url, **kwargs})
            ordinal = len(self.calls)
            return FakeResponse(
                {
                    "id": f"file_{ordinal}",
                    "filename": str(kwargs["files"]["upload"][0]),  # type: ignore[index]
                    "content_type": str(kwargs["files"]["upload"][2]),  # type: ignore[index]
                    "size_bytes": 10,
                    "storage_key": f"local:key-{ordinal}",
                    "checksum_sha256": f"checksum-{ordinal}",
                    "ingestion_status": "ready",
                    "page_count": 0,
                    "extracted_text": "",
                    "extraction_metadata": {},
                }
            )

    fake_client = FakeClient()
    runner.client = fake_client  # type: ignore[assignment]
    attachments = await runner._build_evaluation_attachments(
        make_case(
            input_type="text_and_image",
            file_refs=[{"path": "diagram.png"}, {"path": "lesson.pdf"}],
        )
    )

    assert [item["file_id"] for item in attachments] == ["file_1", "file_2"]
    assert all("path" not in item for item in attachments)
    assert [call["url"] for call in fake_client.calls] == [
        "/api/v1/files",
        "/api/v1/files",
    ]
    assert fake_client.calls[0]["data"] == {"purpose": "evaluation_attachment"}


@pytest.mark.asyncio
async def test_runner_rejects_case_files_without_explicit_root(tmp_path: Path) -> None:
    runner = runner_without_lifespan(tmp_path)
    with pytest.raises(ValueError, match="explicit case attachment root"):
        await runner._build_evaluation_attachments(
            make_case(file_refs=[{"path": "diagram.png"}])
        )


@pytest.mark.asyncio
async def test_runner_uses_local_file_api_for_mock_attachment_upload(
    app: FastAPI,
    settings: Settings,
    tmp_path: Path,
) -> None:
    image = tmp_path / "diagram.png"
    image.write_bytes(b"local-image-bytes")
    runner = EvaluationRunner(
        app,
        mode="offline",
        cache=EvaluationCache(tmp_path / "cache", fingerprint="test"),
        report_root=tmp_path / "reports",
    )

    async with runner:
        runner._case_attachment_root = tmp_path
        attachments = await runner._build_evaluation_attachments(
            make_case(file_refs=[{"path": "diagram.png"}])
        )

    assert len(attachments) == 1
    assert attachments[0]["file_id"]
    assert attachments[0]["storage_key"]
    assert attachments[0]["checksum_sha256"]
    assert attachments[0]["content_type"] == "image/png"
    assert "path" not in attachments[0]
    assert settings.local_storage_path.exists()


@pytest.mark.asyncio
async def test_runner_local_task_flow_hydrates_and_cleans_evaluation_attachment(
    app: FastAPI,
    settings: Settings,
    tmp_path: Path,
) -> None:
    image = tmp_path / "diagram.png"
    with Image.new("RGB", (2, 2), color="white") as generated:
        generated.save(image, format="PNG")
    runner = EvaluationRunner(
        app,
        mode="offline",
        cache=EvaluationCache(tmp_path / "cache", fingerprint="test"),
        report_root=tmp_path / "reports",
    )

    async with runner:
        runner._case_attachment_root = tmp_path
        task = await runner._execute(
            make_case(
                input_type="text_and_image",
                file_refs=[{"path": "diagram.png"}],
            ),
            "trace-local-attachment",
        )

    assert task["status"] in {"completed", "failed", "cancelled"}
    task_attachment = task["input_content"]["attachments"][0]
    assert task_attachment["filename"] == "diagram.png"
    assert "path" not in task_attachment
    storage_key = str(task_attachment["storage_key"])
    if storage_key.startswith("local:"):
        assert not (
            settings.local_storage_path / storage_key.removeprefix("local:")
        ).exists()
    async with app.state.session_factory() as db:
        assert await FileRepository(db).get(str(task_attachment["file_id"])) is None


@pytest.mark.asyncio
async def test_runner_task_payload_uses_attachment_ref_not_case_path(
    tmp_path: Path,
) -> None:
    image = tmp_path / "diagram.png"
    image.write_bytes(b"local-image-bytes")
    runner = runner_without_lifespan(tmp_path)
    runner._case_attachment_root = tmp_path

    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self.payload

    class FakeClient:
        def __init__(self) -> None:
            self.task_payload: dict[str, Any] | None = None

        async def post(self, url: str, **kwargs: object) -> FakeResponse:
            if url == "/api/v1/files":
                return FakeResponse(
                    {
                        "id": "file_1",
                        "filename": "diagram.png",
                        "content_type": "image/png",
                        "size_bytes": 17,
                        "storage_key": "local:diagram.png",
                        "checksum_sha256": "checksum-1",
                        "ingestion_status": "ready",
                        "page_count": 0,
                        "extracted_text": "",
                        "extraction_metadata": {},
                    }
                )
            if url == "/api/v1/sessions":
                return FakeResponse({"id": "session_1"})
            if url == "/api/v1/tasks":
                self.task_payload = dict(kwargs["json"])  # type: ignore[arg-type]
                return FakeResponse({"status": "completed", "id": "task_1"})
            raise AssertionError(f"unexpected URL: {url}")

    fake_client = FakeClient()
    runner.client = fake_client  # type: ignore[assignment]
    task = await runner._execute(
        make_case(
            input_type="text_and_image",
            file_refs=[{"path": "diagram.png"}],
        ),
        "trace-1",
    )

    assert task["status"] == "completed"
    assert fake_client.task_payload is not None
    attachment = fake_client.task_payload["attachments"][0]
    assert attachment["file_id"] == "file_1"
    assert attachment["storage_key"] == "local:diagram.png"
    assert "path" not in attachment


@pytest.mark.asyncio
async def test_runner_does_not_cleanup_attachment_while_task_is_non_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = tmp_path / "diagram.png"
    image.write_bytes(b"local-image-bytes")
    runner = runner_without_lifespan(tmp_path)
    runner._case_attachment_root = tmp_path

    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self.payload

    class FakeClient:
        async def post(self, url: str, **kwargs: object) -> FakeResponse:
            if url == "/api/v1/files":
                return FakeResponse(
                    {
                        "id": "file_1",
                        "filename": "diagram.png",
                        "content_type": "image/png",
                        "size_bytes": 17,
                        "storage_key": "local:diagram.png",
                        "checksum_sha256": "checksum-1",
                        "ingestion_status": "ready",
                        "page_count": 0,
                        "extracted_text": "",
                        "extraction_metadata": {},
                    }
                )
            if url == "/api/v1/sessions":
                return FakeResponse({"id": "session_1"})
            if url == "/api/v1/tasks":
                return FakeResponse({"status": "queued", "id": "task_1"})
            raise AssertionError(f"unexpected URL: {url}")

        async def get(self, url: str, **kwargs: object) -> FakeResponse:
            assert url.startswith("/api/v1/tasks/task_1")
            return FakeResponse({"status": "queued", "id": "task_1"})

    cleanup_calls = 0

    async def record_cleanup(_attachments: list[dict[str, Any]]) -> None:
        nonlocal cleanup_calls
        cleanup_calls += 1

    monkeypatch.setattr(runner, "_cleanup_evaluation_attachments", record_cleanup)
    runner.client = FakeClient()  # type: ignore[assignment]
    operation = asyncio.create_task(
        runner._execute(
            make_case(
                input_type="text_and_image",
                file_refs=[{"path": "diagram.png"}],
            ),
            "trace-timeout-attachment",
        )
    )
    await asyncio.sleep(0.03)
    operation.cancel()
    with pytest.raises(asyncio.CancelledError):
        await operation
    assert cleanup_calls == 0


@pytest.mark.asyncio
async def test_runner_rejects_pdf_when_local_ingestion_requires_ocr(
    app: FastAPI,
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    output = BytesIO()
    writer.write(output)
    pdf.write_bytes(output.getvalue())
    runner = EvaluationRunner(
        app,
        mode="offline",
        cache=EvaluationCache(tmp_path / "cache", fingerprint="test"),
        report_root=tmp_path / "reports",
    )

    async with runner:
        runner._case_attachment_root = tmp_path
        with pytest.raises(ValueError, match="ingestion failed"):
            await runner._build_evaluation_attachments(
                make_case(file_refs=[{"path": "scan.pdf"}])
            )


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
