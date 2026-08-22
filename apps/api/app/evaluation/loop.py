from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from enum import StrEnum
from statistics import mean
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.experience import (
    ExperienceCandidateCreate,
    ExperienceEvidenceLevel,
    ExperiencePrivacyClass,
    ExperienceRedactionStatus,
    ExperienceScope,
    ExperienceType,
)
from app.evaluation.contracts import (
    EvaluationCase,
    EvaluationProvenance,
    EvaluationResult,
    SuiteReport,
)
from app.evaluation.contracts import (
    FailureStage as LegacyFailureStage,
)

EvidenceLevel = Literal[
    "synthetic_provider_free",
    "offline_real_case",
    "real_provider_test",
    "controlled_canary",
    "production",
]


class LoopFailureStage(StrEnum):
    INPUT = "input"
    ROUTING = "routing"
    PLANNER = "planner"
    SKILL_SELECTION = "skill_selection"
    TOOL = "tool"
    RAG = "rag"
    MODEL_GENERATION = "model_generation"
    REFLECTION = "reflection"
    VERIFICATION = "verification"
    GOVERNANCE = "governance"
    RUNTIME = "runtime"
    INFRASTRUCTURE = "infrastructure"
    FIXTURE = "fixture"
    UNKNOWN = "unknown"


FailureSeverity = Literal["critical", "high", "medium", "low", "info"]
ProposalType = Literal[
    "planner_policy",
    "skill_metadata",
    "skill_selection",
    "tool_binding",
    "rag_policy",
    "verification_rule",
    "reflection_policy",
    "experience_strategy",
    "prompt_candidate",
    "fallback_policy",
    "test_fixture",
    "infrastructure",
]
ProposalStatus = Literal[
    "draft",
    "reviewed",
    "replay_ready",
    "validated",
    "approved",
    "rejected",
    "deferred",
    "promoted",
]


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


_PRIVATE_KEYS = frozenset(
    {
        "answer",
        "answers",
        "content",
        "full_text",
        "message",
        "messages",
        "prompt",
        "raw_answer",
        "raw_content",
        "raw_prompt",
        "student_answer",
    }
)


def _safe(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Keep bounded evidence while excluding prompts, answers and content."""

    if key.casefold() in _PRIVATE_KEYS:
        return "[omitted]"
    if depth > 3:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            str(item_key): _safe(item_value, key=str(item_key), depth=depth + 1)
            for item_key, item_value in list(value.items())[:32]
            if str(item_key).casefold() not in _PRIVATE_KEYS
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe(item, depth=depth + 1) for item in list(value)[:32]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)[:200]


class EvaluationRecord(BaseModel):
    """Unified, bounded evaluation evidence record for the existing runner."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["evaluation_record.v1"] = "evaluation_record.v1"
    evaluation_id: str = Field(default_factory=lambda: _id("eval"), min_length=1)
    suite_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    evidence_level: EvidenceLevel
    task_family: str = ""
    course: str = ""
    capability: str = ""
    expected_outcome: dict[str, Any] = Field(default_factory=dict)
    actual_outcome: dict[str, Any] = Field(default_factory=dict)
    score_dimensions: dict[str, float] = Field(default_factory=dict)
    overall_score: float | None = Field(default=None, ge=0, le=100)
    status: Literal["passed", "failed", "error", "timeout", "cached"] = "failed"
    failure_stage: LoopFailureStage | None = None
    failure_codes: list[str] = Field(default_factory=list, max_length=32)
    task_id: str = ""
    run_id: str = ""
    trace_ids: list[str] = Field(default_factory=list, max_length=32)
    planner_version: str = ""
    plan_version: str = ""
    skill_versions: dict[str, str] = Field(default_factory=dict, max_length=32)
    tool_versions: dict[str, str] = Field(default_factory=dict, max_length=32)
    model_provider_version: str = ""
    reflection_version: str = ""
    experience_ids: list[str] = Field(default_factory=list, max_length=32)
    latency_ms: float = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    cost: float = Field(default=0, ge=0)
    reproducible: bool = False
    baseline_id: str = ""
    candidate_id: str = ""


class FailureRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["failure_record.v1"] = "failure_record.v1"
    failure_id: str = Field(default_factory=lambda: _id("failure"), min_length=1)
    evaluation_id: str
    case_id: str
    stage: LoopFailureStage
    owner_component: str
    error_codes: list[str] = Field(default_factory=list, max_length=32)
    severity: FailureSeverity = "medium"
    observed_evidence: dict[str, Any] = Field(default_factory=dict)
    expected_behavior: dict[str, Any] = Field(default_factory=dict)
    actual_behavior: dict[str, Any] = Field(default_factory=dict)
    reproducible: bool | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    upstream_dependencies: list[str] = Field(default_factory=list, max_length=32)
    downstream_effects: list[str] = Field(default_factory=list, max_length=32)
    version_context: dict[str, str] = Field(default_factory=dict, max_length=32)
    evidence_refs: list[str] = Field(default_factory=list, max_length=32)
    dimensions: dict[str, str] = Field(default_factory=dict, max_length=32)


class FailureAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_stage: LoopFailureStage
    component: str
    contributing_factors: list[str] = Field(default_factory=list, max_length=16)
    evidence_refs: list[str] = Field(default_factory=list, max_length=32)
    confidence: float = Field(default=0, ge=0, le=1)
    alternative_causes: list[str] = Field(default_factory=list, max_length=16)
    reproducibility: bool | None = None


class FailurePattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["failure_pattern.v1"] = "failure_pattern.v1"
    pattern_id: str = Field(default_factory=lambda: _id("pattern"))
    occurrence_count: int = Field(default=0, ge=0)
    case_ids: list[str] = Field(default_factory=list, max_length=512)
    failure_ids: list[str] = Field(default_factory=list, max_length=512)
    dimensions: dict[str, str] = Field(default_factory=dict, max_length=32)
    primary_stage: LoopFailureStage
    owner_component: str
    error_codes: list[str] = Field(default_factory=list, max_length=32)
    evidence_level_counts: dict[str, int] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list, max_length=64)
    reproducible_rate: float = Field(default=0, ge=0, le=1)
    generalizable: bool = False
    aggregation_eligible: bool = False
    guardrails: list[str] = Field(default_factory=list, max_length=16)


class ImprovementProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["improvement_proposal.v1"] = "improvement_proposal.v1"
    proposal_id: str = Field(default_factory=lambda: _id("proposal"))
    source_pattern_ids: list[str] = Field(min_length=1, max_length=32)
    proposal_type: ProposalType
    target_component: str = Field(min_length=1)
    target_version: str = ""
    problem_statement: str = Field(min_length=1, max_length=2000)
    proposed_change: str = Field(min_length=1, max_length=4000)
    expected_effect: str = Field(min_length=1, max_length=2000)
    success_metrics: dict[str, float | int | str] = Field(default_factory=dict)
    risk: str = Field(min_length=1, max_length=2000)
    estimated_cost: float = Field(default=0, ge=0)
    required_cases: list[str] = Field(default_factory=list, max_length=512)
    rollback_plan: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=64)
    status: ProposalStatus = "draft"


class ReplayPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score_epsilon: float = Field(default=0.01, ge=0)
    max_cost_increase_ratio: float = Field(default=0.2, ge=0)
    allow_failure_rate_increase: bool = False
    allow_safety_degradation: bool = False


class ReplayResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["replay_result.v1"] = "replay_result.v1"
    replay_result_id: str = Field(default_factory=lambda: _id("replay"))
    proposal_id: str
    baseline_id: str
    candidate_id: str
    case_count: int = Field(ge=0)
    improved: int = Field(default=0, ge=0)
    unchanged: int = Field(default=0, ge=0)
    degraded: int = Field(default=0, ge=0)
    critical_regressions: list[str] = Field(default_factory=list, max_length=512)
    score_delta: float | None = None
    failure_rate_delta: float | None = None
    latency_delta: float | None = None
    token_delta: int | None = None
    cost_delta: float | None = None
    safety_delta: float | None = None
    evidence_level: EvidenceLevel
    drift: list[str] = Field(default_factory=list, max_length=64)
    gate_passed: bool = False
    gate_reasons: list[str] = Field(default_factory=list, max_length=32)


class PromotionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["promotion_decision.v1"] = "promotion_decision.v1"
    proposal_id: str
    replay_result_id: str
    status: Literal["approve", "reject", "defer", "needs_review"]
    eligible_targets: list[str] = Field(default_factory=list, max_length=8)
    evidence_level: EvidenceLevel
    regression_summary: dict[str, Any] = Field(default_factory=dict)
    risk: str
    approval_reason: str
    reviewer: str = ""
    policy: str = "phase_f_default"
    rollback_requirement: str = Field(min_length=1)


class EvaluationLoopSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["evaluation_loop_summary.v1"] = "evaluation_loop_summary.v1"
    suite_id: str
    evidence_level: EvidenceLevel
    case_count: int = Field(ge=0)
    expected_case_count: int = Field(default=336, ge=1)
    coverage_status: Literal["complete", "partial", "empty"]
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    overall_score: float | None = None
    course_breakdown: dict[str, dict[str, float | int]] = Field(default_factory=dict)
    task_family_breakdown: dict[str, dict[str, float | int]] = Field(
        default_factory=dict
    )
    failure_stage_breakdown: dict[str, int] = Field(default_factory=dict)
    route_planner_failures: int = Field(default=0, ge=0)
    skill_tool_failures: int = Field(default=0, ge=0)
    generation_failures: int = Field(default=0, ge=0)
    verification_reflection_failures: int = Field(default=0, ge=0)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    total_tokens: int = Field(default=0, ge=0)
    total_cost: float = Field(default=0, ge=0)
    top_pattern_ids: list[str] = Field(default_factory=list, max_length=10)
    historical_failures_included: bool = False
    real_provider_evidence_included: bool = False


_LEGACY_STAGE_MAP: dict[LegacyFailureStage, LoopFailureStage] = {
    LegacyFailureStage.INPUT_NORMALIZATION: LoopFailureStage.INPUT,
    LegacyFailureStage.ROUTING: LoopFailureStage.ROUTING,
    LegacyFailureStage.COURSE_PACK_RESOLUTION: LoopFailureStage.ROUTING,
    LegacyFailureStage.MULTIMODAL_EXTRACTION: LoopFailureStage.INPUT,
    LegacyFailureStage.PROBLEM_STRUCTURING: LoopFailureStage.PLANNER,
    LegacyFailureStage.SOLVABILITY: LoopFailureStage.PLANNER,
    LegacyFailureStage.CAPABILITY_SELECTION: LoopFailureStage.SKILL_SELECTION,
    LegacyFailureStage.RETRIEVAL: LoopFailureStage.RAG,
    LegacyFailureStage.PLANNING: LoopFailureStage.PLANNER,
    LegacyFailureStage.GENERATION: LoopFailureStage.MODEL_GENERATION,
    LegacyFailureStage.TOOL_EXECUTION: LoopFailureStage.TOOL,
    LegacyFailureStage.VERIFICATION: LoopFailureStage.VERIFICATION,
    LegacyFailureStage.CORRECTION: LoopFailureStage.REFLECTION,
    LegacyFailureStage.CITATION_VALIDATION: LoopFailureStage.VERIFICATION,
    LegacyFailureStage.FINALIZATION: LoopFailureStage.VERIFICATION,
    LegacyFailureStage.TIMEOUT: LoopFailureStage.INFRASTRUCTURE,
    LegacyFailureStage.PROVIDER: LoopFailureStage.INFRASTRUCTURE,
    LegacyFailureStage.UNKNOWN: LoopFailureStage.UNKNOWN,
}


def _evidence_level(report: SuiteReport, case: EvaluationCase) -> EvidenceLevel:
    if report.mode in {"live", "real_model"}:
        return "real_provider_test"
    if "controlled_canary" in case.tags:
        return "controlled_canary"
    if case.provenance.source_type == "synthetic":
        return "synthetic_provider_free"
    return "offline_real_case"


def _compact_actual(result: EvaluationResult) -> dict[str, Any]:
    actual = result.actual
    allowed = {
        "task_id",
        "run_id",
        "course",
        "intent",
        "task_family",
        "agent_id",
        "execution_agent",
        "route_status",
        "execution_path",
        "status",
        "planner_version",
        "plan_version",
        "skill_ids",
        "skill_versions",
        "selected_tools",
        "tool_versions",
        "reflection_version",
        "experience_ids",
        "verification_status",
        "quality_status",
        "error_type",
        "provider",
        "model",
        "capability",
        "metrics",
    }
    compact = {key: _safe(actual[key], key=key) for key in allowed if key in actual}
    compact["result_status"] = result.status
    compact["result_error_types"] = [str(item) for item in result.error_types]
    return compact


class EvaluationRecordAdapter:
    """Adapt the existing SuiteReport without introducing another runner."""

    @staticmethod
    def from_suite_report(
        report: SuiteReport,
        cases: Sequence[EvaluationCase] = (),
        *,
        suite_id: str = "",
        baseline_id: str = "",
        candidate_id: str = "",
    ) -> list[EvaluationRecord]:
        case_by_id = {case.case_id: case for case in cases}
        resolved_suite_id = suite_id or str(
            report.filters.get("suite") or "existing_evaluation"
        )
        return [
            EvaluationRecordAdapter.from_result(
                report,
                result,
                case_by_id.get(result.case_id),
                suite_id=resolved_suite_id,
                baseline_id=baseline_id,
                candidate_id=candidate_id,
            )
            for result in report.results
        ]

    @staticmethod
    def from_result(
        report: SuiteReport,
        result: EvaluationResult,
        case: EvaluationCase | None = None,
        *,
        suite_id: str,
        baseline_id: str = "",
        candidate_id: str = "",
    ) -> EvaluationRecord:
        actual = _compact_actual(result)
        expected = _safe(result.expected)
        model_calls = result.model_calls
        model_provider = sorted(
            {
                ":".join(
                    str(value)
                    for value in (call.get("provider"), call.get("model"))
                    if value
                )
                for call in model_calls
                if call.get("provider") or call.get("model")
            }
        )
        explicit_stage = (
            _LEGACY_STAGE_MAP.get(result.failure_stage)
            if result.failure_stage is not None
            else None
        )
        reproducible = bool(
            report.run_metadata.case_ids_sha256
            and report.run_metadata.implementation_fingerprint
        )
        return EvaluationRecord(
            suite_id=suite_id,
            case_id=result.case_id,
            evidence_level=_evidence_level(
                report,
                case
                or EvaluationCase(
                    case_id=result.case_id,
                    title=result.case_id,
                    course=str(result.expected.get("course", "")),
                    task_family=str(result.expected.get("task_family", "")),
                    intent="evaluation",
                    message="",
                    expected_agent=str(result.expected.get("agent_id", "unknown")),
                    provenance=EvaluationProvenance(source_type="synthetic"),
                ),
            ),
            task_family=str(
                case.task_family if case else result.expected.get("task_family", "")
            ),
            course=str(case.course if case else result.expected.get("course", "")),
            capability=str(
                actual.get("capability")
                or (case.problem_type if case else "")
                or result.expected.get("agent_id", "")
            ),
            expected_outcome=expected,
            actual_outcome=actual,
            score_dimensions={
                str(key): float(value)
                for key, value in result.dimension_scores.items()
                if isinstance(value, (int, float))
            },
            overall_score=result.total_score,
            status=result.status,
            failure_stage=explicit_stage,
            failure_codes=[str(item) for item in result.error_types],
            task_id=str(actual.get("task_id", "")),
            run_id=report.run_metadata.run_id,
            trace_ids=[result.trace_id] if result.trace_id else [],
            planner_version=str(actual.get("planner_version", "")),
            plan_version=str(actual.get("plan_version", "")),
            skill_versions={
                str(key): str(value)
                for key, value in dict(actual.get("skill_versions", {})).items()
            },
            tool_versions={
                str(key): str(value)
                for key, value in dict(actual.get("tool_versions", {})).items()
            },
            model_provider_version=",".join(model_provider),
            reflection_version=str(actual.get("reflection_version", "")),
            experience_ids=[str(item) for item in actual.get("experience_ids", [])]
            if isinstance(actual.get("experience_ids", []), list)
            else [],
            latency_ms=float(result.elapsed_ms),
            tokens=sum(int(call.get("total_tokens") or 0) for call in model_calls),
            cost=float(actual.get("metrics", {}).get("cost", 0) or 0)
            if isinstance(actual.get("metrics"), dict)
            else 0,
            reproducible=reproducible,
            baseline_id=baseline_id,
            candidate_id=candidate_id,
        )


class FailureAttributor:
    """Deterministic attribution; every conclusion points to bounded evidence."""

    _OWNER_BY_STAGE = {
        LoopFailureStage.INPUT: "input_boundary",
        LoopFailureStage.ROUTING: "router",
        LoopFailureStage.PLANNER: "planner",
        LoopFailureStage.SKILL_SELECTION: "skill_policy",
        LoopFailureStage.TOOL: "tool_registry",
        LoopFailureStage.RAG: "rag",
        LoopFailureStage.MODEL_GENERATION: "model_provider",
        LoopFailureStage.REFLECTION: "reflection",
        LoopFailureStage.VERIFICATION: "verification",
        LoopFailureStage.GOVERNANCE: "governance",
        LoopFailureStage.RUNTIME: "runtime",
        LoopFailureStage.INFRASTRUCTURE: "infrastructure",
        LoopFailureStage.FIXTURE: "evaluation_fixture",
        LoopFailureStage.UNKNOWN: "unknown",
    }

    def attribute(self, record: EvaluationRecord) -> FailureRecord | None:
        if record.status in {"passed", "cached"} and not record.failure_codes:
            return None
        stage = record.failure_stage or self._infer_stage(record)
        codes = list(dict.fromkeys(record.failure_codes or ["unclassified_failure"]))
        transient = {"timeout", "provider_error", "fixture_error"}
        severity: FailureSeverity = (
            "critical"
            if any("safety" in code for code in codes)
            else "high"
            if record.status in {"error", "timeout"}
            else "medium"
        )
        if stage in {LoopFailureStage.INFRASTRUCTURE, LoopFailureStage.FIXTURE}:
            severity = "low"
        reproducible = record.reproducible and not bool(set(codes) & transient)
        confidence = 0.95 if record.failure_stage else 0.65
        if stage == LoopFailureStage.UNKNOWN:
            confidence = 0.2
        observed = {
            "status": record.status,
            "failure_codes": codes,
            "stage_signal": record.failure_stage.value
            if record.failure_stage
            else "inferred",
            "actual_outcome": record.actual_outcome,
        }
        dimensions = {
            "course": record.course or "unknown",
            "task_family": record.task_family or "unknown",
            "capability": record.capability or "unknown",
            "planner_version": record.planner_version or "unknown",
            "model_provider": record.model_provider_version or "unknown",
            "input_mode": str(record.actual_outcome.get("input_mode", "unknown")),
            "evidence_quality": record.evidence_level,
            "problem_type": str(record.actual_outcome.get("problem_type", "unknown")),
            "skill": ",".join(
                str(item) for item in record.actual_outcome.get("skill_ids", [])
            )
            or "unknown",
            "tool": ",".join(
                str(item) for item in record.actual_outcome.get("selected_tools", [])
            )
            or "unknown",
        }
        return FailureRecord(
            evaluation_id=record.evaluation_id,
            case_id=record.case_id,
            stage=stage,
            owner_component=self._OWNER_BY_STAGE[stage],
            error_codes=codes,
            severity=severity,
            observed_evidence=observed,
            expected_behavior=record.expected_outcome,
            actual_behavior=record.actual_outcome,
            reproducible=reproducible,
            confidence=confidence,
            upstream_dependencies=self._dependencies(stage),
            downstream_effects=self._effects(stage),
            version_context={
                "planner_version": record.planner_version,
                "plan_version": record.plan_version,
                "model_provider_version": record.model_provider_version,
                "reflection_version": record.reflection_version,
            },
            evidence_refs=[*record.trace_ids, record.evaluation_id],
            dimensions=dimensions,
        )

    def explain(self, record: EvaluationRecord) -> FailureAttribution | None:
        failure = self.attribute(record)
        if failure is None:
            return None
        return FailureAttribution(
            primary_stage=failure.stage,
            component=failure.owner_component,
            contributing_factors=failure.error_codes,
            evidence_refs=failure.evidence_refs,
            confidence=failure.confidence,
            alternative_causes=(
                ["transient_provider_or_fixture_issue"]
                if failure.stage
                in {
                    LoopFailureStage.INFRASTRUCTURE,
                    LoopFailureStage.FIXTURE,
                }
                else []
            ),
            reproducibility=failure.reproducible,
        )

    @staticmethod
    def _infer_stage(record: EvaluationRecord) -> LoopFailureStage:
        codes = " ".join(record.failure_codes).casefold()
        if "fixture" in codes:
            return LoopFailureStage.FIXTURE
        if "route" in codes or "agent_mismatch" in codes:
            return LoopFailureStage.ROUTING
        if "skill" in codes or "capability" in codes:
            return LoopFailureStage.SKILL_SELECTION
        if "tool" in codes:
            return LoopFailureStage.TOOL
        if "rag" in codes or "retriev" in codes or "citation" in codes:
            return LoopFailureStage.RAG
        if "reflect" in codes or "correction" in codes:
            return LoopFailureStage.REFLECTION
        if "verif" in codes or "numeric" in codes:
            return LoopFailureStage.VERIFICATION
        if record.status == "timeout" or "provider" in codes:
            return LoopFailureStage.INFRASTRUCTURE
        if record.status == "error":
            return LoopFailureStage.RUNTIME
        return LoopFailureStage.UNKNOWN

    @staticmethod
    def _dependencies(stage: LoopFailureStage) -> list[str]:
        order = list(LoopFailureStage)
        index = order.index(stage)
        return [order[index - 1].value] if index else []

    @staticmethod
    def _effects(stage: LoopFailureStage) -> list[str]:
        order = list(LoopFailureStage)
        index = order.index(stage)
        return [order[index + 1].value] if index < len(order) - 1 else []


class FailurePatternAggregator:
    """Aggregate evidence while flagging transient/non-generalizable failures."""

    _KEYS = (
        "course",
        "task_family",
        "problem_type",
        "capability",
        "skill",
        "tool",
        "planner_version",
        "model_provider",
        "input_mode",
        "evidence_quality",
    )

    def aggregate(self, failures: Iterable[FailureRecord]) -> list[FailurePattern]:
        groups: dict[tuple[str, ...], list[FailureRecord]] = defaultdict(list)
        for failure in failures:
            key = (
                failure.stage.value,
                failure.owner_component,
                ";".join(failure.error_codes) or "unknown",
                *[failure.dimensions.get(item, "unknown") for item in self._KEYS],
            )
            groups[key].append(failure)
        patterns: list[FailurePattern] = []
        for key, items in sorted(groups.items(), key=lambda item: item[0]):
            stage = LoopFailureStage(key[0])
            transient = stage in {
                LoopFailureStage.INFRASTRUCTURE,
                LoopFailureStage.FIXTURE,
            }
            reproducible_rate = mean(
                1.0 if item.reproducible else 0.0 for item in items
            )
            eligible = not transient
            generalizable = eligible and reproducible_rate >= 0.5 and len(items) >= 2
            guards = []
            if transient:
                guards.append("transient_or_fixture_failure_not_strategy_evidence")
            if len(items) < 2:
                guards.append("single_observation_requires_reproduction")
            if any(
                item.dimensions.get("evidence_quality") == "synthetic_provider_free"
                for item in items
            ):
                guards.append("synthetic_evidence_cannot_claim_production_quality")
            patterns.append(
                FailurePattern(
                    occurrence_count=len(items),
                    case_ids=sorted({item.case_id for item in items}),
                    failure_ids=[item.failure_id for item in items],
                    dimensions={
                        "stage": stage.value,
                        "owner_component": key[1],
                        "error_codes": key[2],
                        **dict(zip(self._KEYS, key[3:], strict=True)),
                    },
                    primary_stage=stage,
                    owner_component=key[1],
                    error_codes=key[2].split(";"),
                    evidence_level_counts=dict(
                        Counter(
                            item.dimensions.get("evidence_quality", "unknown")
                            for item in items
                        )
                    ),
                    evidence_refs=sorted(
                        {ref for item in items for ref in item.evidence_refs}
                    )[:64],
                    reproducible_rate=reproducible_rate,
                    generalizable=generalizable,
                    aggregation_eligible=eligible,
                    guardrails=guards,
                )
            )
        return patterns


class ImprovementProposalService:
    _TRANSITIONS: dict[ProposalStatus, set[ProposalStatus]] = {
        "draft": {"reviewed", "deferred", "rejected"},
        "reviewed": {"replay_ready", "deferred", "rejected"},
        "replay_ready": {"validated", "deferred", "rejected"},
        "validated": {"approved", "deferred", "rejected"},
        "approved": {"promoted", "deferred", "rejected"},
        "rejected": set(),
        "deferred": {"reviewed", "rejected"},
        "promoted": set(),
    }

    @staticmethod
    def create(
        pattern: FailurePattern,
        *,
        proposal_type: ProposalType,
        target_component: str,
        target_version: str,
        problem_statement: str,
        proposed_change: str,
        expected_effect: str,
        success_metrics: dict[str, float | int | str],
        risk: str,
        estimated_cost: float,
        required_cases: Sequence[str],
        rollback_plan: str,
        evidence_refs: Sequence[str] = (),
    ) -> ImprovementProposal:
        if not pattern.aggregation_eligible:
            raise ValueError("only aggregation-eligible patterns can create proposals")
        return ImprovementProposal(
            source_pattern_ids=[pattern.pattern_id],
            proposal_type=proposal_type,
            target_component=target_component,
            target_version=target_version,
            problem_statement=problem_statement,
            proposed_change=proposed_change,
            expected_effect=expected_effect,
            success_metrics=success_metrics,
            risk=risk,
            estimated_cost=estimated_cost,
            required_cases=list(required_cases),
            rollback_plan=rollback_plan,
            evidence_refs=list(evidence_refs or pattern.evidence_refs),
        )

    @classmethod
    def transition(
        cls, proposal: ImprovementProposal, status: ProposalStatus
    ) -> ImprovementProposal:
        if status not in cls._TRANSITIONS[proposal.status]:
            raise ValueError(
                f"invalid proposal transition: {proposal.status}->{status}"
            )
        return proposal.model_copy(update={"status": status})


class OfflineReplayService:
    def compare(
        self,
        proposal: ImprovementProposal,
        baseline: Sequence[EvaluationRecord],
        candidate: Sequence[EvaluationRecord],
        *,
        baseline_id: str,
        candidate_id: str,
        policy: ReplayPolicy | None = None,
    ) -> ReplayResult:
        if not baseline or not candidate:
            raise ValueError("replay requires baseline and candidate records")
        baseline_by_case = {item.case_id: item for item in baseline}
        candidate_by_case = {item.case_id: item for item in candidate}
        if set(baseline_by_case) != set(candidate_by_case):
            raise ValueError("baseline and candidate must use the same case set")
        replay_policy = policy or ReplayPolicy()
        drift = self._drift(baseline, candidate)
        improved = unchanged = degraded = 0
        critical: list[str] = []
        for case_id in sorted(baseline_by_case):
            before = baseline_by_case[case_id]
            after = candidate_by_case[case_id]
            delta = (after.overall_score or 0) - (before.overall_score or 0)
            before_passed = before.status in {"passed", "cached"}
            after_passed = after.status in {"passed", "cached"}
            if delta > replay_policy.score_epsilon or (
                not before_passed and after_passed
            ):
                improved += 1
            elif delta < -replay_policy.score_epsilon or (
                before_passed and not after_passed
            ):
                degraded += 1
            else:
                unchanged += 1
            if (before_passed and not after_passed) or self._safety_regressed(
                before, after
            ):
                critical.append(case_id)
        count = len(baseline_by_case)
        baseline_score = mean(
            item.overall_score for item in baseline if item.overall_score is not None
        )
        candidate_score = mean(
            item.overall_score for item in candidate if item.overall_score is not None
        )
        baseline_failure_rate = (
            sum(item.status not in {"passed", "cached"} for item in baseline) / count
        )
        candidate_failure_rate = (
            sum(item.status not in {"passed", "cached"} for item in candidate) / count
        )
        baseline_cost = sum(item.cost for item in baseline)
        candidate_cost = sum(item.cost for item in candidate)
        score_delta = candidate_score - baseline_score
        failure_rate_delta = candidate_failure_rate - baseline_failure_rate
        cost_delta = candidate_cost - baseline_cost
        safety_delta = self._mean_dimension(candidate, "safety") - self._mean_dimension(
            baseline, "safety"
        )
        reasons: list[str] = []
        if drift:
            reasons.append("evaluation_condition_drift")
        if critical:
            reasons.append("critical_regression")
        if score_delta < -replay_policy.score_epsilon:
            reasons.append("overall_score_degraded")
        if not replay_policy.allow_failure_rate_increase and failure_rate_delta > 0:
            reasons.append("failure_rate_increased")
        if (
            not replay_policy.allow_safety_degradation
            and safety_delta < -replay_policy.score_epsilon
        ):
            reasons.append("safety_score_degraded")
        if baseline_cost > 0 and candidate_cost > baseline_cost * (
            1 + replay_policy.max_cost_increase_ratio
        ):
            reasons.append("cost_increase_exceeds_policy")
        return ReplayResult(
            proposal_id=proposal.proposal_id,
            baseline_id=baseline_id,
            candidate_id=candidate_id,
            case_count=count,
            improved=improved,
            unchanged=unchanged,
            degraded=degraded,
            critical_regressions=critical,
            score_delta=score_delta,
            failure_rate_delta=failure_rate_delta,
            latency_delta=mean(item.latency_ms for item in candidate)
            - mean(item.latency_ms for item in baseline),
            token_delta=sum(item.tokens for item in candidate)
            - sum(item.tokens for item in baseline),
            cost_delta=cost_delta,
            safety_delta=safety_delta,
            evidence_level=self._evidence_level(candidate),
            drift=drift,
            gate_passed=not reasons,
            gate_reasons=reasons,
        )

    @staticmethod
    def _drift(
        baseline: Sequence[EvaluationRecord], candidate: Sequence[EvaluationRecord]
    ) -> list[str]:
        drift: list[str] = []
        for field in (
            "evidence_level",
            "task_family",
            "course",
            "planner_version",
            "plan_version",
            "skill_versions",
            "tool_versions",
            "model_provider_version",
            "reflection_version",
        ):
            before = {str(getattr(item, field)) for item in baseline}
            after = {str(getattr(item, field)) for item in candidate}
            if before != after:
                drift.append(field)
        return drift

    @staticmethod
    def _safety_regressed(before: EvaluationRecord, after: EvaluationRecord) -> bool:
        return (
            before.score_dimensions.get("safety", 100)
            - after.score_dimensions.get("safety", 100)
            > 0.01
        )

    @staticmethod
    def _mean_dimension(records: Sequence[EvaluationRecord], name: str) -> float:
        values = [
            item.score_dimensions[name]
            for item in records
            if name in item.score_dimensions
        ]
        return mean(values) if values else 100.0

    @staticmethod
    def _evidence_level(records: Sequence[EvaluationRecord]) -> EvidenceLevel:
        levels = {item.evidence_level for item in records}
        if len(levels) == 1:
            return next(iter(levels))
        return "synthetic_provider_free"


class PromotionGovernance:
    """Return a governance decision; it never applies a production mutation."""

    def decide(
        self,
        proposal: ImprovementProposal,
        replay: ReplayResult,
        *,
        reviewer: str = "",
        policy: str = "phase_f_default",
    ) -> PromotionDecision:
        if not replay.gate_passed:
            return PromotionDecision(
                proposal_id=proposal.proposal_id,
                replay_result_id=replay.replay_result_id,
                status="reject",
                evidence_level=replay.evidence_level,
                regression_summary=self._summary(replay),
                risk=proposal.risk,
                approval_reason="replay gate failed; no candidate may be promoted",
                reviewer=reviewer,
                policy=policy,
                rollback_requirement=proposal.rollback_plan,
            )
        if replay.evidence_level == "synthetic_provider_free":
            status: Literal["approve", "reject", "defer", "needs_review"] = (
                "needs_review"
            )
            reason = (
                "synthetic evidence is structurally useful but not production "
                "quality evidence"
            )
        elif proposal.status != "validated":
            status = "needs_review"
            reason = "proposal must reach validated before governance approval"
        else:
            status = "approve"
            reason = (
                "replay passed; approval only permits a governed Experience candidate"
            )
        return PromotionDecision(
            proposal_id=proposal.proposal_id,
            replay_result_id=replay.replay_result_id,
            status=status,
            eligible_targets=["experience_candidate"] if status == "approve" else [],
            evidence_level=replay.evidence_level,
            regression_summary=self._summary(replay),
            risk=proposal.risk,
            approval_reason=reason,
            reviewer=reviewer,
            policy=policy,
            rollback_requirement=proposal.rollback_plan,
        )

    @staticmethod
    def to_experience_candidate(
        proposal: ImprovementProposal,
        pattern: FailurePattern,
        decision: PromotionDecision,
        *,
        experience_type: ExperienceType = ExperienceType.STRATEGY,
    ) -> ExperienceCandidateCreate:
        if decision.status != "approve":
            raise ValueError("only approved governance decisions create candidates")
        course = pattern.dimensions.get("course") or None
        capability = pattern.dimensions.get("capability", "")
        return ExperienceCandidateCreate(
            experience_type=experience_type,
            scope=ExperienceScope.GLOBAL_DEIDENTIFIED,
            course_id=course,
            capability_id=capability,
            planner_version=pattern.dimensions.get("planner_version", ""),
            strategy_summary=proposal.proposed_change,
            failure_stage=pattern.primary_stage.value,
            error_codes=pattern.error_codes,
            verification_result={
                "replay_result_id": decision.replay_result_id,
                "governance_status": decision.status,
            },
            outcome_metrics=proposal.success_metrics,
            evidence_level=ExperienceEvidenceLevel(decision.evidence_level),
            source_trace_ids=[
                ref for ref in pattern.evidence_refs if ref.startswith("trace_")
            ],
            source_eval_ids=[
                ref for ref in pattern.evidence_refs if ref.startswith("eval_")
            ],
            confidence=pattern.reproducible_rate,
            privacy_class=ExperiencePrivacyClass.GLOBAL_DEIDENTIFIED,
            redaction_status=ExperienceRedactionStatus.VERIFIED,
            promotion_provenance={
                "proposal_id": proposal.proposal_id,
                "policy": decision.policy,
                "reviewer": decision.reviewer,
            },
            applicability=[pattern.dimensions.get("task_family", "")],
        )

    @staticmethod
    def _summary(replay: ReplayResult) -> dict[str, Any]:
        return {
            "case_count": replay.case_count,
            "improved": replay.improved,
            "unchanged": replay.unchanged,
            "degraded": replay.degraded,
            "critical_regressions": replay.critical_regressions,
            "score_delta": replay.score_delta,
            "failure_rate_delta": replay.failure_rate_delta,
            "cost_delta": replay.cost_delta,
            "safety_delta": replay.safety_delta,
            "drift": replay.drift,
        }


class EvaluationLoop:
    """Compose the existing report, attribution and pattern services."""

    def analyze(
        self,
        report: SuiteReport,
        cases: Sequence[EvaluationCase] = (),
        *,
        suite_id: str = "",
        baseline_id: str = "",
        candidate_id: str = "",
        expected_case_count: int = 336,
    ) -> tuple[
        list[EvaluationRecord],
        list[FailureRecord],
        list[FailurePattern],
        EvaluationLoopSummary,
    ]:
        records = EvaluationRecordAdapter.from_suite_report(
            report,
            cases,
            suite_id=suite_id,
            baseline_id=baseline_id,
            candidate_id=candidate_id,
        )
        return self.analyze_records(
            records,
            expected_case_count=expected_case_count,
        )

    def analyze_records(
        self,
        records: Sequence[EvaluationRecord],
        *,
        expected_case_count: int = 336,
    ) -> tuple[
        list[EvaluationRecord],
        list[FailureRecord],
        list[FailurePattern],
        EvaluationLoopSummary,
    ]:
        failures = [
            failure
            for record in records
            if (failure := FailureAttributor().attribute(record)) is not None
        ]
        patterns = FailurePatternAggregator().aggregate(failures)
        summary = self._summary(
            records, patterns, expected_case_count=expected_case_count
        )
        return list(records), failures, patterns, summary

    @staticmethod
    def _summary(
        records: Sequence[EvaluationRecord],
        patterns: Sequence[FailurePattern],
        *,
        expected_case_count: int,
    ) -> EvaluationLoopSummary:
        by_course: dict[str, list[EvaluationRecord]] = defaultdict(list)
        by_family: dict[str, list[EvaluationRecord]] = defaultdict(list)
        stage_counts: Counter[str] = Counter()
        attributor = FailureAttributor()
        for record in records:
            by_course[record.course or "unknown"].append(record)
            by_family[record.task_family or "unknown"].append(record)
            failure = attributor.attribute(record)
            if failure is not None:
                stage_counts[failure.stage.value] += 1

        def breakdown(
            groups: dict[str, list[EvaluationRecord]],
        ) -> dict[str, dict[str, float | int]]:
            return {
                name: {
                    "case_count": len(items),
                    "passed": sum(
                        item.status in {"passed", "cached"} for item in items
                    ),
                    "pass_rate": sum(
                        item.status in {"passed", "cached"} for item in items
                    )
                    / len(items),
                    "average_score": mean(
                        item.overall_score
                        for item in items
                        if item.overall_score is not None
                    )
                    if any(item.overall_score is not None for item in items)
                    else 0.0,
                }
                for name, items in sorted(groups.items())
            }

        passed = sum(item.status in {"passed", "cached"} for item in records)
        score_values = [
            item.overall_score for item in records if item.overall_score is not None
        ]
        failure_stages = [
            failure.stage
            for item in records
            if (failure := attributor.attribute(item)) is not None
        ]
        route_planner = sum(
            stage in {LoopFailureStage.ROUTING, LoopFailureStage.PLANNER}
            for stage in failure_stages
        )
        skill_tool = sum(
            stage in {LoopFailureStage.SKILL_SELECTION, LoopFailureStage.TOOL}
            for stage in failure_stages
        )
        generation = sum(
            stage == LoopFailureStage.MODEL_GENERATION for stage in failure_stages
        )
        verification = sum(
            stage in {LoopFailureStage.VERIFICATION, LoopFailureStage.REFLECTION}
            for stage in failure_stages
        )
        suite_id = records[0].suite_id if records else "empty"
        evidence = records[0].evidence_level if records else "synthetic_provider_free"
        return EvaluationLoopSummary(
            suite_id=suite_id,
            evidence_level=evidence,
            case_count=len(records),
            expected_case_count=expected_case_count,
            coverage_status=(
                "complete"
                if len(records) >= expected_case_count
                else "partial"
                if records
                else "empty"
            ),
            passed=passed,
            failed=len(records) - passed,
            overall_score=mean(score_values) if score_values else None,
            course_breakdown=breakdown(by_course),
            task_family_breakdown=breakdown(by_family),
            failure_stage_breakdown=dict(stage_counts),
            route_planner_failures=route_planner,
            skill_tool_failures=skill_tool,
            generation_failures=generation,
            verification_reflection_failures=verification,
            latency_ms={
                "average": mean(item.latency_ms for item in records) if records else 0,
                "max": max((item.latency_ms for item in records), default=0),
            },
            total_tokens=sum(item.tokens for item in records),
            total_cost=sum(item.cost for item in records),
            top_pattern_ids=[
                item.pattern_id
                for item in sorted(
                    patterns,
                    key=lambda pattern: (-pattern.occurrence_count, pattern.pattern_id),
                )[:10]
            ],
            historical_failures_included=any(
                item.evidence_level == "offline_real_case" for item in records
            ),
            real_provider_evidence_included=any(
                item.evidence_level
                in {"real_provider_test", "controlled_canary", "production"}
                for item in records
            ),
        )


__all__ = [
    "EvaluationLoop",
    "EvaluationLoopSummary",
    "EvaluationRecord",
    "EvaluationRecordAdapter",
    "FailureAttribution",
    "FailureAttributor",
    "FailurePattern",
    "FailurePatternAggregator",
    "FailureRecord",
    "ImprovementProposal",
    "ImprovementProposalService",
    "LoopFailureStage",
    "OfflineReplayService",
    "PromotionDecision",
    "PromotionGovernance",
    "ReplayPolicy",
    "ReplayResult",
]
