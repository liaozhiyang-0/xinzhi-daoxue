from __future__ import annotations

import pytest
from app.contracts.research_analysis import (
    ResearchAnalysisRequest,
    ResearchDataManifest,
    ResearchEvidenceReference,
    ResearchVariable,
)
from app.services.research_analysis_planner import ResearchAnalysisPlannerService


def _request(design: str) -> ResearchAnalysisRequest:
    role_sets = {
        "experimental_comparison": [
            ResearchVariable(
                name="outcome", role="outcome", dtype="float", unit="score"
            ),
            ResearchVariable(name="treatment", role="treatment", dtype="category"),
        ],
        "observational_regression": [
            ResearchVariable(
                name="outcome", role="outcome", dtype="float", unit="score"
            ),
            ResearchVariable(
                name="exposure", role="exposure", dtype="float", unit="dose"
            ),
        ],
        "time_series": [
            ResearchVariable(name="period", role="time", dtype="date"),
            ResearchVariable(
                name="outcome", role="outcome", dtype="float", unit="count"
            ),
        ],
        "small_sample": [
            ResearchVariable(
                name="outcome", role="outcome", dtype="float", unit="score"
            ),
        ],
    }
    return ResearchAnalysisRequest(
        research_question="What does the declared study estimate?",
        hypothesis=(
            "The prespecified comparison differs." if design != "time_series" else ""
        ),
        analysis_goal="compare" if design != "time_series" else "predict",
        design=design,
        unit_of_analysis="one declared observation",
        variables=role_sets[design],
        data_manifest=ResearchDataManifest(
            dataset_id="dataset-demo",
            version="1",
            format="csv",
            checksum_sha256="a" * 64,
            row_count=100,
            column_count=len(role_sets[design]),
            authorized=True,
        ),
        data_dictionary="outcome and design variables are documented",
        evidence=[
            ResearchEvidenceReference(
                evidence_id="method-001",
                role="method_reference",
                title="A citable method reference",
                source_ref="https://example.test/method",
                cited=True,
            ),
            ResearchEvidenceReference(
                evidence_id="dataset-001",
                role="user_dataset",
                title="User dataset",
                source_ref="local://dataset-demo",
                cited=True,
            ),
        ],
        exploratory=design == "time_series",
    )


@pytest.mark.parametrize(
    "design",
    [
        "experimental_comparison",
        "observational_regression",
        "time_series",
        "small_sample",
    ],
)
def test_planner_freezes_a_design_specific_plan(design: str) -> None:
    decision = ResearchAnalysisPlannerService().create_plan(_request(design))

    assert decision.analysis_status == "ready_for_execution"
    assert decision.plan is not None
    assert decision.plan.design == design
    assert decision.plan.primary_method
    assert decision.plan.diagnostic_checks
    assert decision.plan.robustness_checks
    assert decision.plan.conclusion_boundaries
    assert len(decision.plan.plan_hash) == 64
    assert decision.method_evidence_ids == ["method-001"]


def test_planner_keeps_quality_blocked_request_without_a_plan() -> None:
    request = _request("experimental_comparison").model_copy(
        update={"variables": [ResearchVariable(name="outcome", role="outcome")]}
    )

    decision = ResearchAnalysisPlannerService().create_plan(request)

    assert decision.analysis_status == "quality_blocked"
    assert decision.plan is None


def test_plan_hash_is_stable_when_the_same_request_is_planned_twice() -> None:
    service = ResearchAnalysisPlannerService()

    first = service.create_plan(_request("small_sample"))
    second = service.create_plan(_request("small_sample"))

    assert first.plan is not None and second.plan is not None
    assert first.plan.plan_hash == second.plan.plan_hash
    assert first.plan.plan_id != second.plan.plan_id


def test_uncited_method_reference_does_not_enter_analysis_evidence() -> None:
    original = _request("experimental_comparison")
    request = original.model_copy(
        update={"evidence": [original.evidence[0].model_copy(update={"cited": False})]}
    )

    decision = ResearchAnalysisPlannerService().create_plan(request)

    assert decision.method_evidence_ids == []
