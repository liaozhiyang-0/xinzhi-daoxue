from __future__ import annotations

# ruff: noqa: I001

import pytest
from pydantic import ValidationError

from app.contracts.research_analysis import (
    ResearchAnalysisPlan,
    ResearchAnalysisRequest,
    ResearchDataManifest,
    ResearchEvidenceReference,
)


def test_analysis_request_requires_authorized_dataset_for_execution_metadata() -> None:
    with pytest.raises(ValidationError, match="authorized"):
        ResearchAnalysisRequest(
            research_question="温度是否影响器件寿命？",
            analysis_goal="estimate_effect",
            estimand="平均寿命差",
            design="experimental_comparison",
            data_manifest=ResearchDataManifest(
                dataset_id="fixture-001", format="csv", authorized=False
            ),
        )


def test_confirmatory_request_requires_hypothesis() -> None:
    with pytest.raises(ValidationError, match="hypothesis"):
        ResearchAnalysisRequest(
            research_question="两组实验是否有差异？",
            analysis_goal="compare",
            design="experimental_comparison",
            exploratory=False,
        )


def test_bootstrap_contract_requires_replicates_when_enabled() -> None:
    with pytest.raises(ValidationError, match="bootstrap_replicates"):
        ResearchAnalysisRequest(
            research_question="重复测量是否有变化？",
            design="repeated_measures",
            resampling_method="bootstrap",
            bootstrap_replicates=0,
        )


def test_analysis_plan_requires_design_and_conclusion_boundary() -> None:
    with pytest.raises(ValidationError):
        ResearchAnalysisPlan(
            plan_id="plan-001",
            research_question="研究问题",
            primary_method="回归",
            missing_data_strategy="待定",
            diagnostic_checks=["残差检查"],
            conclusion_boundaries=[],
            design="unknown",
        )


def test_cited_method_reference_requires_safe_verifiable_source() -> None:
    with pytest.raises(ValidationError, match="verifiable reference"):
        ResearchEvidenceReference(
            evidence_id="method-path",
            role="method_reference",
            source_ref="C:/private/method.pdf",
            cited=True,
        )

    with pytest.raises(ValidationError, match="credentials"):
        ResearchEvidenceReference(
            evidence_id="method-credential",
            role="method_reference",
            source_ref="https://user:pass@example.test/method",
            cited=True,
        )
