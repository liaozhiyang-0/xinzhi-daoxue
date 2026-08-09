from app.contracts.research_analysis import (
    ResearchAnalysisRequest,
    ResearchDataManifest,
    ResearchVariable,
)
from app.services.research_data_quality import ResearchDataQualityService


def test_quality_gate_returns_insufficient_data_without_manifest() -> None:
    request = ResearchAnalysisRequest(
        research_question="两组实验是否有差异？",
        design="experimental_comparison",
        analysis_goal="compare",
    )

    decision = ResearchDataQualityService().evaluate(request)

    assert decision.analysis_status == "insufficient_data"
    assert decision.report.status == "blocked"
    assert "missing_dataset_manifest" in decision.reasons


def test_quality_gate_blocks_missing_design_roles() -> None:
    request = ResearchAnalysisRequest(
        research_question="温度是否影响寿命？",
        design="experimental_comparison",
        analysis_goal="estimate_effect",
        estimand="平均寿命差",
        data_manifest=ResearchDataManifest(
            dataset_id="exp-001",
            format="csv",
            checksum_sha256="abc123",
            row_count=100,
            column_count=4,
            authorized=True,
        ),
        variables=[ResearchVariable(name="寿命", role="outcome", unit="小时")],
        data_dictionary="寿命：器件失效前的小时数",
    )

    decision = ResearchDataQualityService().evaluate(request)

    assert decision.analysis_status == "quality_blocked"
    assert "missing_required_variable_roles" in decision.reasons


def test_quality_gate_requires_review_for_sensitive_data_and_missing_checksum() -> None:
    request = ResearchAnalysisRequest(
        research_question="预测实验结果",
        design="prediction",
        analysis_goal="predict",
        data_manifest=ResearchDataManifest(
            dataset_id="pred-001",
            format="parquet",
            row_count=200,
            column_count=8,
            authorized=True,
            contains_sensitive_data=True,
        ),
        variables=[
            ResearchVariable(name="结果", role="outcome", unit="分数"),
            ResearchVariable(name="特征", role="feature", unit="单位"),
        ],
        data_dictionary="结果和特征字段定义",
    )

    decision = ResearchDataQualityService().evaluate(request)

    assert decision.analysis_status == "planning"
    assert decision.report.status == "needs_review"
    assert "sensitive_data_requires_review" in decision.reasons
    assert "missing_dataset_checksum" in decision.reasons


def test_quality_gate_allows_ready_metadata_for_execution() -> None:
    request = ResearchAnalysisRequest(
        research_question="两组实验是否有差异？",
        hypothesis="处理组的平均结果高于对照组",
        analysis_goal="compare",
        design="experimental_comparison",
        exploratory=False,
        data_manifest=ResearchDataManifest(
            dataset_id="exp-002",
            format="csv",
            checksum_sha256="abc123",
            row_count=100,
            column_count=4,
            authorized=True,
        ),
        variables=[
            ResearchVariable(name="结果", role="outcome", unit="分数"),
            ResearchVariable(name="处理组", role="treatment", unit="0/1"),
        ],
        data_dictionary="结果和处理组字段定义",
    )

    decision = ResearchDataQualityService().evaluate(request)

    assert decision.analysis_status == "ready_for_execution"
    assert decision.report.status == "passed"
