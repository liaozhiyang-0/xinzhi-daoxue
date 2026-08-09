from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from app.contracts.agent import new_id
from app.contracts.research_analysis import (
    AnalysisDesign,
    ResearchAnalysisPlan,
    ResearchAnalysisPlanningDecision,
    ResearchAnalysisRequest,
    ResearchQualityGateDecision,
)
from app.services.research_data_quality import ResearchDataQualityService


@dataclass(frozen=True)
class _MethodSpec:
    primary_method: str
    secondary_methods: tuple[str, ...]
    diagnostic_checks: tuple[str, ...]
    robustness_checks: tuple[str, ...]
    exclusion_rules: tuple[str, ...]
    conclusion_boundaries: tuple[str, ...]


METHOD_SPECS: dict[AnalysisDesign, _MethodSpec] = {
    "experimental_comparison": _MethodSpec(
        primary_method="two_group_effect_estimate",
        secondary_methods=(
            "randomization_or_permutation_inference",
            "standardized_effect_size",
        ),
        diagnostic_checks=(
            "group_counts_and_assignment_balance",
            "outcome_distribution_by_group",
            "variance_heterogeneity",
            "missingness_by_group",
            "outlier_and_influence_review",
        ),
        robustness_checks=(
            "exact_or_permutation_comparison",
            "alternative_effect_scale",
            "leave_one_out_sensitivity",
        ),
        exclusion_rules=(
            "deduplicate_the_unit_of_analysis",
            "exclude_rows_without_outcome_or_treatment_after_review",
        ),
        conclusion_boundaries=(
            "causal_language_requires_a_documented_assignment_mechanism",
            "the_effect_is_limited_to_the_observed_sampling_frame",
            "point_estimates_must_be_reported_with_uncertainty",
        ),
    ),
    "multigroup_comparison": _MethodSpec(
        primary_method=(
            "multi_group_effect_estimates_with_declared_multiple_comparison_control"
        ),
        secondary_methods=(
            "omnibus_between_group_variance_decomposition",
            "pairwise_permutation_inference_when_feasible",
            "standardized_pairwise_effect_sizes",
        ),
        diagnostic_checks=(
            "group_counts_and_assignment_balance",
            "outcome_distribution_by_group",
            "variance_heterogeneity",
            "missingness_by_group",
            "outlier_and_influence_review",
        ),
        robustness_checks=(
            "holm_adjusted_pairwise_comparisons_when_requested",
            "bootstrap_effect_intervals_when_requested",
            "leave_one_out_sensitivity",
        ),
        exclusion_rules=(
            "deduplicate_the_unit_of_analysis",
            "exclude_rows_without_outcome_or_group_after_review",
        ),
        conclusion_boundaries=(
            "pairwise_results_are_not_independent_without_adjustment",
            "causal_language_requires_a_documented_assignment_mechanism",
            "the_effect_is_limited_to_the_observed_sampling_frame",
        ),
    ),
    "repeated_measures": _MethodSpec(
        primary_method="within_unit_change_with_subject_level_resampling",
        secondary_methods=(
            "paired_change_distribution",
            "complete_subject_sensitivity",
        ),
        diagnostic_checks=(
            "subject_duplicate_and_pair_completeness",
            "period_order_and_condition_balance",
            "within_subject_outlier_review",
            "missingness_by_period",
        ),
        robustness_checks=(
            "paired_bootstrap_effect_interval_when_requested",
            "leave_one_subject_out_sensitivity",
            "complete_pair_vs_available_pair_sensitivity",
        ),
        exclusion_rules=(
            "retain_subject_pair_identity_until_pairing",
            "exclude_incomplete_pairs_only_with_an_explicit_log",
        ),
        conclusion_boundaries=(
            "within_subject_change_is_not_generalizable_without_sampling_support",
            "period_or_condition_order_effects_require_protocol_review",
            "causal_language_requires_a_documented_assignment_mechanism",
        ),
    ),
    "observational_regression": _MethodSpec(
        primary_method="prespecified_multivariable_regression_for_conditional_association",
        secondary_methods=(
            "nonlinear_or_interaction_sensitivity",
            "overlap_and_weighting_sensitivity_when_design_allows",
        ),
        diagnostic_checks=(
            "missingness_pattern_and_data_leakage",
            "functional_form_and_residual_pattern",
            "collinearity_review",
            "heteroskedasticity_review",
            "influential_observation_review",
            "exposure_covariate_overlap",
        ),
        robustness_checks=(
            "alternative_covariate_specification",
            "robust_standard_errors_or_resampling",
            "complete_case_vs_prespecified_missing_data_strategy",
        ),
        exclusion_rules=(
            "deduplicate_the_unit_of_analysis",
            "exclude_post_outcome_variables_from_predictors",
        ),
        conclusion_boundaries=(
            "observational_association_is_not_causal_without_identification_support",
            "coefficients_are_conditional_on_the_prespecified_covariates",
            "prediction_or_feature_importance_must_not_be_called_treatment_effect",
        ),
    ),
    "time_series": _MethodSpec(
        primary_method="time_ordered_baseline_with_rolling_origin_backtest",
        secondary_methods=(
            "seasonal_naive_baseline",
            "trend_or_autoregressive_comparison",
        ),
        diagnostic_checks=(
            "time_order_and_duplicate_period_review",
            "gaps_and_irregular_interval_review",
            "seasonality_and_trend_review",
            "residual_autocorrelation_review",
            "rolling_error_stability",
        ),
        robustness_checks=(
            "alternative_forecast_horizons",
            "rolling_window_sensitivity",
            "missing_period_sensitivity",
        ),
        exclusion_rules=(
            "sort_by_time_before_any_split",
            "prevent_future_rows_from_entering_training_features",
        ),
        conclusion_boundaries=(
            "forecast_quality_is_defined_for_the_declared_horizon_and_split",
            "time_series_association_does_not_establish_intervention_effect",
            "distribution_shift_after_the_observation_window_requires_review",
        ),
    ),
    "small_sample": _MethodSpec(
        primary_method="exact_or_permutation_comparison_with_effect_size",
        secondary_methods=(
            "finite_sample_resampling_when_justified",
            "individual_level_trajectory_review",
        ),
        diagnostic_checks=(
            "sample_count_per_group_or_condition",
            "within_subject_repetition_and_independence",
            "outlier_and_influence_review",
            "variance_heterogeneity",
            "finite_sample_assumption_review",
        ),
        robustness_checks=(
            "exact_vs_asymptotic_inference",
            "leave_one_out_sensitivity",
            "alternative_summary_measure",
        ),
        exclusion_rules=(
            "retain_all_observed_units_with_explicit_exclusion_log",
            "do_not_hide_outliers_without_protocol_justification",
        ),
        conclusion_boundaries=(
            "small_samples_produce_wide_and_design_sensitive_uncertainty",
            "a_non_significant_result_is_not_evidence_of_no_effect",
            "generalization_beyond_the_study_units_requires_new_evidence",
        ),
    ),
}


class ResearchAnalysisPlannerService:
    """Freeze an auditable plan without reading or transforming raw data."""

    def __init__(self, quality_service: ResearchDataQualityService | None = None):
        self.quality_service = quality_service or ResearchDataQualityService()

    def create_plan(
        self,
        request: ResearchAnalysisRequest,
        *,
        quality_gate: ResearchQualityGateDecision | None = None,
    ) -> ResearchAnalysisPlanningDecision:
        gate = quality_gate or self.quality_service.evaluate(request)
        if gate.analysis_status in {"quality_blocked", "insufficient_data"}:
            return ResearchAnalysisPlanningDecision(
                analysis_status=gate.analysis_status,
                quality_gate=gate,
                warnings=["analysis_plan_not_frozen_until_quality_gate_is_resolved"],
            )

        spec = METHOD_SPECS.get(request.design)
        if spec is None:
            return ResearchAnalysisPlanningDecision(
                analysis_status="quality_blocked",
                quality_gate=gate,
                warnings=["unsupported_or_unknown_research_design"],
            )

        plan = self._freeze_plan(request, spec)
        method_evidence_ids = [
            item.evidence_id
            for item in request.evidence
            if item.role == "method_reference"
            and item.source_ref.strip()
            and item.cited
        ]
        warnings = [
            "plan_is_methodological_scaffolding_until_raw_data_checks_are_run",
        ]
        if not method_evidence_ids:
            warnings.append("no_citable_method_reference_was_attached")
        if gate.analysis_status == "planning":
            warnings.append("quality_gate_requires_human_review_before_execution")
        return ResearchAnalysisPlanningDecision(
            analysis_status=gate.analysis_status,
            quality_gate=gate,
            plan=plan,
            method_evidence_ids=method_evidence_ids,
            warnings=warnings,
        )

    def validate_frozen_plan(
        self,
        request: ResearchAnalysisRequest,
        plan: ResearchAnalysisPlan,
    ) -> bool:
        spec = METHOD_SPECS.get(request.design)
        if spec is None or plan.design != request.design:
            return False
        expected = self._freeze_plan(request, spec)
        return expected.plan_hash == plan.plan_hash

    @staticmethod
    def _freeze_plan(
        request: ResearchAnalysisRequest,
        spec: _MethodSpec,
    ) -> ResearchAnalysisPlan:
        frozen_at = datetime.now(UTC)
        plan_data = {
            "version": "2.0.0",
            "research_question": request.research_question,
            "hypothesis": request.hypothesis,
            "design": request.design,
            "estimand": _effective_estimand(request),
            "primary_method": spec.primary_method,
            "secondary_methods": list(spec.secondary_methods),
            "exclusion_rules": list(spec.exclusion_rules),
            "missing_data_strategy": _missing_data_strategy(request),
            "diagnostic_checks": list(spec.diagnostic_checks),
            "robustness_checks": list(spec.robustness_checks),
            "resampling_method": request.resampling_method,
            "bootstrap_replicates": request.bootstrap_replicates,
            "random_seed": request.random_seed,
            "multiple_comparison_method": request.multiple_comparison_method,
            "conclusion_boundaries": list(spec.conclusion_boundaries),
            "exploratory": request.exploratory,
        }
        plan_hash = hashlib.sha256(
            json.dumps(
                plan_data,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return ResearchAnalysisPlan(
            plan_id=new_id("research_plan"),
            frozen_at=frozen_at,
            plan_hash=plan_hash,
            version="2.0.0",
            research_question=request.research_question,
            hypothesis=request.hypothesis,
            design=request.design,
            estimand=_effective_estimand(request),
            primary_method=spec.primary_method,
            secondary_methods=list(spec.secondary_methods),
            exclusion_rules=list(spec.exclusion_rules),
            missing_data_strategy=_missing_data_strategy(request),
            diagnostic_checks=list(spec.diagnostic_checks),
            robustness_checks=list(spec.robustness_checks),
            resampling_method=request.resampling_method,
            bootstrap_replicates=request.bootstrap_replicates,
            random_seed=request.random_seed,
            multiple_comparison_method=request.multiple_comparison_method,
            conclusion_boundaries=list(spec.conclusion_boundaries),
            exploratory=request.exploratory,
        )


def _effective_estimand(request: ResearchAnalysisRequest) -> str:
    if request.estimand.strip():
        return request.estimand.strip()
    defaults = {
        "experimental_comparison": "difference in outcome between declared groups",
        "multigroup_comparison": (
            "pairwise outcome differences among the declared groups"
        ),
        "repeated_measures": (
            "within-unit outcome change between the declared conditions"
        ),
        "observational_regression": (
            "conditional association between exposure and outcome"
        ),
        "time_series": "forecast error for the declared outcome and horizon",
        "small_sample": "study-level effect estimate with finite-sample uncertainty",
    }
    return defaults.get(request.design, "declared outcome summary")


def _missing_data_strategy(request: ResearchAnalysisRequest) -> str:
    for constraint in request.constraints:
        if "missing" in constraint.casefold() or "缺失" in constraint:
            return constraint.strip()
    return (
        "profile missingness before choosing complete-case, imputation, "
        "or model-based handling"
    )
