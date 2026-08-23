from __future__ import annotations

import json
from pathlib import Path

from app.agents.internal.contracts import VisionComponent, VisionExtraction
from app.contracts.solver import AcademicProblem
from app.services.academic_solver_service import AcademicProblemSolverService
from app.services.visual_acceptance import evaluate_visual_acceptance

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "team_feedback_31_scenarios.json"


def _fixture_case(scenario_id: str) -> dict[str, object]:
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return next(case for case in cases if case["scenario_id"] == scenario_id)


def test_feedback_visual_contract_accepts_captured_signal_markers() -> None:
    case = _fixture_case("G1-Q01")
    specification = case["visual_acceptance"]
    extraction = VisionExtraction(
        recognized_text=[
            "x(t) support [0,1]",
            "h(t) support [0,4]",
            "breakpoints 0, 1, 4, 5",
            "support interval and amplitude scale are visible",
        ],
        diagram_description="Two finite-support signals.",
        confidence=0.95,
    )

    decision = evaluate_visual_acceptance(extraction, specification)

    assert decision["status"] == "passed"
    assert decision["missing_must_capture"] == []
    assert decision["missing_refuse_if_missing"] == []


def test_feedback_visual_contract_blocks_missing_required_markers() -> None:
    case = _fixture_case("G1-Q01")
    specification = case["visual_acceptance"]
    extraction = VisionExtraction(
        recognized_text=["x(t) is shown"],
        diagram_description="A partially visible signal.",
        confidence=0.95,
    )

    decision = evaluate_visual_acceptance(extraction, specification)

    assert decision["status"] == "blocked"
    assert "x_support:[0,1]" in decision["missing_must_capture"]
    assert "support_interval" in decision["missing_refuse_if_missing"]


def test_real_provider_signal_prose_is_normalized_without_inference() -> None:
    extraction = VisionExtraction(
        recognized_text=["Q01"],
        diagram_description=(
            "The image displays two time-domain waveform plots. The left plot "
            "shows signal x(t), which is a rectangular pulse of amplitude 1 "
            "starting at t=0 and ending at t=1. The right plot shows signal "
            "h(t), which is a rectangular pulse of amplitude 0.5 starting at "
            "t=0 and ending at t=4."
        ),
        confidence=1.0,
    )

    decision = evaluate_visual_acceptance(
        extraction,
        {
            "must_capture": ["x_support:[0,1]", "h_support:[0,4]"],
            "refuse_if_missing": ["support_interval", "amplitude_or_scale"],
        },
    )

    assert decision["status"] == "passed"
    assert decision["missing_must_capture"] == []
    assert decision["missing_refuse_if_missing"] == []


def test_real_provider_spectrum_prose_is_normalized_without_topology_rules() -> None:
    extraction = VisionExtraction(
        recognized_text=["Q02", "F(jω)", "-π", "0", "π", "ω"],
        diagram_description=(
            "The horizontal axis is angular frequency ω and the vertical axis is "
            "the spectrum F(jω). The spectrum is nonzero on [-π, π], reaches "
            "peak 1 at ω=0, and falls to 0 at ω=±π."
        ),
        confidence=0.98,
    )

    decision = evaluate_visual_acceptance(
        extraction,
        {
            "must_capture": ["spectrum_support:[-π,π]"],
            "refuse_if_missing": ["frequency_axis", "spectrum_support"],
        },
    )

    assert decision["status"] == "passed"


def test_real_provider_bandpass_prose_is_normalized_without_inference() -> None:
    extraction = VisionExtraction(
        recognized_text=["Q03", "f (kHz)", "-10", "-8", "8", "10"],
        diagram_description=(
            "The frequency axis is f in kHz. The positive frequency band is "
            "[8,10] kHz and the negative frequency band is [-10,-8] kHz."
        ),
        confidence=0.98,
    )

    decision = evaluate_visual_acceptance(
        extraction,
        {
            "must_capture": [
                "positive_band:[8,10]kHz",
                "negative_band:[-10,-8]kHz",
                "frequency_units",
            ],
            "refuse_if_missing": ["band_edges", "frequency_units"],
        },
    )

    assert decision["status"] == "passed"


def test_solver_blocks_when_scenario_visual_contract_is_incomplete() -> None:
    case = _fixture_case("G1-Q04")
    problem = AcademicProblem(
        course="CT",
        problem_text=str(case["prompt"]),
        figures_given=[{"file_id": "image-1"}],
    )
    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        (
            '{"recognized_text":["16 V","8 V"],'
            '"diagram_description":"A source and load are connected.",'
            '"components":[{"component_type":"voltage source","label":"V1",'
            '"value":"16 V","connections":["N1","GND"],'
            '"terminal_map":{"positive":"N1","negative":"GND"},'
            '"polarity":"+ at N1","certainty":"certain"}],'
            '"confidence":0.95}'
        ),
        acceptance_spec=case["visual_acceptance"],
    )

    assert metadata["visual_acceptance"]["status"] == "blocked"
    assert metadata["visual_topology_validated"] is False
    assert merged.can_continue is False
    assert any(
        item["description"].startswith("visual_acceptance_missing:")
        for item in merged.uncertain_info
    )


def test_solver_does_not_apply_circuit_terminal_rules_to_signal_figures() -> None:
    case = _fixture_case("G1-Q01")
    problem = AcademicProblem(
        course="CT",
        problem_text=str(case["prompt"]),
        figures_given=[{"file_id": "image-1"}],
    )
    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        (
            '{"recognized_text":["x(t) support [0,1]",'
            '"h(t) support [0,4]", "breakpoints 0, 1, 4, 5",'
            '"support interval and amplitude scale are visible"],'
            '"diagram_description":"Two finite-support signals.",'
            '"confidence":0.95}'
        ),
        acceptance_spec=case["visual_acceptance"],
    )

    assert metadata["visual_topology_validated"] is True
    assert merged.can_continue is True
    assert "visual_topology_missing_components" not in metadata[
        "visual_topology_issues"
    ]


def test_solver_allows_noncritical_spectrum_annotation_uncertainty() -> None:
    problem = AcademicProblem(
        course="DSP",
        problem_text=(
            "已知 f(t) 的傅里叶变换是以 ω=0 为中心、支撑区间 [-π,π] "
            "的三角频谱，y(t)=f(t)sin(πt)。求 Y(jω)。"
        ),
        figures_given=[{"file_id": "image-1"}],
    )
    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        (
            '{"recognized_text":["F(jω)","-π","0","π","ω"],'
            '"diagram_description":"频谱图，横轴为角频率 ω，支撑区间 [-π,π]。",'
            '"uncertain_info":["坐标轴刻度不完整", "坐标轴箭头未完全画出"],'
            '"confidence":0.98}'
        ),
        acceptance_spec={
            "must_capture": ["spectrum_support:[-π,π]"],
            "refuse_if_missing": ["frequency_axis", "spectrum_support"],
        },
    )

    assert metadata["visual_acceptance"]["status"] == "passed"
    assert metadata["visual_topology_validated"] is True
    assert merged.can_continue is True
    assert "visual_topology_contains_uncertain_info" not in metadata[
        "visual_topology_issues"
    ]


def test_solver_preserves_top_level_real_vision_band_fields() -> None:
    problem = AcademicProblem(
        course="DSP",
        problem_text=(
            "实信号频谱正频带仅在 8–10 kHz、负频带仅在 -10–-8 kHz 非零。"
        ),
        figures_given=[{"file_id": "image-1"}],
    )
    _, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        (
            '{"positive_band":[8,10],"negative_band":[-10,-8],'
            '"frequency_units":"kHz","band_edges":[-10,-8,8,10],'
            '"frequency_axis":"f (kHz)","confidence":0.95}'
        ),
        acceptance_spec={
            "must_capture": [
                "positive_band:[8,10]kHz",
                "negative_band:[-10,-8]kHz",
                "frequency_units",
            ],
            "refuse_if_missing": ["band_edges", "frequency_units"],
        },
    )

    assert metadata["visual_acceptance"]["status"] == "passed"


def test_solver_can_continue_on_explicit_prompt_facts_without_passing_visual_gate(
) -> None:
    problem = AcademicProblem(
        course="DSP",
        problem_text=(
            "实信号频谱正频带仅在 8–10 kHz、负频带仅在 -10–-8 kHz 非零。"
        ),
        figures_given=[{"file_id": "image-1"}],
    )
    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        '{"diagram_description":"频谱图，频率轴为 f (kHz)。", "confidence":0.95}',
        acceptance_spec={
            "must_capture": [
                "positive_band:[8,10]kHz",
                "negative_band:[-10,-8]kHz",
                "frequency_units",
            ],
            "refuse_if_missing": ["band_edges", "frequency_units"],
        },
    )

    assert metadata["visual_acceptance"]["status"] == "blocked"
    assert metadata["visual_acceptance"]["prompt_facts_cover"] is True
    assert merged.can_continue is True


def test_visual_contract_can_capture_source_polarity_and_reference_fields() -> None:
    extraction = VisionExtraction(
        recognized_text=["independent voltage source 16 V"],
        diagram_description="Power reference direction is shown.",
        components=[
            VisionComponent(
                component_type="voltage source",
                label="V1",
                value="16 V",
                connections=["N1", "GND"],
                terminal_map={"positive": "N1", "negative": "GND"},
                polarity="+ at N1, - at GND",
                reference_direction="power absorbed direction",
            )
        ],
        confidence=0.95,
    )

    decision = evaluate_visual_acceptance(
        extraction,
        {
            "must_capture": [
                "independent_sources:16V/8V",
                "power_reference_direction",
            ],
            "refuse_if_missing": ["source_polarity_or_value"],
        },
    )

    assert decision["status"] == "blocked"
    assert "independent_sources:16V/8V" in decision["missing_must_capture"]
    assert decision["missing_refuse_if_missing"] == []
