from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from app.contracts.research_analysis import (
    ResearchAnalysisRequest,
    ResearchDataManifest,
    ResearchEvidenceReference,
    ResearchVariable,
)
from app.services.research_analysis_planner import ResearchAnalysisPlannerService
from app.services.research_local_analysis import ResearchLocalAnalysisExecutor
from openpyxl import Workbook


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _request(
    path: Path,
    *,
    design: str,
    columns: list[ResearchVariable],
    row_count: int,
) -> ResearchAnalysisRequest:
    return ResearchAnalysisRequest(
        research_question="What does the declared local dataset support?",
        hypothesis=(
            "The prespecified outcome differs." if design != "time_series" else ""
        ),
        analysis_goal="predict" if design == "time_series" else "compare",
        design=design,
        unit_of_analysis="one row",
        variables=columns,
        data_manifest=ResearchDataManifest(
            dataset_id="local-demo",
            version="1",
            format="csv",
            checksum_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            row_count=row_count,
            column_count=len(columns),
            authorized=True,
            source_ref=str(path),
        ),
        data_dictionary="The declared columns and units are documented.",
        evidence=[
            ResearchEvidenceReference(
                evidence_id="method-001",
                role="method_reference",
                source_ref="https://example.test/method",
                cited=True,
            ),
            ResearchEvidenceReference(
                evidence_id="user-data-001",
                role="user_dataset",
                source_ref=str(path),
                cited=True,
            ),
        ],
        exploratory=design == "time_series",
    )


def test_executor_runs_two_group_mvp_and_writes_reproducible_artifacts(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "groups.csv"
    rows = [
        {"outcome": "10", "treatment": "control"},
        {"outcome": "12", "treatment": "control"},
        {"outcome": "14", "treatment": "control"},
        {"outcome": "16", "treatment": "treatment"},
        {"outcome": "18", "treatment": "treatment"},
        {"outcome": "20", "treatment": "treatment"},
    ]
    _write_csv(data_path, rows)
    request = _request(
        data_path,
        design="experimental_comparison",
        columns=[
            ResearchVariable(name="outcome", role="outcome", unit="score"),
            ResearchVariable(name="treatment", role="treatment"),
        ],
        row_count=len(rows),
    )
    plan_decision = ResearchAnalysisPlannerService().create_plan(request)
    assert plan_decision.plan is not None

    result = ResearchLocalAnalysisExecutor().execute(
        request,
        plan_decision.plan,
        output_dir=tmp_path / "analysis-pack",
    )

    assert result.status == "executed"
    assert "group_difference=6" in result.effect_estimates
    assert "本次分析纳入" in result.plain_language_summary
    assert "标准化差异" in result.plain_language_summary
    assert "excluded_rows=0" in result.diagnostics
    assert "no_p_value_is_reported" not in result.limitations
    assert result.evidence_ids == ["method-001"]
    assert result.evidence_references[0].source_ref == "https://example.test/method"
    assert result.review_checklist is not None
    assert not result.review_checklist.ready_for_signoff
    assert any(
        finding.startswith("exact_two_sided_permutation_p_value=")
        for finding in result.robustness_findings
    )
    assert len(result.artifacts) == 7
    for artifact in result.artifacts:
        artifact_path = tmp_path / "analysis-pack" / artifact.content_ref
        assert artifact_path.is_file()
        assert artifact.checksum_sha256
    report = json.loads(
        (tmp_path / "analysis-pack" / "analysis_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert str(data_path) not in json.dumps(report, ensure_ascii=False)
    provenance = json.loads(
        (tmp_path / "analysis-pack" / "analysis_provenance.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        provenance["dataset"]["checksum_sha256"]
        == request.data_manifest.checksum_sha256
    )
    assert provenance["dataset"]["source_ref_included"] is False
    assert [item["name"] for item in provenance["variables"]] == [
        "outcome",
        "treatment",
    ]
    bundle = json.loads(
        (tmp_path / "analysis-pack" / "analysis_bundle.json").read_text(
            encoding="utf-8"
        )
    )
    assert bundle["method_evidence_references"][0]["evidence_id"] == "method-001"


def test_executor_runs_observational_regression_mvp(tmp_path: Path) -> None:
    data_path = tmp_path / "regression.csv"
    rows = [
        {"outcome": str(2 * x + 1), "exposure": str(x)} for x in range(1, 7)
    ]
    _write_csv(data_path, rows)
    request = _request(
        data_path,
        design="observational_regression",
        columns=[
            ResearchVariable(name="outcome", role="outcome", unit="score"),
            ResearchVariable(name="exposure", role="exposure", unit="dose"),
        ],
        row_count=len(rows),
    )
    plan = ResearchAnalysisPlannerService().create_plan(request).plan
    assert plan is not None

    result = ResearchLocalAnalysisExecutor().execute(
        request, plan, output_dir=tmp_path / "analysis-pack"
    )

    assert result.status == "executed"
    assert "coefficient_exposure=2" in result.effect_estimates
    assert any("causal" in value for value in result.limitations)


def test_executor_runs_small_sample_mvp_with_exact_sensitivity(tmp_path: Path) -> None:
    data_path = tmp_path / "small-sample.csv"
    rows = [
        {"outcome": "5", "treatment": "control"},
        {"outcome": "6", "treatment": "control"},
        {"outcome": "8", "treatment": "treatment"},
        {"outcome": "9", "treatment": "treatment"},
    ]
    _write_csv(data_path, rows)
    request = _request(
        data_path,
        design="small_sample",
        columns=[
            ResearchVariable(name="outcome", role="outcome", unit="score"),
            ResearchVariable(name="treatment", role="treatment"),
        ],
        row_count=len(rows),
    )
    plan = ResearchAnalysisPlannerService().create_plan(request).plan
    assert plan is not None

    result = ResearchLocalAnalysisExecutor().execute(
        request, plan, output_dir=tmp_path / "analysis-pack"
    )

    assert result.status == "executed"
    assert "group_difference=3" in result.effect_estimates
    assert any(
        finding.startswith("exact_two_sided_permutation_p_value=")
        for finding in result.robustness_findings
    )


def test_executor_runs_time_series_baseline_mvp(tmp_path: Path) -> None:
    data_path = tmp_path / "series.csv"
    rows = [
        {"period": "2024-01-01", "outcome": "10"},
        {"period": "2024-02-01", "outcome": "12"},
        {"period": "2024-03-01", "outcome": "15"},
        {"period": "2024-04-01", "outcome": "14"},
    ]
    _write_csv(data_path, rows)
    request = _request(
        data_path,
        design="time_series",
        columns=[
            ResearchVariable(name="period", role="time", dtype="date"),
            ResearchVariable(name="outcome", role="outcome", unit="count"),
        ],
        row_count=len(rows),
    )
    plan = ResearchAnalysisPlannerService().create_plan(request).plan
    assert plan is not None

    result = ResearchLocalAnalysisExecutor().execute(
        request, plan, output_dir=tmp_path / "analysis-pack"
    )

    assert result.status == "executed"
    assert "one_step_mae=2" in result.effect_estimates
    assert "not an intervention effect" in result.interpretation


def test_executor_blocks_manifest_shape_mismatch_before_analysis(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "mismatch.csv"
    rows = [
        {"outcome": "1", "treatment": "control"},
        {"outcome": "2", "treatment": "treatment"},
    ]
    _write_csv(data_path, rows)
    request = _request(
        data_path,
        design="small_sample",
        columns=[
            ResearchVariable(name="outcome", role="outcome", unit="score"),
            ResearchVariable(name="treatment", role="treatment"),
        ],
        row_count=999,
    )
    plan = ResearchAnalysisPlannerService().create_plan(request).plan
    assert plan is not None

    result = ResearchLocalAnalysisExecutor().execute(
        request, plan, output_dir=tmp_path / "analysis-pack"
    )

    assert result.status == "quality_blocked"
    assert result.artifacts == []
    assert any(
        item.check_id == "manifest_shape_match" for item in result.data_quality.checks
    )


def test_executor_blocks_unplanned_missingness(tmp_path: Path) -> None:
    data_path = tmp_path / "missing.csv"
    rows = [
        {"outcome": "1", "treatment": "control"},
        {"outcome": "", "treatment": "control"},
        {"outcome": "3", "treatment": "treatment"},
        {"outcome": "4", "treatment": "treatment"},
    ]
    _write_csv(data_path, rows)
    request = _request(
        data_path,
        design="experimental_comparison",
        columns=[
            ResearchVariable(name="outcome", role="outcome", unit="score"),
            ResearchVariable(name="treatment", role="treatment"),
        ],
        row_count=len(rows),
    )
    plan = ResearchAnalysisPlannerService().create_plan(request).plan
    assert plan is not None

    result = ResearchLocalAnalysisExecutor().execute(
        request, plan, output_dir=tmp_path / "analysis-pack"
    )

    assert result.status == "quality_blocked"
    assert any(
        item.check_id == "missingness_strategy" and item.blocking
        for item in result.data_quality.checks
    )


def test_executor_rejects_tampered_frozen_plan(tmp_path: Path) -> None:
    data_path = tmp_path / "tampered.csv"
    rows = [
        {"outcome": "1", "treatment": "control"},
        {"outcome": "2", "treatment": "control"},
        {"outcome": "3", "treatment": "treatment"},
        {"outcome": "4", "treatment": "treatment"},
    ]
    _write_csv(data_path, rows)
    request = _request(
        data_path,
        design="experimental_comparison",
        columns=[
            ResearchVariable(name="outcome", role="outcome", unit="score"),
            ResearchVariable(name="treatment", role="treatment"),
        ],
        row_count=len(rows),
    )
    plan = ResearchAnalysisPlannerService().create_plan(request).plan
    assert plan is not None

    result = ResearchLocalAnalysisExecutor().execute(
        request,
        plan.model_copy(update={"plan_hash": "c" * 64}),
        output_dir=tmp_path / "analysis-pack",
    )

    assert result.status == "failed"
    assert result.limitations == ["plan_hash_or_request_design_mismatch"]


def test_executor_rejects_dataset_checksum_mismatch(tmp_path: Path) -> None:
    data_path = tmp_path / "checksum.csv"
    rows = [
        {"outcome": "1", "treatment": "control"},
        {"outcome": "2", "treatment": "control"},
        {"outcome": "3", "treatment": "treatment"},
        {"outcome": "4", "treatment": "treatment"},
    ]
    _write_csv(data_path, rows)
    base_request = _request(
        data_path,
        design="experimental_comparison",
        columns=[
            ResearchVariable(name="outcome", role="outcome", unit="score"),
            ResearchVariable(name="treatment", role="treatment"),
        ],
        row_count=len(rows),
    )
    assert base_request.data_manifest is not None
    request = base_request.model_copy(
        update={
            "data_manifest": base_request.data_manifest.model_copy(
                update={"checksum_sha256": "f" * 64}
            )
        }
    )
    plan = ResearchAnalysisPlannerService().create_plan(request).plan
    assert plan is not None

    result = ResearchLocalAnalysisExecutor().execute(
        request,
        plan,
        output_dir=tmp_path / "analysis-pack",
    )

    assert result.status == "failed"
    assert result.limitations == ["dataset_checksum_mismatch"]


def test_executor_reads_xlsx_and_writes_a_figure_artifact(tmp_path: Path) -> None:
    data_path = tmp_path / "groups.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["outcome", "treatment"])
    for row in ((10, "control"), (12, "control"), (16, "treatment"), (18, "treatment")):
        sheet.append(list(row))
    workbook.save(data_path)
    request = _request(
        data_path,
        design="experimental_comparison",
        columns=[
            ResearchVariable(name="outcome", role="outcome", unit="score"),
            ResearchVariable(name="treatment", role="treatment"),
        ],
        row_count=4,
    ).model_copy(
        update={
            "data_manifest": _request(
                data_path,
                design="experimental_comparison",
                columns=[
                    ResearchVariable(name="outcome", role="outcome", unit="score"),
                    ResearchVariable(name="treatment", role="treatment"),
                ],
                row_count=4,
            ).data_manifest.model_copy(update={"format": "xlsx"})
        }
    )
    plan = ResearchAnalysisPlannerService().create_plan(request).plan
    assert plan is not None

    result = ResearchLocalAnalysisExecutor().execute(
        request, plan, output_dir=tmp_path / "xlsx-pack"
    )

    assert result.status == "executed"
    figure = next(item for item in result.artifacts if item.artifact_type == "figure")
    assert (tmp_path / "xlsx-pack" / figure.content_ref).read_text().startswith("<svg")


def test_executor_reads_parquet_and_runs_multigroup_bootstrap_deterministically(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "groups.parquet"
    table = pa.Table.from_pylist(
        [
            {"outcome": 1, "treatment": "A"},
            {"outcome": 2, "treatment": "A"},
            {"outcome": 4, "treatment": "B"},
            {"outcome": 5, "treatment": "B"},
            {"outcome": 8, "treatment": "C"},
            {"outcome": 9, "treatment": "C"},
        ]
    )
    pq.write_table(table, data_path)
    request = ResearchAnalysisRequest(
        research_question="Do the three declared groups differ?",
        hypothesis="The declared group means differ.",
        analysis_goal="compare",
        design="multigroup_comparison",
        variables=[
            ResearchVariable(name="outcome", role="outcome", unit="score"),
            ResearchVariable(name="treatment", role="treatment"),
        ],
        data_manifest=ResearchDataManifest(
            dataset_id="parquet-groups",
            version="1",
            format="parquet",
            checksum_sha256=hashlib.sha256(data_path.read_bytes()).hexdigest(),
            row_count=6,
            column_count=2,
            authorized=True,
            source_ref=str(data_path),
        ),
        data_dictionary="outcome and treatment are documented",
        multiple_comparison_method="holm",
        resampling_method="bootstrap",
        bootstrap_replicates=100,
        random_seed=17,
        exploratory=False,
    )
    plan = ResearchAnalysisPlannerService().create_plan(request).plan
    assert plan is not None
    executor = ResearchLocalAnalysisExecutor()
    first = executor.execute(request, plan, output_dir=tmp_path / "multi-a")
    second = executor.execute(request, plan, output_dir=tmp_path / "multi-b")

    assert first.status == "executed"
    assert first.effect_estimates == second.effect_estimates
    assert any(
        item.startswith("holm_adjusted_p_")
        for item in first.robustness_findings
    )
    assert any(item.artifact_type == "figure" for item in first.artifacts)


def test_multigroup_output_matches_declared_unadjusted_comparison_method(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "groups.csv"
    _write_csv(
        data_path,
        [
            {"outcome": "1", "treatment": "A"},
            {"outcome": "2", "treatment": "A"},
            {"outcome": "4", "treatment": "B"},
            {"outcome": "5", "treatment": "B"},
            {"outcome": "8", "treatment": "C"},
            {"outcome": "9", "treatment": "C"},
        ],
    )
    request = ResearchAnalysisRequest(
        research_question="Do the three declared groups differ?",
        hypothesis="The declared group means differ.",
        analysis_goal="compare",
        design="multigroup_comparison",
        variables=[
            ResearchVariable(name="outcome", role="outcome", unit="score"),
            ResearchVariable(name="treatment", role="treatment"),
        ],
        data_manifest=ResearchDataManifest(
            dataset_id="csv-groups",
            version="1",
            format="csv",
            checksum_sha256=hashlib.sha256(data_path.read_bytes()).hexdigest(),
            row_count=6,
            column_count=2,
            authorized=True,
            source_ref=str(data_path),
        ),
        data_dictionary="outcome and treatment are documented",
        exploratory=False,
    )
    plan = ResearchAnalysisPlannerService().create_plan(request).plan
    assert plan is not None

    result = ResearchLocalAnalysisExecutor().execute(
        request, plan, output_dir=tmp_path / "unadjusted-pack"
    )

    assert result.status == "executed"
    assert any(
        item.startswith("unadjusted_pairwise_p_")
        for item in result.robustness_findings
    )
    assert not any(
        item.startswith("holm_adjusted_p_")
        for item in result.robustness_findings
    )
    assert "unadjusted_pairwise_results_require_review" in result.robustness_findings


def test_executor_runs_repeated_measures_with_subject_level_resampling(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "repeated.csv"
    _write_csv(
        data_path,
        [
            {"subject": "s1", "condition": "before", "outcome": "10"},
            {"subject": "s1", "condition": "after", "outcome": "12"},
            {"subject": "s2", "condition": "before", "outcome": "8"},
            {"subject": "s2", "condition": "after", "outcome": "11"},
            {"subject": "s3", "condition": "before", "outcome": "9"},
            {"subject": "s3", "condition": "after", "outcome": "10"},
        ],
    )
    request = ResearchAnalysisRequest(
        research_question="What is the within-subject change?",
        hypothesis="The after condition increases the outcome.",
        analysis_goal="compare",
        design="repeated_measures",
        variables=[
            ResearchVariable(name="subject", role="identifier"),
            ResearchVariable(name="condition", role="treatment"),
            ResearchVariable(name="outcome", role="outcome", unit="score"),
        ],
        data_manifest=ResearchDataManifest(
            dataset_id="repeated-demo",
            format="csv",
            checksum_sha256=hashlib.sha256(data_path.read_bytes()).hexdigest(),
            row_count=6,
            column_count=3,
            authorized=True,
            source_ref=str(data_path),
        ),
        data_dictionary="subject, condition and outcome are documented",
        resampling_method="bootstrap",
        bootstrap_replicates=100,
        random_seed=3,
        exploratory=False,
    )
    plan = ResearchAnalysisPlannerService().create_plan(request).plan
    assert plan is not None
    result = ResearchLocalAnalysisExecutor().execute(
        request, plan, output_dir=tmp_path / "repeated-pack"
    )

    assert result.status == "executed"
    assert "mean_within_subject_change=2" in result.effect_estimates
    assert any(
        "paired_bootstrap_95_percent_change_interval" in item
        for item in result.robustness_findings
    )
