from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReflectionEvidenceLevel = Literal[
    "synthetic_provider_free",
    "offline_real_case",
    "real_provider_test",
    "controlled_canary",
    "production",
]
ReflectionEvaluationDecision = Literal["GO", "CONDITIONAL_GO", "NO_GO"]


class ReflectionEvaluationObservation(BaseModel):
    """Auditable observation emitted by one reflection evaluation case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=120)
    capability: Literal["academic_solver", "knowledge", "research", "teaching"]
    evidence_level: ReflectionEvidenceLevel
    critic_status: Literal["pass", "revise", "fail", "needs_review", "not_run"]
    labeled_issue: bool = False
    issue_detected: bool = False
    unsupported_critique: bool = False
    revision_attempted: bool = False
    revision_status: Literal["verified", "no_change", "failed", "not_run"] = "not_run"
    improved: bool = False
    degraded: bool = False
    new_error_introduced: bool = False
    verification_before: Literal["pass", "fail", "unknown"] = "unknown"
    verification_after: Literal["pass", "fail", "unknown"] = "unknown"
    critic_latency_ms: int = Field(default=0, ge=0)
    critic_tokens: int = Field(default=0, ge=0)
    revision_latency_ms: int = Field(default=0, ge=0)
    revision_tokens: int = Field(default=0, ge=0)
    checkpoint_resume_ok: bool = True
    rollback_ok: bool = True
    event_order_ok: bool = True
    duplicate_side_effects: int = Field(default=0, ge=0)


class ReflectionEvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["reflection_evaluation.v1"] = "reflection_evaluation.v1"
    evidence_level: ReflectionEvidenceLevel
    decision: ReflectionEvaluationDecision
    observations: list[ReflectionEvaluationObservation] = Field(default_factory=list)
    metrics: dict[str, int | float | bool] = Field(default_factory=dict)
    provider_free: bool
    improvement_evidence: bool
    rollback_integrity: bool


class ReflectionCanaryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    allowlist: list[str] = Field(default_factory=list, max_length=32)
    rollback_enabled: bool = True
    automatic_expansion: bool = False


class ReflectionCanaryDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["disabled", "approved", "rejected", "rolled_back"]
    capabilities: list[str] = Field(default_factory=list, max_length=16)
    reason_codes: list[str] = Field(default_factory=list, max_length=16)
    rollback_integrity: bool = True


class ReflectionControlledCanary:
    """Policy-only gate; it never changes Runtime or task state."""

    def decide(
        self,
        report: ReflectionEvaluationReport,
        capabilities: Sequence[str],
        config: ReflectionCanaryConfig | None = None,
    ) -> ReflectionCanaryDecision:
        policy = config or ReflectionCanaryConfig()
        selected = list(
            dict.fromkeys(str(item).strip() for item in capabilities if item)
        )
        if not policy.enabled:
            return ReflectionCanaryDecision(
                status="disabled",
                capabilities=selected,
                reason_codes=["canary_default_off"],
            )
        reasons: list[str] = []
        if report.decision != "GO":
            reasons.append("evaluation_not_go")
        if not policy.rollback_enabled:
            reasons.append("rollback_not_configured")
        if policy.automatic_expansion:
            reasons.append("automatic_expansion_forbidden")
        if not selected:
            reasons.append("canary_allowlist_empty")
        if not set(selected).issubset(set(policy.allowlist)):
            reasons.append("capability_not_allowlisted")
        if reasons:
            return ReflectionCanaryDecision(
                status="rejected",
                capabilities=selected,
                reason_codes=list(dict.fromkeys(reasons)),
            )
        return ReflectionCanaryDecision(status="approved", capabilities=selected)

    def rollback(
        self, decision: ReflectionCanaryDecision
    ) -> ReflectionCanaryDecision:
        return decision.model_copy(
            update={
                "status": "rolled_back",
                "capabilities": [],
                "reason_codes": [*decision.reason_codes, "manual_rollback"],
                "rollback_integrity": True,
            }
        )


class ReflectionEvaluationService:
    """Score Critic/revision observations without claiming provider quality."""

    def evaluate(
        self,
        observations: Sequence[ReflectionEvaluationObservation],
        *,
        evidence_level: ReflectionEvidenceLevel | None = None,
    ) -> ReflectionEvaluationReport:
        if not observations:
            raise ValueError("reflection evaluation requires at least one observation")
        levels = {item.evidence_level for item in observations}
        if evidence_level is not None:
            levels.add(evidence_level)
        if len(levels) != 1:
            raise ValueError("one report must contain one evidence level")
        level = next(iter(levels))
        metrics = self._metrics(observations)
        improvement = any(item.improved for item in observations)
        safe = (
            metrics["critical_deterministic_regressions"] == 0
            and metrics["duplicate_side_effects"] == 0
            and metrics["unsupported_critique_rate"] <= 0.05
            and metrics["revision_degradation_rate"] <= 0.02
            and bool(metrics["checkpoint_resume_ok"])
            and bool(metrics["event_order_ok"])
            and bool(metrics["rollback_integrity"])
        )
        decision: ReflectionEvaluationDecision
        if not safe or not improvement:
            decision = "NO_GO"
        elif level == "synthetic_provider_free":
            decision = "CONDITIONAL_GO"
        else:
            decision = "GO"
        return ReflectionEvaluationReport(
            evidence_level=level,
            decision=decision,
            observations=list(observations),
            metrics=metrics,
            provider_free=level == "synthetic_provider_free",
            improvement_evidence=improvement,
            rollback_integrity=bool(metrics["rollback_integrity"]),
        )

    @staticmethod
    def _metrics(
        observations: Sequence[ReflectionEvaluationObservation],
    ) -> dict[str, int | float | bool]:
        total = len(observations)
        predicted = sum(item.issue_detected for item in observations)
        actual = sum(item.labeled_issue for item in observations)
        true_positive = sum(
            item.issue_detected and item.labeled_issue for item in observations
        )
        revisions = [item for item in observations if item.revision_attempted]
        return {
            "case_count": total,
            "critic_issue_precision": true_positive / predicted if predicted else 0.0,
            "critic_issue_recall": true_positive / actual if actual else 0.0,
            "critic_false_positive_rate": (
                sum(
                    item.issue_detected and not item.labeled_issue
                    for item in observations
                )
                / max(1, total - actual)
            ),
            "unsupported_critique_rate": sum(
                item.unsupported_critique for item in observations
            )
            / total,
            "critic_verifier_disagreement_count": sum(
                item.critic_status in {"revise", "fail"}
                and item.verification_before == "pass"
                for item in observations
            ),
            "revision_attempt_rate": len(revisions) / total,
            "revision_success_rate": sum(
                item.revision_status == "verified" for item in revisions
            )
            / max(1, len(revisions)),
            "revision_improvement_rate": sum(item.improved for item in revisions)
            / max(1, len(revisions)),
            "revision_no_change_rate": sum(
                item.revision_status == "no_change" for item in revisions
            )
            / max(1, len(revisions)),
            "revision_degradation_rate": sum(item.degraded for item in revisions)
            / max(1, len(revisions)),
            "new_error_introduction_rate": sum(
                item.new_error_introduced for item in revisions
            )
            / max(1, len(revisions)),
            "verification_pass_before": sum(
                item.verification_before == "pass" for item in observations
            ),
            "verification_pass_after": sum(
                item.verification_after == "pass" for item in observations
            ),
            "added_latency_ms": sum(
                item.critic_latency_ms + item.revision_latency_ms
                for item in observations
            ),
            "critic_tokens": sum(item.critic_tokens for item in observations),
            "revision_tokens": sum(item.revision_tokens for item in observations),
            "critical_deterministic_regressions": sum(
                item.new_error_introduced and item.verification_after == "fail"
                for item in observations
            ),
            "duplicate_side_effects": sum(
                item.duplicate_side_effects for item in observations
            ),
            "checkpoint_resume_ok": all(
                item.checkpoint_resume_ok for item in observations
            ),
            "event_order_ok": all(item.event_order_ok for item in observations),
            "rollback_integrity": all(item.rollback_ok for item in observations),
        }
