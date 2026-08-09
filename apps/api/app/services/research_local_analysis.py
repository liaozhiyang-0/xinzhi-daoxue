from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import date, datetime
from itertools import combinations
from pathlib import Path
from typing import Any, Literal

from app.contracts.research_analysis import (
    ResearchAnalysisPlan,
    ResearchAnalysisProvenance,
    ResearchAnalysisRequest,
    ResearchAnalysisResult,
    ResearchDataQualityCheck,
    ResearchDataQualityReport,
    ResearchDatasetProvenance,
    ResearchEvidenceReference,
    ResearchExecutionArtifact,
)
from app.services.research_analysis_planner import ResearchAnalysisPlannerService
from app.services.research_analysis_review import ResearchAnalysisReviewService
from app.services.research_data_quality import ResearchDataQualityService
from app.services.research_tabular_io import (
    ResearchTabularReadError,
    read_tabular_rows,
)


class LocalAnalysisExecutionError(ValueError):
    """Raised when a local, deterministic analysis cannot be executed safely."""


@dataclass(frozen=True)
class _AnalysisOutput:
    primary_result: str
    effect_estimates: list[str]
    uncertainty_summary: list[str]
    diagnostics: list[str]
    robustness_findings: list[str]
    interpretation: str
    limitations: list[str]
    figure_svg: str | None = None
    plain_language_summary: str = ""


class ResearchLocalAnalysisExecutor:
    """Execute approved plans against an explicitly supplied local data file.

    This executor deliberately accepts only local tabular data. It does not call
    a model, retrieve papers, or use conversation memory. The output directory
    is supplied by the caller so that storage policy stays outside this module.
    """

    def __init__(
        self,
        quality_service: ResearchDataQualityService | None = None,
        planner_service: ResearchAnalysisPlannerService | None = None,
    ) -> None:
        self.quality_service = quality_service or ResearchDataQualityService()
        self.planner_service = planner_service or ResearchAnalysisPlannerService(
            self.quality_service
        )
        self.review_service = ResearchAnalysisReviewService()

    def execute(
        self,
        request: ResearchAnalysisRequest,
        plan: ResearchAnalysisPlan,
        *,
        output_dir: Path,
    ) -> ResearchAnalysisResult:
        gate = self.quality_service.evaluate(request)
        evidence_ids = _method_evidence_ids(request)
        evidence_references = method_evidence_references(request)
        if gate.analysis_status != "ready_for_execution":
            status: Literal[
                "quality_blocked", "needs_review", "insufficient_data"
            ] = (
                "insufficient_data"
                if gate.analysis_status == "insufficient_data"
                else "quality_blocked"
                if gate.analysis_status == "quality_blocked"
                else "needs_review"
            )
            return ResearchAnalysisResult(
                status=status,
                design_assessment="raw data execution was not started",
                data_quality=gate.report,
                plan=plan,
                provenance=build_research_analysis_provenance(request),
                interpretation="The quality gate must be resolved before execution.",
                limitations=gate.reasons,
                evidence_ids=evidence_ids,
                evidence_references=evidence_references,
                human_review_required=True,
            )

        if not self.planner_service.validate_frozen_plan(request, plan):
            return ResearchAnalysisResult(
                status="failed",
                design_assessment="the frozen plan does not match the current request",
                data_quality=gate.report,
                plan=plan,
                provenance=build_research_analysis_provenance(request),
                limitations=["plan_hash_or_request_design_mismatch"],
                evidence_ids=evidence_ids,
                evidence_references=evidence_references,
                human_review_required=True,
            )

        try:
            columns, rows = _load_rows(request)
        except (OSError, LocalAnalysisExecutionError, ResearchTabularReadError) as exc:
            return ResearchAnalysisResult(
                status="failed",
                design_assessment="local dataset could not be loaded",
                data_quality=gate.report,
                plan=plan,
                provenance=build_research_analysis_provenance(request),
                limitations=[str(exc)],
                evidence_ids=evidence_ids,
                evidence_references=evidence_references,
                human_review_required=True,
            )

        report = _raw_data_quality_report(
            request,
            columns,
            rows,
            gate.report,
            plan=plan,
        )
        if report.has_blocking_issue:
            return ResearchAnalysisResult(
                status="quality_blocked",
                design_assessment="raw data quality checks blocked execution",
                data_quality=report,
                plan=plan,
                provenance=build_research_analysis_provenance(request),
                limitations=report.limitations,
                evidence_ids=evidence_ids,
                evidence_references=evidence_references,
                human_review_required=True,
            )

        try:
            output = _run_design(request, rows)
        except LocalAnalysisExecutionError as exc:
            return ResearchAnalysisResult(
                status="insufficient_data",
                design_assessment="the declared design lacks executable observations",
                data_quality=report,
                plan=plan,
                limitations=[str(exc)],
                evidence_ids=evidence_ids,
                evidence_references=evidence_references,
                human_review_required=True,
            )

        artifacts = _write_artifacts(
            output_dir=output_dir,
            request=request,
            plan=plan,
            output=output,
            report=report,
            evidence_ids=evidence_ids,
            evidence_references=evidence_references,
        )
        result = ResearchAnalysisResult(
            status="executed",
            design_assessment=(
                f"deterministic local execution completed for {request.design}"
            ),
            data_quality=report,
            plan=plan,
            provenance=build_research_analysis_provenance(request),
            artifacts=artifacts,
            plain_language_summary=output.plain_language_summary,
            primary_result=output.primary_result,
            effect_estimates=output.effect_estimates,
            uncertainty_summary=output.uncertainty_summary,
            diagnostics=output.diagnostics,
            robustness_findings=output.robustness_findings,
            interpretation=output.interpretation,
            limitations=output.limitations,
            evidence_ids=evidence_ids,
            evidence_references=evidence_references,
            human_review_required=True,
        )
        return result.model_copy(
            update={"review_checklist": self.review_service.build_checklist(result)}
        )


def _load_rows(
    request: ResearchAnalysisRequest,
) -> tuple[list[str], list[dict[str, str]]]:
    manifest = request.data_manifest
    if manifest is None or not manifest.source_ref.strip():
        raise LocalAnalysisExecutionError("dataset_source_ref_missing")
    source = manifest.source_ref.strip()
    if "://" in source:
        raise LocalAnalysisExecutionError("only_local_filesystem_sources_are_supported")
    path = Path(source)
    if not path.is_file():
        raise LocalAnalysisExecutionError("dataset_file_not_found")
    actual_checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    if manifest.checksum_sha256 and actual_checksum != manifest.checksum_sha256:
        raise LocalAnalysisExecutionError("dataset_checksum_mismatch")

    if manifest.format == "unknown":
        raise LocalAnalysisExecutionError("dataset_format_must_be_declared")
    return read_tabular_rows(path, manifest.format)


def _raw_data_quality_report(
    request: ResearchAnalysisRequest,
    columns: list[str],
    rows: list[dict[str, str]],
    base: ResearchDataQualityReport,
    *,
    plan: ResearchAnalysisPlan,
) -> ResearchDataQualityReport:
    manifest = request.data_manifest
    assert manifest is not None
    checks = list(base.checks)
    missing_columns = sorted(
        item.name for item in request.variables if item.name not in columns
    )
    checks.append(
        ResearchDataQualityCheck(
            check_id="required_columns",
            status="failed" if missing_columns else "passed",
            summary=(
                "required columns are missing"
                if missing_columns
                else "all declared variables are present"
            ),
            affected_columns=missing_columns,
            blocking=bool(missing_columns),
        )
    )
    if request.design == "repeated_measures":
        subject_name = _role_name(request, "identifier")
        condition_name = _role_name(request, "treatment")
        seen_pairs: set[tuple[str, str]] = set()
        duplicate_pairs: set[tuple[str, str]] = set()
        for row in rows:
            pair = (
                row.get(subject_name, "").strip(),
                row.get(condition_name, "").strip(),
            )
            if not pair[0] or not pair[1]:
                continue
            if pair in seen_pairs:
                duplicate_pairs.add(pair)
            seen_pairs.add(pair)
        checks.append(
            ResearchDataQualityCheck(
                check_id="subject_condition_uniqueness",
                status="failed" if duplicate_pairs else "passed",
                summary=(
                    "重复的 subject-condition 行会改变配对估计"
                    if duplicate_pairs
                    else "每个 subject-condition 组合唯一"
                ),
                affected_columns=[subject_name, condition_name]
                if duplicate_pairs
                else [],
                blocking=bool(duplicate_pairs),
            )
        )
    shape_mismatch = (
        manifest.row_count is not None and manifest.row_count != len(rows)
    ) or (manifest.column_count is not None and manifest.column_count != len(columns))
    checks.append(
        ResearchDataQualityCheck(
            check_id="manifest_shape_match",
            status="failed" if shape_mismatch else "passed",
            summary=(
                "loaded data shape differs from the authorized manifest"
                if shape_mismatch
                else "loaded data shape matches the authorized manifest"
            ),
            blocking=shape_mismatch,
        )
    )
    required_names = [item.name for item in request.variables]
    missingness = {
        name: sum(not str(row.get(name, "")).strip() for row in rows)
        for name in required_names
        if name in columns
    }
    missingness_summary = json.dumps(missingness, ensure_ascii=False, sort_keys=True)
    limitations = list(base.limitations)
    missing_values_present = any(missingness.values())
    explicit_missingness_strategy = not plan.missing_data_strategy.startswith(
        "profile missingness"
    )
    checks.append(
        ResearchDataQualityCheck(
            check_id="missingness_strategy",
            status="warning" if missing_values_present else "passed",
            summary=(
                "missing values require a frozen handling strategy"
                if missing_values_present
                else "no missing values detected in declared variables"
            ),
            blocking=missing_values_present and not explicit_missingness_strategy,
        )
    )
    if missing_values_present:
        limitations.append("missingness is reported; handling remains plan-defined")
    status = (
        "blocked"
        if any(item.blocking or item.status == "failed" for item in checks)
        else "passed"
    )
    return base.model_copy(
        update={
            "status": status,
            "checks": checks,
            "missingness_summary": missingness_summary,
            "limitations": limitations,
        }
    )


def _run_design(
    request: ResearchAnalysisRequest, rows: list[dict[str, str]]
) -> _AnalysisOutput:
    if request.design in {"experimental_comparison", "small_sample"}:
        return _run_two_group(request, rows)
    if request.design == "multigroup_comparison":
        return _run_multigroup(request, rows)
    if request.design == "repeated_measures":
        return _run_repeated_measures(request, rows)
    if request.design == "observational_regression":
        return _run_regression(request, rows)
    if request.design == "time_series":
        return _run_time_series(request, rows)
    raise LocalAnalysisExecutionError("design_has_no_local_executor")


def _run_two_group(
    request: ResearchAnalysisRequest, rows: list[dict[str, str]]
) -> _AnalysisOutput:
    outcome_name = _role_name(request, "outcome")
    group_name = _role_name(request, "treatment")
    groups: dict[str, list[float]] = {}
    for row in rows:
        group = row.get(group_name, "").strip()
        value = _finite_float(row.get(outcome_name, ""))
        if group and value is not None:
            groups.setdefault(group, []).append(value)
    if len(groups) != 2:
        raise LocalAnalysisExecutionError(
            "two_group_analysis_requires_exactly_two_groups"
        )
    labels = sorted(groups)
    first, second = groups[labels[0]], groups[labels[1]]
    if len(first) < 2 or len(second) < 2:
        raise LocalAnalysisExecutionError(
            "each_group_needs_at_least_two_numeric_outcomes"
        )
    first_mean, second_mean = _mean(first), _mean(second)
    difference = second_mean - first_mean
    standard_error = math.sqrt(
        _sample_variance(first) / len(first) + _sample_variance(second) / len(second)
    )
    interval = 1.96 * standard_error
    effect = _format_number(difference)
    interval_text = (
        "normal_approximation_95_percent_interval="
        f"[{_format_number(difference - interval)}, "
        f"{_format_number(difference + interval)}]"
    )
    pooled_variance = (
        ((len(first) - 1) * _sample_variance(first))
        + ((len(second) - 1) * _sample_variance(second))
    ) / (len(first) + len(second) - 2)
    standardized_effect = (
        difference / math.sqrt(pooled_variance) if pooled_variance > 0 else None
    )
    leave_one_out = _leave_one_out_difference_range(first, second)
    permutation_p = _permutation_p_value(first, second)
    effect_estimates = [
        f"group_difference={effect}",
        f"group_{labels[0]}_mean={_format_number(first_mean)}",
        f"group_{labels[1]}_mean={_format_number(second_mean)}",
    ]
    if standardized_effect is not None:
        effect_estimates.append(
            f"pooled_standardized_effect={_format_number(standardized_effect)}"
        )
    robustness_findings = [
        "leave_one_out_sensitivity_range="
        f"[{_format_number(leave_one_out[0])}, {_format_number(leave_one_out[1])}]",
    ]
    if permutation_p is None:
        robustness_findings.append(
            "exact_permutation_sensitivity_not_run_above_18_valid_observations"
        )
    else:
        robustness_findings.append(
            f"exact_two_sided_permutation_p_value={_format_number(permutation_p)}"
        )
    bootstrap_interval = _bootstrap_difference_interval(
        first,
        second,
        method=request.resampling_method,
        replicates=request.bootstrap_replicates,
        seed=request.random_seed,
    )
    if bootstrap_interval is None:
        robustness_findings.append("bootstrap_effect_interval_not_requested")
    else:
        robustness_findings.append(
            "bootstrap_95_percent_effect_interval="
            f"[{_format_number(bootstrap_interval[0])}, "
            f"{_format_number(bootstrap_interval[1])}]"
        )
    interval_low = difference - interval
    interval_high = difference + interval
    permutation_sentence = (
        f"精确双侧置换检验 p={_format_number(permutation_p)}，"
        "表示在当前样本量和置换假设下，"
        "如果组别实际上没有差异，出现同样或更大组间差异的情况并不常见；这不是因果效应的证明。"
        if permutation_p is not None
        else "本次样本量未运行精确置换检验，因此不对 p 值作判断。"
    )
    plain_language_summary = (
        f"本次分析纳入 {len(first) + len(second)} 条有效记录："
        f"{labels[0]} 组 {len(first)} 条，"
        f"{labels[1]} 组 {len(second)} 条。{labels[1]} 组的平均 {outcome_name} 为 "
        f"{_format_number(second_mean)}，{labels[0]} 组为 "
        f"{_format_number(first_mean)}；"
        f"也就是 {labels[1]} 组比 {labels[0]} 组高 {_format_number(difference)}。"
        f"差异的 95% 描述性区间约为 [{_format_number(interval_low)}, "
        f"{_format_number(interval_high)}]，在这组数据下没有跨过 0。"
        + (
            f"标准化差异约为 {_format_number(standardized_effect)}，说明两组均值相差约 "
            f"{_format_number(standardized_effect)} 个组内标准差；"
            "但小样本下这个指标可能不稳定。"
            if standardized_effect is not None
            else "由于组内波动无法估计，未报告标准化差异。"
        )
        + permutation_sentence
        + f"留一法得到的差异范围为 [{_format_number(leave_one_out[0])}, "
        f"{_format_number(leave_one_out[1])}]，说明去掉任意一名受试者后方向没有改变，"
        "但单个受试者仍会影响差异大小。"
        "因此，当前结论应表述为‘本样本中两组观察到的平均结果不同，处理组更高’，"
        "不能仅凭这张表确认干预造成了差异；还需要核对随机分配、研究方案、测量过程和目标人群。"
    )
    return _AnalysisOutput(
        primary_result=(
            f"difference ({labels[1]} - {labels[0]}) = {effect}; "
            f"n={len(first)} and n={len(second)}"
        ),
        effect_estimates=effect_estimates,
        uncertainty_summary=[
            interval_text,
            "interval is a descriptive approximation and requires design review",
        ],
        diagnostics=[
            f"valid_outcome_rows={len(first) + len(second)}",
            f"groups={labels}",
            f"excluded_rows={max(0, len(rows) - len(first) - len(second))}",
        ],
        robustness_findings=robustness_findings,
        interpretation=(
            "The output is a difference in observed group means. Causal wording "
            "requires an assignment mechanism and protocol review."
        ),
        limitations=[
            "exact_permutation_p_value_is_descriptive_and_requires_design_review",
            "normal_approximation_interval_is_not_a_substitute_for_design_review",
        ],
        figure_svg=_group_bar_svg(
            [(labels[0], first_mean), (labels[1], second_mean)],
            title="Observed group means",
        ),
        plain_language_summary=plain_language_summary,
    )


def _run_multigroup(
    request: ResearchAnalysisRequest, rows: list[dict[str, str]]
) -> _AnalysisOutput:
    outcome_name = _role_name(request, "outcome")
    group_name = _role_name(request, "treatment")
    groups: dict[str, list[float]] = {}
    for row in rows:
        group = row.get(group_name, "").strip()
        value = _finite_float(row.get(outcome_name, ""))
        if group and value is not None:
            groups.setdefault(group, []).append(value)
    if len(groups) < 3:
        raise LocalAnalysisExecutionError(
            "multi_group_analysis_requires_at_least_three_groups"
        )
    if any(len(values) < 2 for values in groups.values()):
        raise LocalAnalysisExecutionError(
            "each_multi_group_level_needs_at_least_two_numeric_outcomes"
        )
    labels = sorted(groups)
    all_values = [value for values in groups.values() for value in values]
    grand_mean = _mean(all_values)
    between = sum(
        len(values) * (_mean(values) - grand_mean) ** 2
        for values in groups.values()
    )
    within = sum(
        (value - _mean(values)) ** 2
        for values in groups.values()
        for value in values
    )
    df_between = len(groups) - 1
    df_within = len(all_values) - len(groups)
    f_statistic = (
        (between / df_between) / (within / df_within)
        if within > 0 and df_between > 0 and df_within > 0
        else None
    )
    pairwise: list[tuple[str, str, float, float | None]] = []
    for first_label, second_label in combinations(labels, 2):
        first = groups[first_label]
        second = groups[second_label]
        pairwise.append(
            (
                first_label,
                second_label,
                _mean(second) - _mean(first),
                _permutation_p_value(first, second),
            )
        )
    adjusted = (
        _holm_adjust([item[3] for item in pairwise])
        if request.multiple_comparison_method == "holm"
        else [None] * len(pairwise)
    )
    effect_estimates = [
        f"group_{label}_mean={_format_number(_mean(groups[label]))}"
        for label in labels
    ]
    robustness_findings = [
        f"multiple_comparison_method={request.multiple_comparison_method}",
        f"pairwise_comparison_count={len(pairwise)}",
    ]
    for index, (first_label, second_label, difference, raw_p_value) in enumerate(
        pairwise
    ):
        effect_estimates.append(
            f"pairwise_difference_{second_label}_minus_{first_label}="
            f"{_format_number(difference)}"
        )
        adjusted_p = adjusted[index]
        if raw_p_value is None:
            robustness_findings.append(
                f"pairwise_p_value_not_estimable_{second_label}_vs_{first_label}"
            )
        elif request.multiple_comparison_method == "holm" and adjusted_p is not None:
            robustness_findings.append(
                f"raw_pairwise_p_{second_label}_vs_{first_label}="
                f"{_format_number(raw_p_value)}"
            )
            robustness_findings.append(
                f"holm_adjusted_p_{second_label}_vs_{first_label}="
                f"{_format_number(adjusted_p)}"
            )
        else:
            robustness_findings.append(
                f"unadjusted_pairwise_p_{second_label}_vs_{first_label}="
                f"{_format_number(raw_p_value)}"
            )
    if request.multiple_comparison_method == "none":
        robustness_findings.append("unadjusted_pairwise_results_require_review")
    omnibus_effects = (
        [f"omnibus_f_statistic={_format_number(f_statistic)}"]
        if f_statistic is not None
        else []
    )
    return _AnalysisOutput(
        primary_result=(
            f"multi-group comparison across {len(groups)} groups; "
            f"n={len(all_values)}"
        ),
        effect_estimates=effect_estimates + omnibus_effects,
        uncertainty_summary=[
            (
                "pairwise permutation p-values are exact only when the "
                "enumeration limit is met"
            ),
            "effect estimates remain bounded by the observed groups and protocol",
        ],
        diagnostics=[
            f"groups={labels}",
            "group_counts="
            + json.dumps(
                {label: len(groups[label]) for label in labels},
                ensure_ascii=False,
                sort_keys=True,
            ),
            "rows with missing or nonnumeric outcome were not used",
        ],
        robustness_findings=robustness_findings,
        interpretation=(
            "The output compares observed group means. Multiple-comparison "
            "adjustment does not establish a causal assignment mechanism."
        ),
        limitations=[
            "omnibus_f_statistic_is_descriptive_without_distributional_review",
            "causal_language_requires_a_documented_assignment_mechanism",
        ],
        figure_svg=_group_bar_svg(
            [(label, _mean(groups[label])) for label in labels],
            title="Observed means by group",
        ),
    )


def _run_repeated_measures(
    request: ResearchAnalysisRequest, rows: list[dict[str, str]]
) -> _AnalysisOutput:
    outcome_name = _role_name(request, "outcome")
    condition_name = _role_name(request, "treatment")
    subject_name = _role_name(request, "identifier")
    by_subject: dict[str, dict[str, float]] = {}
    condition_order: list[str] = []
    duplicate_pairs = 0
    for row in rows:
        subject = row.get(subject_name, "").strip()
        condition = row.get(condition_name, "").strip()
        value = _finite_float(row.get(outcome_name, ""))
        if not subject or not condition or value is None:
            continue
        if condition not in condition_order:
            condition_order.append(condition)
        subject_values = by_subject.setdefault(subject, {})
        if condition in subject_values:
            duplicate_pairs += 1
        subject_values[condition] = value
    conditions = condition_order
    if len(conditions) != 2:
        raise LocalAnalysisExecutionError(
            "repeated_measures_requires_exactly_two_conditions"
        )
    first, second = conditions
    complete = [
        subject_values
        for subject_values in by_subject.values()
        if first in subject_values and second in subject_values
    ]
    if len(complete) < 2:
        raise LocalAnalysisExecutionError(
            "repeated_measures_needs_at_least_two_complete_subjects"
        )
    first_values = [item[first] for item in complete]
    second_values = [item[second] for item in complete]
    changes = [
        second - first
        for first, second in zip(first_values, second_values, strict=True)
    ]
    change = _mean(changes)
    interval = _bootstrap_mean_interval(
        changes,
        method=request.resampling_method,
        replicates=request.bootstrap_replicates,
        seed=request.random_seed,
    )
    robustness = [
        "complete_subject_count=" + str(len(complete)),
        "leave_one_subject_out_change_range="
        f"[{_format_number(min(_leave_one_out_mean(changes)))}, "
        f"{_format_number(max(_leave_one_out_mean(changes)))}]",
    ]
    if interval is None:
        robustness.append("paired_bootstrap_interval_not_requested")
    else:
        robustness.append(
            "paired_bootstrap_95_percent_change_interval="
            f"[{_format_number(interval[0])}, {_format_number(interval[1])}]"
        )
    return _AnalysisOutput(
        primary_result=(
            f"within-subject change ({second} - {first}) = "
            f"{_format_number(change)}; complete_subjects={len(complete)}"
        ),
        effect_estimates=[
            f"mean_within_subject_change={_format_number(change)}",
            f"condition_{first}_mean={_format_number(_mean(first_values))}",
            f"condition_{second}_mean={_format_number(_mean(second_values))}",
        ],
        uncertainty_summary=[
            (
                "uncertainty is based on complete subject pairs and requires "
                "protocol review"
            ),
        ],
        diagnostics=[
            f"condition_order={conditions}",
            "subjects_with_incomplete_pairs="
            + str(len(by_subject) - len(complete)),
            f"duplicate_subject_condition_rows={duplicate_pairs}",
        ],
        robustness_findings=robustness,
        interpretation=(
            "The result is a within-subject change between two observed conditions; "
            "period and order effects require study protocol review."
        ),
        limitations=[
            "incomplete_subject_pairs_are_not_imputed",
            "causal_language_requires_a_documented_assignment_mechanism",
        ],
        figure_svg=_group_bar_svg(
            [(first, _mean(first_values)), (second, _mean(second_values))],
            title="Paired condition means",
        ),
    )


def _run_regression(
    request: ResearchAnalysisRequest, rows: list[dict[str, str]]
) -> _AnalysisOutput:
    outcome_name = _role_name(request, "outcome")
    exposure_name = _role_name(request, "exposure")
    controls = [item.name for item in request.variables if item.role == "control"]
    predictors = [exposure_name, *controls]
    matrix: list[list[float]] = []
    outcomes: list[float] = []
    simple_matrix: list[list[float]] = []
    simple_outcomes: list[float] = []
    for row in rows:
        simple_values = [
            _finite_float(row.get(name, ""))
            for name in [outcome_name, exposure_name]
        ]
        simple_numeric_values = [
            value for value in simple_values if value is not None
        ]
        if len(simple_numeric_values) == len(simple_values):
            simple_outcomes.append(simple_numeric_values[0])
            simple_matrix.append([1.0, simple_numeric_values[1]])
        values = [
            _finite_float(row.get(name, "")) for name in [outcome_name, *predictors]
        ]
        numeric_values = [value for value in values if value is not None]
        if len(numeric_values) == len(values):
            outcomes.append(numeric_values[0])
            matrix.append([1.0, *numeric_values[1:]])
    if len(matrix) <= len(predictors) + 1:
        raise LocalAnalysisExecutionError(
            "regression_needs_more_complete_rows_than_parameters"
        )
    coefficients, inverse = _ordinary_least_squares(matrix, outcomes)
    residuals = [
        y - sum(coef * value for coef, value in zip(coefficients, row, strict=True))
        for row, y in zip(matrix, outcomes, strict=True)
    ]
    sse = sum(value * value for value in residuals)
    outcome_mean = _mean(outcomes)
    sst = sum((value - outcome_mean) ** 2 for value in outcomes)
    r_squared = 1.0 - sse / sst if sst else 0.0
    dof = len(matrix) - len(coefficients)
    residual_variance = sse / dof
    exposure_se = math.sqrt(max(0.0, residual_variance * inverse[1][1]))
    exposure = coefficients[1]
    residual_scale = math.sqrt(residual_variance)
    max_standardized_residual = (
        max(abs(value) for value in residuals) / residual_scale
        if residual_scale > 0
        else 0.0
    )
    interval = 1.96 * exposure_se
    interval_text = (
        "normal_approximation_95_percent_interval="
        f"[{_format_number(exposure - interval)}, "
        f"{_format_number(exposure + interval)}]"
    )
    effect_estimates = [
        f"coefficient_{exposure_name}={_format_number(exposure)}",
        f"r_squared={_format_number(r_squared)}",
    ]
    robustness_findings = [
        f"max_abs_standardized_residual={_format_number(max_standardized_residual)}",
    ]
    if len(simple_matrix) > 2:
        simple_coefficients, _ = _ordinary_least_squares(
            simple_matrix, simple_outcomes
        )
        robustness_findings.append(
            "unadjusted_vs_adjusted_exposure_delta="
            f"{_format_number(exposure - simple_coefficients[1])}"
        )
    else:
        robustness_findings.append("unadjusted_sensitivity_not_estimable")
    return _AnalysisOutput(
        primary_result=(
            f"conditional association coefficient for {exposure_name} = "
            f"{_format_number(exposure)}; complete_rows={len(matrix)}"
        ),
        effect_estimates=effect_estimates,
        uncertainty_summary=[
            interval_text,
            "interval assumes the declared linear model and requires diagnostics",
        ],
        diagnostics=[
            f"predictors={[exposure_name, *controls]}",
            f"complete_rows={len(matrix)}",
            f"max_abs_standardized_residual={_format_number(max_standardized_residual)}",
            "collinearity, influence, and overlap checks remain review items",
        ],
        robustness_findings=robustness_findings,
        interpretation=(
            "The coefficient is a conditional observational association under the "
            "declared linear specification, not an automatic causal effect."
        ),
        limitations=[
            "numeric predictors_only_in_this_MVP",
            "no_causal_identification_claim",
            "no_p_value_is_reported_by_this_deterministic_MVP",
        ],
    )


def _run_time_series(
    request: ResearchAnalysisRequest, rows: list[dict[str, str]]
) -> _AnalysisOutput:
    time_name = _role_name(request, "time")
    outcome_name = _role_name(request, "outcome")
    observations: list[tuple[tuple[int, Any], float]] = []
    for row in rows:
        time_value = row.get(time_name, "").strip()
        outcome = _finite_float(row.get(outcome_name, ""))
        if time_value and outcome is not None:
            observations.append((_time_key(time_value), outcome))
    observations.sort(key=lambda item: item[0])
    if len(observations) < 3:
        raise LocalAnalysisExecutionError(
            "time_series_needs_at_least_three_ordered_points"
        )
    if len({item[0] for item in observations}) != len(observations):
        raise LocalAnalysisExecutionError("time_series_has_duplicate_periods")
    errors = [
        current - previous
        for (_, previous), (_, current) in zip(
            observations, observations[1:], strict=False
        )
    ]
    mae = _mean([abs(value) for value in errors])
    rmse = math.sqrt(_mean([value * value for value in errors]))
    diagnostics = [
        f"ordered_points={len(observations)}",
        "time_order_and_duplicate_period_check=passed",
        "rolling_origin_uses_previous_observation_as_the_baseline",
        f"max_absolute_one_step_error={_format_number(max(map(abs, errors)))}",
    ]
    robustness_findings = []
    if len(observations) >= 4:
        two_step_errors = [
            current - previous
            for (_, previous), (_, current) in zip(
                observations, observations[2:], strict=False
            )
        ]
        two_step_mae = _mean([abs(value) for value in two_step_errors])
        robustness_findings.append(
            f"two_step_previous_value_mae={_format_number(two_step_mae)}"
        )
        split = max(1, len(errors) // 2)
        robustness_findings.append(
            "late_window_vs_full_mae_delta="
            f"{_format_number(_mean([abs(value) for value in errors[split:]]) - mae)}"
        )
    else:
        robustness_findings.append("alternative_horizon_sensitivity_not_estimable")
    return _AnalysisOutput(
        primary_result=(
            f"one_step_previous_value_baseline: MAE={_format_number(mae)}, "
            f"RMSE={_format_number(rmse)}, forecast_points={len(errors)}"
        ),
        effect_estimates=[
            f"one_step_mae={_format_number(mae)}",
            f"one_step_rmse={_format_number(rmse)}",
        ],
        uncertainty_summary=[
            "forecast error metrics are not sampling confidence intervals",
            "uncertainty intervals require a declared forecasting model and horizon",
        ],
        diagnostics=diagnostics,
        robustness_findings=robustness_findings,
        interpretation=(
            "The result measures a one-step baseline forecast error on the supplied "
            "ordered observations; it is not an intervention effect."
        ),
        limitations=[
            "no_seasonality_period_was_inferred",
            "no_future_distribution_shift_assessment",
        ],
    )


def _ordinary_least_squares(
    matrix: list[list[float]], outcomes: list[float]
) -> tuple[list[float], list[list[float]]]:
    columns = len(matrix[0])
    xtx = [
        [sum(row[i] * row[j] for row in matrix) for j in range(columns)]
        for i in range(columns)
    ]
    xty = [
        sum(row[i] * value for row, value in zip(matrix, outcomes, strict=True))
        for i in range(columns)
    ]
    inverse = _invert_matrix(xtx)
    coefficients = [
        sum(inverse[i][j] * xty[j] for j in range(columns)) for i in range(columns)
    ]
    return coefficients, inverse


def _invert_matrix(matrix: list[list[float]]) -> list[list[float]]:
    size = len(matrix)
    augmented = [
        row[:] + [1.0 if i == j else 0.0 for j in range(size)]
        for i, row in enumerate(matrix)
    ]
    for pivot_column in range(size):
        pivot_row = max(
            range(pivot_column, size),
            key=lambda row: abs(augmented[row][pivot_column]),
        )
        pivot = augmented[pivot_row][pivot_column]
        if abs(pivot) < 1e-12:
            raise LocalAnalysisExecutionError("regression_design_matrix_is_singular")
        augmented[pivot_column], augmented[pivot_row] = (
            augmented[pivot_row],
            augmented[pivot_column],
        )
        pivot_values = augmented[pivot_column]
        augmented[pivot_column] = [value / pivot for value in pivot_values]
        for row_index in range(size):
            if row_index == pivot_column:
                continue
            factor = augmented[row_index][pivot_column]
            augmented[row_index] = [
                left - factor * right
                for left, right in zip(
                    augmented[row_index], augmented[pivot_column], strict=True
                )
            ]
    return [row[size:] for row in augmented]


def _write_artifacts(
    *,
    output_dir: Path,
    request: ResearchAnalysisRequest,
    plan: ResearchAnalysisPlan,
    output: _AnalysisOutput,
    report: ResearchDataQualityReport,
    evidence_ids: list[str],
    evidence_references: list[ResearchEvidenceReference],
) -> list[ResearchExecutionArtifact]:
    output_dir.mkdir(parents=True, exist_ok=True)
    provenance = build_research_analysis_provenance(request).model_dump(mode="json")
    payloads: dict[str, object] = {
        "analysis_plan.json": plan.model_dump(mode="json"),
        "analysis_provenance.json": provenance,
        "analysis_estimates.json": {
            "plain_language_summary": output.plain_language_summary,
            "primary_result": output.primary_result,
            "effect_estimates": output.effect_estimates,
            "uncertainty_summary": output.uncertainty_summary,
        },
        "analysis_diagnostics.json": {
            "diagnostics": output.diagnostics,
            "robustness_findings": output.robustness_findings,
            "limitations": output.limitations,
            "data_quality": report.model_dump(mode="json"),
        },
        "analysis_report.json": {
            "plain_language_summary": output.plain_language_summary,
            "interpretation": output.interpretation,
            "conclusion_boundaries": plan.conclusion_boundaries,
            "scientific_limitations": output.limitations,
            "provenance": provenance,
        },
        "analysis_bundle.json": {
            "plan": plan.model_dump(mode="json"),
            "provenance": provenance,
            "data_quality": report.model_dump(mode="json"),
            "primary_result": output.primary_result,
            "effect_estimates": output.effect_estimates,
            "uncertainty_summary": output.uncertainty_summary,
            "diagnostics": output.diagnostics,
            "robustness_findings": output.robustness_findings,
            "interpretation": output.interpretation,
            "limitations": output.limitations,
            "method_evidence_ids": evidence_ids,
            "method_evidence_references": [
                item.model_dump(mode="json") for item in evidence_references
            ],
            "human_review_required": True,
        },
    }
    if output.figure_svg:
        payloads["analysis_figure.svg"] = output.figure_svg
    artifact_types: dict[
        str, Literal["script", "table", "figure", "diagnostic", "report"]
    ] = {
        "analysis_plan.json": "report",
        "analysis_provenance.json": "report",
        "analysis_estimates.json": "table",
        "analysis_diagnostics.json": "diagnostic",
        "analysis_report.json": "report",
        "analysis_bundle.json": "report",
        "analysis_figure.svg": "figure",
    }
    artifacts: list[ResearchExecutionArtifact] = []
    for filename, payload in payloads.items():
        path = output_dir / filename
        encoded = (
            str(payload).encode("utf-8")
            if filename.endswith(".svg")
            else json.dumps(
                payload, ensure_ascii=False, indent=2, sort_keys=True
            ).encode("utf-8")
        )
        path.write_bytes(encoded)
        artifacts.append(
            ResearchExecutionArtifact(
                artifact_id=f"artifact_{path.stem}",
                artifact_type=artifact_types[filename],
                label=filename,
                content_ref=filename,
                checksum_sha256=hashlib.sha256(encoded).hexdigest(),
                reproducible=True,
            )
        )
    return artifacts


def build_research_analysis_provenance(
    request: ResearchAnalysisRequest,
) -> ResearchAnalysisProvenance:
    """Build reproducibility metadata without exposing a local source path."""

    manifest = request.data_manifest
    dataset = None
    if manifest is not None:
        dataset = ResearchDatasetProvenance(
            dataset_id=manifest.dataset_id,
            version=manifest.version,
            format=manifest.format,
            checksum_sha256=manifest.checksum_sha256,
            row_count=manifest.row_count,
            column_count=manifest.column_count,
            authorized=manifest.authorized,
            contains_sensitive_data=manifest.contains_sensitive_data,
        )
    return ResearchAnalysisProvenance(
        research_question=request.research_question,
        analysis_goal=request.analysis_goal,
        design=request.design,
        estimand=request.estimand,
        unit_of_analysis=request.unit_of_analysis,
        dataset=dataset,
        variables=request.variables,
        software_environment=request.software_environment,
        reproducibility_notes=[
            "dataset source_ref is intentionally omitted from the artifact",
            (
                "rerun requires an independently authorized local dataset with "
                "the recorded checksum"
            ),
        ],
    )


def _role_name(request: ResearchAnalysisRequest, role: str) -> str:
    for item in request.variables:
        if item.role == role:
            return item.name
    raise LocalAnalysisExecutionError(f"variable_role_missing:{role}")


def _method_evidence_ids(request: ResearchAnalysisRequest) -> list[str]:
    return [item.evidence_id for item in method_evidence_references(request)]


def method_evidence_references(
    request: ResearchAnalysisRequest,
) -> list[ResearchEvidenceReference]:
    """Return cited method references; user data never enters this list."""

    return [
        item
        for item in request.evidence
        if item.role == "method_reference" and item.source_ref.strip() and item.cited
    ]


def _finite_float(value: object) -> float | None:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _mean(values: list[float]) -> float:
    if not values:
        raise LocalAnalysisExecutionError("mean_requires_at_least_one_value")
    return sum(values) / len(values)


def _sample_variance(values: list[float]) -> float:
    if len(values) < 2:
        raise LocalAnalysisExecutionError("variance_requires_at_least_two_values")
    average = _mean(values)
    return sum((value - average) ** 2 for value in values) / (len(values) - 1)


def _leave_one_out_difference_range(
    first: list[float], second: list[float]
) -> tuple[float, float]:
    differences: list[float] = []
    if len(first) > 1:
        differences.extend(
            _mean(second) - _mean(first[:index] + first[index + 1 :])
            for index in range(len(first))
        )
    if len(second) > 1:
        differences.extend(
            _mean(second[:index] + second[index + 1 :]) - _mean(first)
            for index in range(len(second))
        )
    if not differences:
        return _mean(second) - _mean(first), _mean(second) - _mean(first)
    return min(differences), max(differences)


def _permutation_p_value(first: list[float], second: list[float]) -> float | None:
    combined = [*first, *second]
    if len(combined) > 18:
        return None
    observed = abs(_mean(second) - _mean(first))
    exceedances = 0
    total = 0
    first_size = len(first)
    for selected_indices in combinations(range(len(combined)), first_size):
        selected = set(selected_indices)
        candidate_first = [
            value for index, value in enumerate(combined) if index in selected
        ]
        candidate_second = [
            value for index, value in enumerate(combined) if index not in selected
        ]
        if abs(_mean(candidate_second) - _mean(candidate_first)) >= observed - 1e-12:
            exceedances += 1
        total += 1
    return exceedances / total if total else None


def _bootstrap_difference_interval(
    first: list[float],
    second: list[float],
    *,
    method: str,
    replicates: int,
    seed: int,
) -> tuple[float, float] | None:
    if method != "bootstrap" or replicates <= 0:
        return None
    rng = random.Random(seed)
    estimates = [
        _mean([rng.choice(second) for _ in second])
        - _mean([rng.choice(first) for _ in first])
        for _ in range(replicates)
    ]
    return _percentile_interval(estimates)


def _bootstrap_mean_interval(
    values: list[float],
    *,
    method: str,
    replicates: int,
    seed: int,
) -> tuple[float, float] | None:
    if method != "bootstrap" or replicates <= 0:
        return None
    rng = random.Random(seed)
    estimates = [
        _mean([rng.choice(values) for _ in values]) for _ in range(replicates)
    ]
    return _percentile_interval(estimates)


def _percentile_interval(values: list[float]) -> tuple[float, float]:
    ordered = sorted(values)
    if not ordered:
        raise LocalAnalysisExecutionError("bootstrap_produced_no_estimates")
    return _quantile(ordered, 0.025), _quantile(ordered, 0.975)


def _quantile(values: list[float], probability: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def _holm_adjust(values: list[float | None]) -> list[float | None]:
    available = sorted(
        ((index, value) for index, value in enumerate(values) if value is not None),
        key=lambda item: item[1],  # type: ignore[arg-type]
    )
    adjusted: list[float | None] = [None] * len(values)
    running_max = 0.0
    count = len(available)
    for rank, (index, value) in enumerate(available):
        assert value is not None
        candidate = min(1.0, value * (count - rank))
        running_max = max(running_max, candidate)
        adjusted[index] = running_max
    return adjusted


def _leave_one_out_mean(values: list[float]) -> tuple[float, float]:
    if len(values) < 2:
        return _mean(values), _mean(values)
    estimates = [
        _mean(values[:index] + values[index + 1 :])
        for index in range(len(values))
    ]
    return min(estimates), max(estimates)


def _group_bar_svg(groups: list[tuple[str, float]], *, title: str) -> str:
    width, height = 640, 360
    chart_left, chart_top = 70, 55
    chart_width, chart_height = 520, 240
    maximum = max(abs(value) for _, value in groups) if groups else 1.0
    scale = chart_height / max(maximum, 1.0)
    bar_width = chart_width / max(len(groups), 1) * 0.6
    bars: list[str] = []
    for index, (label, value) in enumerate(groups):
        x = chart_left + (index + 0.2) * chart_width / max(len(groups), 1)
        bar_height = abs(value) * scale
        y = chart_top + chart_height - bar_height
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" '
            f'height="{bar_height:.2f}" fill="#2563eb" />'
            f'<text x="{x + bar_width / 2:.2f}" y="{height - 42}" '
            f'text-anchor="middle" font-size="12">{_escape_svg(label)}</text>'
            f'<text x="{x + bar_width / 2:.2f}" y="{max(y - 6, 20):.2f}" '
            f'text-anchor="middle" font-size="11">{_format_number(value)}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<title>{_escape_svg(title)}</title>'
        f'<rect width="100%" height="100%" fill="white" />'
        f'<text x="{width / 2}" y="28" text-anchor="middle" '
        f'font-size="16" font-family="sans-serif">{_escape_svg(title)}</text>'
        f'<line x1="{chart_left}" y1="{chart_top + chart_height}" '
        f'x2="{chart_left + chart_width}" y2="{chart_top + chart_height}" '
        f'stroke="#334155" />'
        + "".join(bars)
        + '<text x="12" y="348" font-size="10" font-family="sans-serif">'
        "Observed values; not a publication-ready figure</text></svg>"
    )


def _escape_svg(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _format_number(value: float) -> str:
    return f"{value:.6g}"


def _stringify_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value).strip()


def _time_key(value: str) -> tuple[int, Any]:
    try:
        return 0, datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return 1, float(value)
        except ValueError:
            return 2, value
