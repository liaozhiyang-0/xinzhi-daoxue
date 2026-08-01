from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from app.capabilities import default_capability_registry
from app.contracts import AgentRequest, Intent, RunMetrics, StudentAttempt
from app.contracts.solver import (
    AcademicProblem,
    AcademicSolutionResult,
    FallbackReason,
    ProblemComplexity,
    SolutionPacketV1,
    SolverTaskMode,
)
from app.core.config import Settings
from app.courses import default_course_registry
from app.orchestrator.graphs import AcademicProblemSolverGraph
from app.services.academic_review import AcademicReviewService
from app.services.academic_solver_service import AcademicProblemSolverService
from app.services.ae_validator import AEValidator
from app.services.de_validator import DEValidator
from app.services.solver_boundary_policy import SolverBoundaryPolicy
from app.services.solver_runtime_policy import (
    FallbackTracker,
    RequestTimeBudget,
    SolverRuntimePolicy,
)
from app.services.student_verification import StudentVerificationService
from app.tools import default_tool_registry

REPO_ROOT = Path(__file__).resolve().parents[3]
PRIVATE_CASE_ROOT = REPO_ROOT / "真实测试题" / "统一格式"


def result(answer: str, *, course: str = "AE") -> AcademicSolutionResult:
    return AcademicSolutionResult(
        status="success",
        course=course,
        problem_summary="定向验证",
        final_answer=answer,
        confidence=0.8,
    )


def load_private_cases(relative_path: str) -> list[dict[str, Any]]:
    path = PRIVATE_CASE_ROOT / relative_path
    if not path.exists():
        pytest.skip(f"private targeted cases not available: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    assert isinstance(cases, list)
    return cases


def graph() -> AcademicProblemSolverGraph:
    return AcademicProblemSolverGraph(
        default_course_registry(),
        default_capability_registry(),
        default_tool_registry(),
    )


def test_solver_prompt_helpers_preserve_grounding_and_visual_structure() -> None:
    class Context:
        evidence = [object()]

        @staticmethod
        def to_retrieved_context() -> str:
            return "教材节点与方法证据"

    assert (
        AcademicProblemSolverService._retrieved_context(Context())
        == "教材节点与方法证据"
    )
    assert AcademicProblemSolverService._retrieved_context(None) == ""
    visual_instruction = AcademicProblemSolverService._visual_extraction_instruction()
    assert "器件端点与节点连接" in visual_instruction
    assert "关键坐标" in visual_instruction
    assert "全部子图" in visual_instruction


def test_request_time_budget_stops_optional_calls_before_hard_deadline() -> None:
    now = [0.0]
    budget = RequestTimeBudget(
        soft_deadline_seconds=140,
        finalization_deadline_seconds=165,
        hard_deadline_seconds=175,
        started_at=0,
        clock=lambda: now[0],
    )

    now[0] = 139
    assert budget.can_start_optional_call()
    assert budget.call_timeout_seconds(180) == 33

    now[0] = 141
    assert budget.soft_exhausted
    assert not budget.can_start_optional_call()
    assert budget.remaining_ms("hard") == 34_000

    now[0] = 166
    assert budget.finalization_required
    assert not budget.hard_exhausted
    assert budget.call_timeout_seconds(180) == 6


def test_runtime_policy_uses_rule_only_complexity_and_bounded_calls() -> None:
    simple = AcademicProblem(
        course="CT",
        problem_text="2Ω电阻两端电压为10V，求电流。",
        extraction_confidence=0.9,
    )
    complex_problem = simple.model_copy(
        update={"problem_text": "含多小问的综合题。" * 150}
    )
    visual_problem = simple.model_copy(
        update={
            "figures_given": [
                {
                    "figure_id": "figure-1",
                    "description": "待识别的电路图",
                }
            ]
        }
    )
    synthesis_problem = simple.model_copy(
        update={
            "problem_text": ("试用译码器和必要的逻辑门，设计一个两位二进制乘法器电路。")
        }
    )

    assert SolverRuntimePolicy.classify(simple) == ProblemComplexity.SIMPLE
    assert (
        SolverRuntimePolicy.model_call_budget(
            ProblemComplexity.SIMPLE,
            task_mode=SolverTaskMode.SOLVE,
        )
        == 1
    )
    assert SolverRuntimePolicy.classify(complex_problem) == ProblemComplexity.COMPLEX
    assert SolverRuntimePolicy.classify(visual_problem) == ProblemComplexity.COMPLEX
    assert SolverRuntimePolicy.classify(synthesis_problem) == ProblemComplexity.COMPLEX
    assert SolverRuntimePolicy.uses_extended_time_budget(ProblemComplexity.COMPLEX)
    assert not SolverRuntimePolicy.uses_extended_time_budget(ProblemComplexity.MEDIUM)
    assert (
        AcademicProblemSolverService._generation_task_type(ProblemComplexity.SIMPLE)
        == "academic_problem_solving_simple"
    )
    assert (
        AcademicProblemSolverService._generation_task_type(ProblemComplexity.MEDIUM)
        == "academic_problem_solving_simple"
    )
    assert (
        AcademicProblemSolverService._generation_task_type(ProblemComplexity.COMPLEX)
        == "academic_problem_solving"
    )
    assert (
        AcademicProblemSolverService._generation_task_type(
            ProblemComplexity.HIGH_RISK
        )
        == "academic_problem_solving"
    )


def test_academic_solver_uses_extended_budget_only_for_complex_cases() -> None:
    settings = Settings(app_env="test", _env_file=None)

    standard = AcademicProblemSolverService._request_time_budget(
        settings,
        ProblemComplexity.MEDIUM,
    )
    extended = AcademicProblemSolverService._request_time_budget(
        settings,
        ProblemComplexity.COMPLEX,
        upstream_elapsed_seconds=25,
    )

    assert (
        standard.soft_deadline_seconds,
        standard.finalization_deadline_seconds,
        standard.hard_deadline_seconds,
    ) == (140, 165, 175)
    assert (
        extended.soft_deadline_seconds,
        extended.finalization_deadline_seconds,
        extended.hard_deadline_seconds,
    ) == (200, 225, 235)
    assert 209_000 <= extended.remaining_ms("hard") <= 210_000


def test_fallback_count_is_limited_and_loop_is_rejected() -> None:
    tracker = FallbackTracker(max_fallbacks=1)
    tracker.start("ACADEMIC_PROBLEM_SOLVER")

    assert tracker.request(
        source_agent="ACADEMIC_PROBLEM_SOLVER",
        target_agent="SOLVER_CT_V1",
        reason=FallbackReason.HIGH_RISK_PROBLEM,
        stage="professional_fallback",
    )
    assert tracker.count == 1
    assert not tracker.request(
        source_agent="SOLVER_CT_V1",
        target_agent="ACADEMIC_PROBLEM_SOLVER",
        reason=FallbackReason.PRIMARY_MODEL_ERROR,
        stage="loop_attempt",
    )
    assert tracker.route_path == [
        "ACADEMIC_PROBLEM_SOLVER",
        "SOLVER_CT_V1",
    ]


@pytest.mark.parametrize(
    ("problem", "answer", "conflict_type"),
    [
        (
            AcademicProblem(
                course="AE",
                problem_type="dc_bias",
                problem_text="求BJT静态工作点。",
            ),
            "先画交流等效电路，再求中频增益。",
            "analysis_mode_mixed",
        ),
        (
            AcademicProblem(
                course="AE",
                problem_type="bjt_small_signal",
                problem_text="求共射电路中频小信号电压增益。",
            ),
            "电压增益 Av=25。",
            "gain_sign",
        ),
        (
            AcademicProblem(
                course="AE",
                problem_text="判断BJT是否处于放大区。",
                known_conditions=[{"name": "V_BE", "value": 0.2}],
            ),
            "该BJT处于放大区。",
            "bjt_operating_region",
        ),
        (
            AcademicProblem(
                course="AE",
                problem_text="判断MOS是否处于饱和区。",
                known_conditions=[
                    {"name": "V_GS", "value": 1},
                    {"name": "V_TH", "value": 2},
                ],
            ),
            "器件处于饱和区，I_D 按饱和区公式计算。",
            "mos_operating_region",
        ),
    ],
)
def test_ae_validator_reports_local_conflicts_without_regeneration(
    problem: AcademicProblem,
    answer: str,
    conflict_type: str,
) -> None:
    validation = AEValidator().validate(problem, result(answer))

    assert not validation.valid
    assert conflict_type in {item.conflict_type for item in validation.conflicts}
    assert validation.affected_steps == ["final_answer"]
    assert not validation.requires_regeneration


def test_de_truth_table_equivalence_is_deterministic() -> None:
    validator = DEValidator()

    equivalent = validator.truth_table_equivalent(
        "A*(B+C)",
        "A*B+A*C",
    )
    different = validator.truth_table_equivalent("A+B", "A*B")

    assert equivalent.equivalent
    assert equivalent.checked_rows == 8
    assert not different.equivalent
    assert different.counterexample is not None


def test_de_state_transition_simulation_updates_only_on_selected_edge() -> None:
    rows = DEValidator().simulate_state_transitions(
        initial_state="00",
        inputs=[0, 1, 0],
        transition_table={
            "00|0": "00",
            "00|1": {"next_state": "01", "output": "0"},
            "01|0": {"next_state": "10", "output": "1"},
        },
        edge="rising",
    )

    assert [item.current_state for item in rows] == ["00", "00", "01"]
    assert [item.next_state for item in rows] == ["00", "01", "10"]
    assert all(item.edge == "rising" for item in rows)


def test_review_mode_returns_first_material_error_and_preserves_prior_step() -> None:
    problem = AcademicProblem(
        course="CT",
        task_mode=SolverTaskMode.REVIEW,
        problem_text="电感电流从1A下降到0.2A，求变化率和电压。",
    )
    review = AcademicReviewService().review(
        problem,
        result(
            "释放能量为0.192 J；di/dt=-800 A/s，关联方向下电压为-320 V。",
            course="CT",
        ),
        {
            "steps": [
                {
                    "step_id": "energy",
                    "content": "释放能量为0.192 J。",
                },
                {
                    "step_id": "voltage-sign",
                    "content": "下降时变化率=800 A/s，电压为320 V。",
                },
            ]
        },
    )

    assert review.student_answer_status == "partially_correct"
    assert review.first_error_step == "voltage-sign"
    assert review.error_type == "sign"
    assert review.remaining_valid_steps == ["energy"]


@pytest.mark.parametrize(
    ("course", "message", "expected_reason"),
    [
        (
            "CT",
            "题8-14所示电路没有提供电路图，也没有R、L和连接信息。",
            "missing_figure",
        ),
        (
            "CT",
            "同一参考方向下证明元件既吸收20W又发出20W。",
            "contradictory_request",
        ),
        (
            "AE",
            "在上题所给电路参数条件下求输出；当前没有上题和参数。",
            "missing_prior_context",
        ),
        (
            "AE",
            "理想运放没有说明反馈，直接令v+=v-。",
            "op_amp_condition_missing",
        ),
        (
            "DE",
            "Verilog输入A=x、B=z，要求给出唯一二值输出0或1。",
            "unknown_logic_state",
        ),
        (
            "DE",
            "未附电路图的三位计数器，未说明初始状态和触发沿。",
            "missing_initial_condition",
        ),
    ],
)
def test_boundary_policy_intercepts_six_core_categories(
    course: str,
    message: str,
    expected_reason: str,
) -> None:
    decision = SolverBoundaryPolicy().evaluate(
        AcademicProblem(course=course, problem_text=message)
    )

    assert decision.intercepted
    assert decision.reason == expected_reason
    assert decision.missing_information or decision.uncertain_points


def test_legacy_contract_defaults_and_json_serialization_remain_stable() -> None:
    problem = AcademicProblem(problem_text="求解 $I=U/R$。")
    metrics = RunMetrics()
    packet = SolutionPacketV1(
        course_id="CT",
        mapping_status="mapped",
        final_answer={"latex": "$I=U/R$"},
    )

    payload = json.loads(problem.model_dump_json())
    metrics_payload = json.loads(metrics.model_dump_json())
    packet_json = packet.model_dump_json()

    assert payload["task_mode"] == "SOLVE"
    assert metrics_payload["deadline_remaining_ms"] == 0
    assert metrics_payload["fallback_count"] == 0
    assert json.loads(packet_json)["problem_summary"] == ""
    assert "$I=U/R$" in packet_json
    assert "```" not in packet_json


def test_selected_private_error_cases_locate_first_error_without_rewriting() -> None:
    selected_ids = {
        "CUR-ERR-CT-001",
        "CUR-ERR-AE-001",
        "CUR-ERR-AE-002",
        "CUR-ERR-DE-001",
        "CUR-ERR-DE-002",
        "CUR-ERR-COMM-001",
        "CUR-ERR-COMM-002",
        "CUR-ERR-DSP-001",
        "CUR-ERR-DSP-002",
        "CUR-ERR-SS-001",
        "CUR-ERR-SS-002",
    }
    cases = {
        item["case_id"]: item
        for item in load_private_cases("curated_answer_sets/part2_error_detection.json")
        if item["case_id"] in selected_ids
    }
    assert set(cases) == selected_ids

    for case_id in sorted(selected_ids):
        case = cases[case_id]
        review = AcademicReviewService().review(
            AcademicProblem(
                course=case["course"],
                task_mode=SolverTaskMode.REVIEW,
                problem_text=case["message"],
            ),
            result(case["reference_answer"], course=case["course"]),
            case["task_options"]["student_attempt"],
        )
        assert (
            review.first_error_step
            == case["evidence_requirements"]["expected_first_error_step"]
        ), case_id
        assert review.student_answer_status in {
            "incorrect",
            "partially_correct",
        }


def test_private_error_cases_flow_through_student_verification() -> None:
    cases = load_private_cases("curated_answer_sets/part2_error_detection.json")
    assert len(cases) == 12

    for case in cases:
        packet = SolutionPacketV1(
            course_id=case["course"],
            problem_type="general",
            problem_summary=case["message"],
            final_answer=case["reference_answer"],
            mapping_status="unavailable",
        )
        report, _ = StudentVerificationService().verify(
            StudentAttempt.model_validate(case["task_options"]["student_attempt"]),
            packet,
        )
        expected_step = case["evidence_requirements"]["expected_first_error_step"]
        assert report.overall_status == "verified_incorrect", case["case_id"]
        assert report.first_confirmed_error_step == expected_step, case["case_id"]
        assert report.step_results[0].error_type.value == case["expected_error_type"], (
            case["case_id"]
        )


def test_selected_private_boundary_cases_are_deterministically_intercepted() -> None:
    selected_ids = {
        "CUR-BND-CT-001",
        "CUR-BND-CT-002",
        "CUR-BND-AE-001",
        "CUR-BND-AE-002",
        "CUR-BND-DE-001",
        "CUR-BND-DE-002",
    }
    cases = {
        item["case_id"]: item
        for item in load_private_cases("curated_answer_sets/part3_boundary.json")
        if item["case_id"] in selected_ids
    }
    assert set(cases) == selected_ids

    for case_id in sorted(selected_ids):
        case = cases[case_id]
        decision = SolverBoundaryPolicy().evaluate(
            AcademicProblem(
                course=case["course"],
                problem_text=case["message"],
            )
        )
        assert decision.intercepted, case_id
        assert decision.answer_status in {"conditional", "unusable"}


def test_timeout_regression_selection_covers_five_courses() -> None:
    path = (
        PRIVATE_CASE_ROOT
        / "evaluation_reports"
        / "full_live_20260727T120134Z"
        / "raw"
        / "latest.json"
    )
    if not path.exists():
        pytest.skip(f"private full-run report not available: {path}")
    results = {
        item["case_id"]: item
        for item in json.loads(path.read_text(encoding="utf-8"))["results"]
    }
    selected_ids = {
        "CT-C01-Q01",
        "KB-CT-11-13",
        "AE-10-1-2",
        "DE-3-2-11",
        "SS-C03-Q05",
        "KB-DSP-3-16",
    }

    assert selected_ids <= results.keys()
    assert {results[case_id]["expected"]["course"] for case_id in selected_ids} == {
        "CT",
        "AE",
        "DE",
        "SS",
        "DSP",
    }
    assert all(results[case_id]["status"] == "timeout" for case_id in selected_ids)
    assert all(results[case_id]["elapsed_ms"] >= 180_000 for case_id in selected_ids)


@pytest.mark.asyncio
async def test_six_historical_timeout_cases_preserve_controlled_partial_result() -> (
    None
):
    class FakeRegistry:
        @staticmethod
        def get_route(_task_type: str) -> object:
            return type("Route", (), {"primary": "model"})()

        @staticmethod
        def get_model(_alias: str) -> object:
            return type("Definition", (), {"provider": "fake"})()

        @staticmethod
        def enabled(_definition: object) -> bool:
            return True

    class TimeoutModelService:
        registry = FakeRegistry()
        providers = {"fake": type("Provider", (), {"available": True})()}
        settings = Settings(app_env="test", _env_file=None)

        @staticmethod
        async def generate_for_task(
            _task_type: str,
            **_kwargs: object,
        ) -> object:
            raise TimeoutError

    selected_ids = {
        "CT-C01-Q01",
        "KB-CT-11-13",
        "AE-10-1-2",
        "DE-3-2-11",
        "SS-C03-Q05",
        "KB-DSP-3-16",
    }
    cases = {
        item["case_id"]: item
        for item in load_private_cases("balanced_336/all_cases.json")
        if item["case_id"] in selected_ids
    }
    assert set(cases) == selected_ids
    service = AcademicProblemSolverService(
        graph(),
        TimeoutModelService(),  # type: ignore[arg-type]
    )

    for case_id in sorted(selected_ids):
        case = cases[case_id]
        response = await service.run(
            AgentRequest(
                session_id="targeted-regression",
                user_id="local-test",
                course_id=case["course"],
                intent=Intent.SOLVE_PROBLEM,
                canonical_input={"text": case["message"]},
            )
        )
        execution = response.structured_result["model_execution"]
        assert response.answer.strip(), case_id
        assert response.metrics.partial_result_available, case_id
        assert execution["status"] == "failed", case_id
        assert execution["error_type"] == "primary_model_time_budget_exhausted", case_id
