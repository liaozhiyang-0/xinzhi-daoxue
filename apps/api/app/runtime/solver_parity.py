"""Offline Legacy/Runtime parity evaluation for the academic solver.

The evaluator consumes paired serialized outputs and Runtime checkpoints. It
never invokes a Provider, solver graph, tool, or model. Its canary decision is
limited to structural and operational regressions; it does not prove answer
semantic equivalence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.runtime.replay import (
    RuntimeLegacyDiffReport,
    RuntimeTraceAudit,
    audit_checkpoint_trace,
    build_runtime_legacy_diff,
)


class SolverParityThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_pairs: int = Field(default=1, ge=1)
    max_status_mismatch_rate: float = Field(default=0, ge=0, le=1)
    max_answer_presence_mismatch_rate: float = Field(default=0, ge=0, le=1)
    max_trace_invalid_rate: float = Field(default=0, ge=0, le=1)
    max_handler_mismatch_rate: float = Field(default=0, ge=0, le=1)
    max_latency_regression_ratio: float = Field(default=0.5, ge=0)
    max_model_call_regression_ratio: float = Field(default=0.5, ge=0)
    max_single_pair_latency_regression_ratio: float = Field(default=0.5, ge=0)
    max_single_pair_model_call_regression_ratio: float = Field(default=0.5, ge=0)


class SolverParityPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=160)
    legacy_payload: dict[str, Any]
    runtime_payload: dict[str, Any]
    runtime_checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    required_handler_ids: set[str] = Field(default_factory=set)


class SolverParitySuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_version: str = "1"
    suite_id: str = Field(min_length=1, max_length=160)
    thresholds: SolverParityThresholds = Field(default_factory=SolverParityThresholds)
    pairs: list[SolverParityPair] = Field(default_factory=list)


class SolverParityPairResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    passed: bool
    diff: RuntimeLegacyDiffReport
    trace_audit: RuntimeTraceAudit
    missing_handler_ids: list[str] = Field(default_factory=list)
    legacy_latency_ms: int = Field(default=0, ge=0)
    runtime_latency_ms: int = Field(default=0, ge=0)
    latency_regression_ratio: float = 0
    legacy_model_calls: int = Field(default=0, ge=0)
    runtime_model_calls: int = Field(default=0, ge=0)
    model_call_regression_ratio: float = 0
    failed_checks: list[str] = Field(default_factory=list)


class SolverParitySuiteReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_id: str
    suite_version: str
    canary_eligible: bool
    pair_count: int = Field(default=0, ge=0)
    passed_pair_count: int = Field(default=0, ge=0)
    status_mismatch_rate: float = Field(default=0, ge=0, le=1)
    answer_presence_mismatch_rate: float = Field(default=0, ge=0, le=1)
    trace_invalid_rate: float = Field(default=0, ge=0, le=1)
    handler_mismatch_rate: float = Field(default=0, ge=0, le=1)
    latency_regression_ratio: float = 0
    model_call_regression_ratio: float = 0
    single_pair_latency_regression_count: int = Field(default=0, ge=0)
    single_pair_model_call_regression_count: int = Field(default=0, ge=0)
    thresholds: SolverParityThresholds
    failed_checks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(
        default_factory=lambda: [
            "semantic_equivalence_requires_human_or_model_evaluation",
            "canary_gate_only_covers_structural_and_operational_parity",
        ]
    )
    results: list[SolverParityPairResult] = Field(default_factory=list)


def _metrics(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    result_content = payload.get("result_content")
    result = result_content if isinstance(result_content, Mapping) else payload
    for candidate in (
        payload.get("metrics"),
        payload.get("metrics_data"),
        result.get("metrics"),
        result.get("metrics_data"),
    ):
        if isinstance(candidate, Mapping):
            return candidate
    return {}


def _metric_int(payload: Mapping[str, Any], key: str) -> int:
    value = _metrics(payload).get(key, payload.get(key, 0))
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _ratio(delta: int, baseline: int) -> float:
    if delta <= 0:
        return 0.0
    return round(delta / max(1, baseline), 6)


def _trace_handler_ids(records: Sequence[Mapping[str, Any]]) -> set[str]:
    if not records:
        return set()
    ordered = sorted(records, key=lambda item: int(item.get("sequence", 0)))
    state_data = ordered[-1].get("state_data")
    if not isinstance(state_data, Mapping):
        return set()
    plan = state_data.get("plan")
    nodes = plan.get("nodes") if isinstance(plan, Mapping) else None
    if not isinstance(nodes, list):
        return set()
    return {
        str(node.get("handler_id", ""))
        for node in nodes
        if isinstance(node, Mapping) and node.get("handler_id")
    }


def evaluate_solver_parity_pair(
    pair: SolverParityPair,
    *,
    thresholds: SolverParityThresholds | None = None,
) -> SolverParityPairResult:
    trace_audit = audit_checkpoint_trace(pair.runtime_checkpoints)
    diff = build_runtime_legacy_diff(
        pair.legacy_payload,
        pair.runtime_payload,
        runtime_trace=trace_audit,
    )
    handlers = _trace_handler_ids(pair.runtime_checkpoints)
    missing_handlers = sorted(pair.required_handler_ids - handlers)
    legacy_latency = _metric_int(pair.legacy_payload, "latency_ms")
    runtime_latency = _metric_int(pair.runtime_payload, "latency_ms")
    legacy_calls = _metric_int(pair.legacy_payload, "model_calls")
    runtime_calls = _metric_int(pair.runtime_payload, "model_calls")
    latency_ratio = _ratio(runtime_latency - legacy_latency, legacy_latency)
    call_ratio = _ratio(runtime_calls - legacy_calls, legacy_calls)
    failed_checks: list[str] = []
    if not diff.status_match:
        failed_checks.append("status_mismatch")
    if not diff.answer_presence_match:
        failed_checks.append("answer_presence_mismatch")
    if not trace_audit.valid:
        failed_checks.append("runtime_trace_invalid")
    if missing_handlers:
        failed_checks.append("runtime_handler_path_mismatch")
    if (
        thresholds is not None
        and latency_ratio > thresholds.max_single_pair_latency_regression_ratio
    ):
        failed_checks.append("single_pair_latency_regression_above_threshold")
    if (
        thresholds is not None
        and call_ratio > thresholds.max_single_pair_model_call_regression_ratio
    ):
        failed_checks.append("single_pair_model_call_regression_above_threshold")
    return SolverParityPairResult(
        case_id=pair.case_id,
        passed=not failed_checks,
        diff=diff,
        trace_audit=trace_audit,
        missing_handler_ids=missing_handlers,
        legacy_latency_ms=legacy_latency,
        runtime_latency_ms=runtime_latency,
        latency_regression_ratio=latency_ratio,
        legacy_model_calls=legacy_calls,
        runtime_model_calls=runtime_calls,
        model_call_regression_ratio=call_ratio,
        failed_checks=failed_checks,
    )


def evaluate_solver_parity_suite(
    suite: SolverParitySuite | Mapping[str, Any],
) -> SolverParitySuiteReport:
    validated = (
        suite
        if isinstance(suite, SolverParitySuite)
        else SolverParitySuite.model_validate(suite)
    )
    results = [
        evaluate_solver_parity_pair(pair, thresholds=validated.thresholds)
        for pair in validated.pairs
    ]
    pair_count = len(results)
    denominator = max(1, pair_count)
    status_mismatches = sum(not item.diff.status_match for item in results)
    answer_mismatches = sum(not item.diff.answer_presence_match for item in results)
    trace_invalid = sum(not item.trace_audit.valid for item in results)
    handler_mismatches = sum(bool(item.missing_handler_ids) for item in results)
    legacy_latency = sum(item.legacy_latency_ms for item in results)
    runtime_latency = sum(item.runtime_latency_ms for item in results)
    legacy_calls = sum(item.legacy_model_calls for item in results)
    runtime_calls = sum(item.runtime_model_calls for item in results)
    latency_ratio = _ratio(runtime_latency - legacy_latency, legacy_latency)
    call_ratio = _ratio(runtime_calls - legacy_calls, legacy_calls)
    thresholds = validated.thresholds
    single_pair_latency_regressions = sum(
        item.latency_regression_ratio
        > thresholds.max_single_pair_latency_regression_ratio
        for item in results
    )
    single_pair_model_call_regressions = sum(
        item.model_call_regression_ratio
        > thresholds.max_single_pair_model_call_regression_ratio
        for item in results
    )
    failed_checks: list[str] = []
    if pair_count < thresholds.min_pairs:
        failed_checks.append("minimum_pair_count_not_met")
    rates = {
        "status_mismatch_rate": status_mismatches / denominator,
        "answer_presence_mismatch_rate": answer_mismatches / denominator,
        "trace_invalid_rate": trace_invalid / denominator,
        "handler_mismatch_rate": handler_mismatches / denominator,
    }
    threshold_pairs = (
        ("status_mismatch_rate", thresholds.max_status_mismatch_rate),
        (
            "answer_presence_mismatch_rate",
            thresholds.max_answer_presence_mismatch_rate,
        ),
        ("trace_invalid_rate", thresholds.max_trace_invalid_rate),
        ("handler_mismatch_rate", thresholds.max_handler_mismatch_rate),
    )
    for name, threshold in threshold_pairs:
        if rates[name] > threshold:
            failed_checks.append(f"{name}_above_threshold")
    if latency_ratio > thresholds.max_latency_regression_ratio:
        failed_checks.append("latency_regression_above_threshold")
    if call_ratio > thresholds.max_model_call_regression_ratio:
        failed_checks.append("model_call_regression_above_threshold")
    if single_pair_latency_regressions:
        failed_checks.append("single_pair_latency_regression_above_threshold")
    if single_pair_model_call_regressions:
        failed_checks.append("single_pair_model_call_regression_above_threshold")
    return SolverParitySuiteReport(
        suite_id=validated.suite_id,
        suite_version=validated.suite_version,
        canary_eligible=not failed_checks,
        pair_count=pair_count,
        passed_pair_count=sum(item.passed for item in results),
        status_mismatch_rate=rates["status_mismatch_rate"],
        answer_presence_mismatch_rate=rates["answer_presence_mismatch_rate"],
        trace_invalid_rate=rates["trace_invalid_rate"],
        handler_mismatch_rate=rates["handler_mismatch_rate"],
        latency_regression_ratio=latency_ratio,
        model_call_regression_ratio=call_ratio,
        single_pair_latency_regression_count=single_pair_latency_regressions,
        single_pair_model_call_regression_count=single_pair_model_call_regressions,
        thresholds=thresholds,
        failed_checks=failed_checks,
        results=results,
    )
