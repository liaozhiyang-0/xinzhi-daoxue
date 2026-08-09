"""Offline Runtime trace auditing and evaluation primitives.

These helpers consume serialized checkpoints only. They do not invoke a
Provider, tool, or model, which makes CI and post-incident replay safe and
reproducible.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.runtime.contracts import AgentRun, RuntimeNodeStatus, RuntimeRunStatus
from app.runtime.semantic_evidence import SHA256_PATTERN


class RuntimeCheckpointRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    state_version: int = Field(ge=1)
    state_data: dict[str, Any]
    event_sequence: int = Field(default=0, ge=0)


class RuntimeTraceAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    run_id: str = ""
    checkpoint_count: int = Field(default=0, ge=0)
    first_state_version: int | None = None
    last_state_version: int | None = None
    first_event_sequence: int | None = None
    last_event_sequence: int | None = None
    final_status: str = ""
    agent_ids: list[str] = Field(default_factory=list)
    plan_versions: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class RuntimeEvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_version: str = Field(default="1", min_length=1, max_length=32)
    case_id: str = Field(min_length=1, max_length=120)
    expected_status: RuntimeRunStatus
    required_node_statuses: dict[str, RuntimeNodeStatus] = Field(
        default_factory=dict
    )
    required_handler_ids: set[str] = Field(default_factory=set)
    max_iterations: int | None = Field(default=None, ge=0)
    require_checkpoint_trace: bool = True


class RuntimeEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    passed: bool
    run_id: str
    status: str
    iteration: int
    checkpoint_count: int
    replan_count: int
    failed_checks: list[str] = Field(default_factory=list)


class RuntimeParitySnapshot(BaseModel):
    """Bounded structural facts for Legacy/Runtime comparison.

    Structural parity is a migration guard, not evidence that two answers
    have equivalent meaning.
    """

    model_config = ConfigDict(extra="forbid")

    source: str
    status: str = ""
    provider: str = ""
    answer_present: bool = False
    artifact_count: int = Field(default=0, ge=0)
    structured_result_keys: list[str] = Field(default_factory=list)
    runtime_run_id: str = ""
    runtime_node_statuses: dict[str, str] = Field(default_factory=dict)


class RuntimeLegacyDiffReport(BaseModel):
    """Offline, non-semantic migration comparison report."""

    model_config = ConfigDict(extra="forbid")

    report_version: str = "1"
    legacy: RuntimeParitySnapshot
    runtime: RuntimeParitySnapshot
    status_match: bool
    answer_presence_match: bool
    provider_match: bool
    artifact_count_delta: int
    structured_result_keys_added: list[str] = Field(default_factory=list)
    structured_result_keys_removed: list[str] = Field(default_factory=list)
    runtime_trace_valid: bool | None = None
    canary_eligible: bool = False
    semantic_equivalence: str = "not_evaluated"
    warnings: list[str] = Field(default_factory=list)


class RuntimeCanaryThresholds(BaseModel):
    """Operational limits for a provider-free Legacy/Runtime canary gate."""

    model_config = ConfigDict(extra="forbid")

    min_pairs: int = Field(default=1, ge=1)
    max_status_mismatch_rate: float = Field(default=0, ge=0, le=1)
    max_answer_presence_mismatch_rate: float = Field(default=0, ge=0, le=1)
    max_provider_mismatch_rate: float = Field(default=0, ge=0, le=1)
    max_trace_invalid_rate: float = Field(default=0, ge=0, le=1)
    max_latency_regression_ratio: float = Field(default=0.5, ge=0)
    max_model_call_regression_ratio: float = Field(default=0.5, ge=0)
    max_unreconciled_recovery_rate: float = Field(default=0, ge=0, le=1)


class RuntimeCanaryEvidence(BaseModel):
    """Provenance required before a structural canary result can release."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["synthetic", "authorized_paired"] = "synthetic"
    agent_id: str = Field(default="", max_length=160)
    agent_version: str = Field(default="", max_length=64)
    runtime_plan_version: str = Field(default="", max_length=64)
    authorization_ref: str = Field(default="", max_length=240)
    captured_at: datetime | None = None
    redaction_status: Literal["not_applicable", "redacted", "unknown"] = (
        "not_applicable"
    )

    @property
    def release_ready(self) -> bool:
        return (
            self.kind == "authorized_paired"
            and bool(self.agent_id.strip())
            and bool(self.agent_version.strip())
            and bool(self.runtime_plan_version.strip())
            and bool(self.authorization_ref.strip())
            and self.captured_at is not None
            and self.redaction_status == "redacted"
        )


class RuntimeCanaryPair(BaseModel):
    """One serialized Legacy/Runtime case used by the canary evaluator."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=160)
    # Synthetic suites created before input binding may omit this field.  An
    # authorized paired suite is release-eligible only when every pair has a
    # valid digest, enforced by ``_release_provenance_failures`` below.
    input_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    legacy_payload: dict[str, Any]
    runtime_payload: dict[str, Any]
    runtime_checkpoints: list[dict[str, Any]] = Field(default_factory=list)


class RuntimeCanaryPairResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    passed: bool
    diff: RuntimeLegacyDiffReport
    trace_audit: RuntimeTraceAudit
    legacy_latency_ms: int = Field(default=0, ge=0)
    runtime_latency_ms: int = Field(default=0, ge=0)
    latency_regression_ratio: float = 0
    legacy_model_calls: int = Field(default=0, ge=0)
    runtime_model_calls: int = Field(default=0, ge=0)
    model_call_regression_ratio: float = 0
    recovery_required: bool = False
    reconciled: bool = False
    failed_checks: list[str] = Field(default_factory=list)


class RuntimeCanarySuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_version: str = Field(default="1", min_length=1, max_length=32)
    suite_id: str = Field(min_length=1, max_length=160)
    evidence: RuntimeCanaryEvidence = Field(default_factory=RuntimeCanaryEvidence)
    thresholds: RuntimeCanaryThresholds = Field(
        default_factory=RuntimeCanaryThresholds
    )
    pairs: list[RuntimeCanaryPair] = Field(default_factory=list)


class RuntimeCanaryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite_id: str
    suite_version: str
    canary_eligible: bool
    release_eligible: bool = False
    evidence: RuntimeCanaryEvidence
    pair_count: int = Field(default=0, ge=0)
    passed_pair_count: int = Field(default=0, ge=0)
    status_mismatch_rate: float = Field(default=0, ge=0, le=1)
    answer_presence_mismatch_rate: float = Field(default=0, ge=0, le=1)
    provider_mismatch_rate: float = Field(default=0, ge=0, le=1)
    trace_invalid_rate: float = Field(default=0, ge=0, le=1)
    latency_regression_ratio: float = 0
    model_call_regression_ratio: float = 0
    recovery_required_count: int = Field(default=0, ge=0)
    reconciled_count: int = Field(default=0, ge=0)
    unreconciled_recovery_count: int = Field(default=0, ge=0)
    unreconciled_recovery_rate: float = Field(default=0, ge=0, le=1)
    thresholds: RuntimeCanaryThresholds
    failed_checks: list[str] = Field(default_factory=list)
    release_failed_checks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(
        default_factory=lambda: [
            "semantic_equivalence_requires_human_or_model_evaluation",
            "canary_gate_only_covers_structural_and_operational_parity",
        ]
    )
    results: list[RuntimeCanaryPairResult] = Field(default_factory=list)


def _payload_metrics(payload: Mapping[str, Any]) -> Mapping[str, Any]:
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


def _payload_metric_int(payload: Mapping[str, Any], key: str) -> int:
    value = _payload_metrics(payload).get(key, payload.get(key, 0))
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _positive_ratio(delta: int, baseline: int) -> float:
    if delta <= 0:
        return 0.0
    return round(delta / max(1, baseline), 6)


def _runtime_node_payloads(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    runtime = payload.get("runtime")
    view = runtime if isinstance(runtime, Mapping) else payload
    nodes = view.get("nodes")
    if isinstance(nodes, Mapping):
        return [item for item in nodes.values() if isinstance(item, Mapping)]
    if isinstance(nodes, list):
        return [item for item in nodes if isinstance(item, Mapping)]
    return []


def _runtime_event_payloads(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    events = payload.get("events")
    if not isinstance(events, list):
        return []
    return [item for item in events if isinstance(item, Mapping)]


def _recovery_evidence(payload: Mapping[str, Any]) -> tuple[bool, bool]:
    recovery_required = any(
        str(item.get("error_code", ""))
        == "in_flight_execution_requires_reconciliation"
        for item in _runtime_node_payloads(payload)
    )
    reconciled = False
    for event in _runtime_event_payloads(payload):
        event_type = str(event.get("type", ""))
        data = event.get("data")
        if (
            event_type in {"runtime.reconciled", "agent.progress"}
            and isinstance(data, Mapping)
            and data.get("status") == "reconciled"
        ):
            reconciled = True
            break
    return recovery_required, reconciled


def _payload_agent_id(payload: Mapping[str, Any]) -> str:
    """Read the redacted Agent identity from common result envelopes."""

    candidates: list[Mapping[str, Any]] = [payload]
    result_content = payload.get("result_content")
    if isinstance(result_content, Mapping):
        candidates.append(result_content)
    for candidate in candidates:
        value = candidate.get("agent_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _release_provenance_failures(
    evidence: RuntimeCanaryEvidence,
    pair: RuntimeCanaryPair,
    trace: RuntimeTraceAudit,
) -> list[str]:
    failures: list[str] = []
    if not evidence.agent_version.strip():
        failures.append("evidence_agent_version_missing")
    if not evidence.runtime_plan_version.strip():
        failures.append("evidence_runtime_plan_version_missing")
    if evidence.kind == "authorized_paired" and pair.input_sha256 is None:
        failures.append(f"{pair.case_id}:input_sha256_missing")
    if not trace.agent_ids:
        failures.append(f"{pair.case_id}:runtime_launch_identity_missing")
    elif any(agent_id != evidence.agent_id for agent_id in trace.agent_ids):
        failures.append(f"{pair.case_id}:runtime_launch_identity_mismatch")
    if not trace.plan_versions:
        failures.append(f"{pair.case_id}:runtime_plan_version_missing")
    elif evidence.runtime_plan_version not in trace.plan_versions:
        failures.append(f"{pair.case_id}:runtime_plan_version_mismatch")
    for label, payload in (
        ("legacy", pair.legacy_payload),
        ("runtime", pair.runtime_payload),
    ):
        payload_agent_id = _payload_agent_id(payload)
        if not payload_agent_id:
            failures.append(f"{pair.case_id}:{label}_agent_identity_missing")
        elif payload_agent_id != evidence.agent_id:
            failures.append(f"{pair.case_id}:{label}_agent_identity_mismatch")
    return failures


def evaluate_runtime_canary_pair(
    pair: RuntimeCanaryPair,
) -> RuntimeCanaryPairResult:
    trace_audit = audit_checkpoint_trace(pair.runtime_checkpoints)
    diff = build_runtime_legacy_diff(
        pair.legacy_payload,
        pair.runtime_payload,
        runtime_trace=trace_audit,
    )
    legacy_latency = _payload_metric_int(pair.legacy_payload, "latency_ms")
    runtime_latency = _payload_metric_int(pair.runtime_payload, "latency_ms")
    legacy_calls = _payload_metric_int(pair.legacy_payload, "model_calls")
    runtime_calls = _payload_metric_int(pair.runtime_payload, "model_calls")
    recovery_required, reconciled = _recovery_evidence(pair.runtime_payload)
    failed_checks: list[str] = []
    if not diff.status_match:
        failed_checks.append("status_mismatch")
    if not diff.answer_presence_match:
        failed_checks.append("answer_presence_mismatch")
    if not diff.provider_match:
        failed_checks.append("provider_mismatch")
    if not trace_audit.valid:
        failed_checks.append("runtime_trace_invalid")
    if recovery_required and not reconciled:
        failed_checks.append("recovery_unreconciled")
    return RuntimeCanaryPairResult(
        case_id=pair.case_id,
        passed=not failed_checks,
        diff=diff,
        trace_audit=trace_audit,
        legacy_latency_ms=legacy_latency,
        runtime_latency_ms=runtime_latency,
        latency_regression_ratio=_positive_ratio(
            runtime_latency - legacy_latency, legacy_latency
        ),
        legacy_model_calls=legacy_calls,
        runtime_model_calls=runtime_calls,
        model_call_regression_ratio=_positive_ratio(
            runtime_calls - legacy_calls, legacy_calls
        ),
        recovery_required=recovery_required,
        reconciled=reconciled,
        failed_checks=failed_checks,
    )


def evaluate_runtime_canary_suite(
    suite: RuntimeCanarySuite | Mapping[str, Any],
) -> RuntimeCanaryReport:
    validated = (
        suite
        if isinstance(suite, RuntimeCanarySuite)
        else RuntimeCanarySuite.model_validate(suite)
    )
    results = [evaluate_runtime_canary_pair(pair) for pair in validated.pairs]
    pair_count = len(results)
    denominator = max(1, pair_count)
    status_mismatches = sum(not item.diff.status_match for item in results)
    answer_mismatches = sum(
        not item.diff.answer_presence_match for item in results
    )
    provider_mismatches = sum(not item.diff.provider_match for item in results)
    trace_invalid = sum(not item.trace_audit.valid for item in results)
    legacy_latency = sum(item.legacy_latency_ms for item in results)
    runtime_latency = sum(item.runtime_latency_ms for item in results)
    legacy_calls = sum(item.legacy_model_calls for item in results)
    runtime_calls = sum(item.runtime_model_calls for item in results)
    recovery_required = sum(item.recovery_required for item in results)
    reconciled = sum(item.reconciled for item in results)
    unreconciled = sum(
        item.recovery_required and not item.reconciled for item in results
    )
    thresholds = validated.thresholds
    rates = {
        "status_mismatch_rate": status_mismatches / denominator,
        "answer_presence_mismatch_rate": answer_mismatches / denominator,
        "provider_mismatch_rate": provider_mismatches / denominator,
        "trace_invalid_rate": trace_invalid / denominator,
        "unreconciled_recovery_rate": unreconciled / denominator,
    }
    failed_checks: list[str] = []
    if pair_count < thresholds.min_pairs:
        failed_checks.append("minimum_pair_count_not_met")
    for name, threshold in (
        ("status_mismatch_rate", thresholds.max_status_mismatch_rate),
        (
            "answer_presence_mismatch_rate",
            thresholds.max_answer_presence_mismatch_rate,
        ),
        ("provider_mismatch_rate", thresholds.max_provider_mismatch_rate),
        ("trace_invalid_rate", thresholds.max_trace_invalid_rate),
        (
            "unreconciled_recovery_rate",
            thresholds.max_unreconciled_recovery_rate,
        ),
    ):
        if rates[name] > threshold:
            failed_checks.append(f"{name}_above_threshold")
    latency_ratio = _positive_ratio(runtime_latency - legacy_latency, legacy_latency)
    call_ratio = _positive_ratio(runtime_calls - legacy_calls, legacy_calls)
    if latency_ratio > thresholds.max_latency_regression_ratio:
        failed_checks.append("latency_regression_above_threshold")
    if call_ratio > thresholds.max_model_call_regression_ratio:
        failed_checks.append("model_call_regression_above_threshold")
    release_failed_checks: list[str] = []
    if validated.evidence.kind == "authorized_paired":
        for pair, result in zip(validated.pairs, results, strict=True):
            release_failed_checks.extend(
                _release_provenance_failures(
                    validated.evidence,
                    pair,
                    result.trace_audit,
                )
            )
    return RuntimeCanaryReport(
        suite_id=validated.suite_id,
        suite_version=validated.suite_version,
        canary_eligible=not failed_checks,
        release_eligible=(
            not failed_checks
            and not release_failed_checks
            and validated.evidence.release_ready
        ),
        evidence=validated.evidence,
        pair_count=pair_count,
        passed_pair_count=sum(item.passed for item in results),
        status_mismatch_rate=rates["status_mismatch_rate"],
        answer_presence_mismatch_rate=rates["answer_presence_mismatch_rate"],
        provider_mismatch_rate=rates["provider_mismatch_rate"],
        trace_invalid_rate=rates["trace_invalid_rate"],
        latency_regression_ratio=latency_ratio,
        model_call_regression_ratio=call_ratio,
        recovery_required_count=recovery_required,
        reconciled_count=reconciled,
        unreconciled_recovery_count=unreconciled,
        unreconciled_recovery_rate=rates["unreconciled_recovery_rate"],
        thresholds=thresholds,
        failed_checks=failed_checks,
        release_failed_checks=sorted(set(release_failed_checks)),
        results=results,
    )


def build_runtime_parity_snapshot(
    payload: Mapping[str, Any], *, source: str
) -> RuntimeParitySnapshot:
    """Extract bounded parity facts from a TaskRead or serialized Runtime run."""

    result_payload = payload.get("result_content")
    result = result_payload if isinstance(result_payload, Mapping) else payload
    structured = result.get("structured_result")
    structured_keys = (
        sorted(str(key) for key in structured)
        if isinstance(structured, Mapping)
        else []
    )
    answer = result.get("answer", payload.get("answer", ""))
    artifacts = result.get("artifacts", payload.get("artifact_ids", []))
    artifact_count = len(artifacts) if isinstance(artifacts, (list, tuple)) else 0
    nodes = payload.get("nodes")
    runtime_nodes: dict[str, str] = {}
    if isinstance(nodes, Mapping):
        runtime_nodes = {
            str(node_id): str(node.get("status", ""))
            for node_id, node in nodes.items()
            if isinstance(node, Mapping)
        }
    return RuntimeParitySnapshot(
        source=source,
        status=str(payload.get("status", result.get("status", ""))),
        provider=str(payload.get("provider", result.get("provider", ""))),
        answer_present=isinstance(answer, str) and bool(answer.strip()),
        artifact_count=artifact_count,
        structured_result_keys=structured_keys,
        runtime_run_id=str(payload.get("run_id", "")),
        runtime_node_statuses=runtime_nodes,
    )


def build_runtime_legacy_diff(
    legacy: Mapping[str, Any],
    runtime: Mapping[str, Any],
    *,
    legacy_source: str = "legacy",
    runtime_source: str = "runtime",
    runtime_trace: RuntimeTraceAudit | None = None,
) -> RuntimeLegacyDiffReport:
    """Compare serialized results without invoking any Provider or tool."""

    legacy_snapshot = build_runtime_parity_snapshot(
        legacy, source=legacy_source
    )
    runtime_snapshot = build_runtime_parity_snapshot(
        runtime, source=runtime_source
    )
    added = sorted(
        set(runtime_snapshot.structured_result_keys)
        - set(legacy_snapshot.structured_result_keys)
    )
    removed = sorted(
        set(legacy_snapshot.structured_result_keys)
        - set(runtime_snapshot.structured_result_keys)
    )
    trace_valid = runtime_trace.valid if runtime_trace else None
    canary_eligible = all(
        (
            status_match := legacy_snapshot.status == runtime_snapshot.status,
            answer_presence_match := (
                legacy_snapshot.answer_present == runtime_snapshot.answer_present
            ),
            provider_match := legacy_snapshot.provider == runtime_snapshot.provider,
            trace_valid is True,
        )
    )
    return RuntimeLegacyDiffReport(
        legacy=legacy_snapshot,
        runtime=runtime_snapshot,
        status_match=status_match,
        answer_presence_match=answer_presence_match,
        provider_match=provider_match,
        artifact_count_delta=(
            runtime_snapshot.artifact_count - legacy_snapshot.artifact_count
        ),
        structured_result_keys_added=added,
        structured_result_keys_removed=removed,
        runtime_trace_valid=trace_valid,
        canary_eligible=canary_eligible,
        warnings=[
            "semantic_equivalence_requires_human_or_model_evaluation",
            "structural_comparison_does_not_prove_answer_correctness",
        ],
    )


def audit_checkpoint_trace(
    payloads: Sequence[RuntimeCheckpointRecord | Mapping[str, Any]],
) -> RuntimeTraceAudit:
    errors: list[str] = []
    records: list[RuntimeCheckpointRecord] = []
    for index, payload in enumerate(payloads, start=1):
        try:
            records.append(
                payload
                if isinstance(payload, RuntimeCheckpointRecord)
                else RuntimeCheckpointRecord.model_validate(payload)
            )
        except ValueError as exc:
            errors.append(f"checkpoint_{index}_invalid:{exc}")
    if not records:
        return RuntimeTraceAudit(valid=False, errors=["checkpoint_trace_empty"])

    records.sort(key=lambda item: item.sequence)
    expected_sequence = 1
    previous_version = 0
    previous_event_sequence = 0
    run_id = ""
    agent_ids: list[str] = []
    plan_versions: list[str] = []
    final_status = ""
    for record in records:
        if record.sequence != expected_sequence:
            errors.append(
                f"checkpoint_sequence_gap:{expected_sequence}->{record.sequence}"
            )
        expected_sequence = record.sequence + 1
        if record.state_version <= previous_version:
            errors.append("checkpoint_state_version_not_increasing")
        previous_version = record.state_version
        if record.event_sequence < previous_event_sequence:
            errors.append("checkpoint_event_sequence_regressed")
        previous_event_sequence = record.event_sequence
        try:
            run = AgentRun.model_validate(record.state_data)
        except ValueError as exc:
            errors.append(f"checkpoint_state_invalid:{exc}")
            continue
        if run_id and run.run_id != run_id:
            errors.append("checkpoint_run_id_changed")
        run_id = run.run_id
        plan_versions.append(run.plan.version)
        if run.launch_decision is not None:
            agent_ids.append(run.launch_decision.agent_id)
        if run.state_version != record.state_version:
            errors.append("checkpoint_state_version_mismatch")
        final_status = run.status.value

    return RuntimeTraceAudit(
        valid=not errors,
        run_id=run_id,
        checkpoint_count=len(records),
        first_state_version=records[0].state_version,
        last_state_version=records[-1].state_version,
        first_event_sequence=records[0].event_sequence,
        last_event_sequence=records[-1].event_sequence,
        final_status=final_status,
        agent_ids=sorted(set(agent_ids)),
        plan_versions=sorted(set(plan_versions)),
        errors=errors,
    )


def evaluate_runtime_run(
    run: AgentRun,
    case: RuntimeEvaluationCase,
    *,
    checkpoint_count: int = 0,
) -> RuntimeEvaluationResult:
    failures: list[str] = []
    if run.status != case.expected_status:
        failures.append(
            f"status_expected:{case.expected_status.value}:actual:{run.status.value}"
        )
    if case.require_checkpoint_trace and checkpoint_count < 1:
        failures.append("checkpoint_trace_required")
    for node_id, expected_status in case.required_node_statuses.items():
        state = run.nodes.get(node_id)
        if state is None:
            failures.append(f"node_missing:{node_id}")
        elif state.status != expected_status:
            failures.append(
                f"node_status:{node_id}:expected:{expected_status.value}"
                f":actual:{state.status.value}"
            )
    handler_ids = {node.handler_id for node in run.plan.nodes}
    for handler_id in sorted(case.required_handler_ids - handler_ids):
        failures.append(f"handler_missing:{handler_id}")
    if case.max_iterations is not None and run.iteration > case.max_iterations:
        failures.append("iteration_budget_exceeded")
    return RuntimeEvaluationResult(
        case_id=case.case_id,
        passed=not failures,
        run_id=run.run_id,
        status=run.status.value,
        iteration=run.iteration,
        checkpoint_count=checkpoint_count,
        replan_count=run.iteration,
        failed_checks=failures,
    )
