from __future__ import annotations

from typing import Any

from app.services.reflection_evaluation import (
    ReflectionCanaryConfig,
    ReflectionControlledCanary,
    ReflectionEvaluationObservation,
    ReflectionEvaluationService,
)


def _case(
    case_id: str, capability: str, **kwargs: object
) -> ReflectionEvaluationObservation:
    evidence_level = str(kwargs.pop("evidence_level", "synthetic_provider_free"))
    payload: dict[str, Any] = {
        "case_id": case_id,
        "capability": capability,
        "evidence_level": evidence_level,
        "critic_status": "pass",
        **kwargs,
    }
    return ReflectionEvaluationObservation.model_validate(payload)


def test_evaluation_scores_detection_revision_cost_and_stability() -> None:
    observations = [
        _case(
            "ct-numeric-error",
            "academic_solver",
            critic_status="revise",
            labeled_issue=True,
            issue_detected=True,
            revision_attempted=True,
            revision_status="verified",
            improved=True,
            verification_before="fail",
            verification_after="pass",
            critic_latency_ms=100,
            critic_tokens=40,
            revision_latency_ms=120,
            revision_tokens=60,
        ),
        _case(
            "ct-derivation-gap",
            "academic_solver",
            critic_status="revise",
            labeled_issue=True,
            issue_detected=True,
            revision_attempted=True,
            revision_status="no_change",
            verification_before="fail",
            verification_after="fail",
        ),
        _case(
            "ct-correct-answer",
            "academic_solver",
            critic_status="pass",
            labeled_issue=False,
            issue_detected=False,
            verification_before="pass",
            verification_after="pass",
        ),
        _case(
            "knowledge-supported",
            "knowledge",
            critic_status="pass",
            verification_before="pass",
            verification_after="pass",
        ),
        _case(
            "knowledge-insufficient",
            "knowledge",
            critic_status="needs_review",
            labeled_issue=True,
            issue_detected=True,
            verification_before="fail",
            verification_after="fail",
        ),
        _case(
            "research-unsupported-claim",
            "research",
            critic_status="revise",
            labeled_issue=True,
            issue_detected=True,
            revision_attempted=True,
            revision_status="verified",
            improved=True,
            verification_before="fail",
            verification_after="pass",
        ),
        _case(
            "teaching-style-difference",
            "teaching",
            critic_status="pass",
            verification_before="pass",
            verification_after="pass",
            checkpoint_resume_ok=True,
        ),
        _case(
            "critic-timeout-revision-failure",
            "research",
            critic_status="fail",
            revision_attempted=True,
            revision_status="failed",
            verification_before="fail",
            verification_after="fail",
            checkpoint_resume_ok=True,
        ),
    ]
    report = ReflectionEvaluationService().evaluate(observations)
    assert report.decision == "CONDITIONAL_GO"
    assert report.provider_free is True
    assert report.improvement_evidence is True
    assert report.metrics["critic_issue_recall"] == 1.0
    assert report.metrics["revision_improvement_rate"] > 0
    assert report.metrics["duplicate_side_effects"] == 0
    assert report.metrics["checkpoint_resume_ok"] is True


def test_unsupported_critique_or_degradation_is_no_go() -> None:
    observation = _case(
        "bad-revision",
        "academic_solver",
        critic_status="revise",
        labeled_issue=True,
        issue_detected=True,
        unsupported_critique=True,
        revision_attempted=True,
        revision_status="verified",
        degraded=True,
        new_error_introduced=True,
        verification_before="pass",
        verification_after="fail",
    )
    report = ReflectionEvaluationService().evaluate([observation])
    assert report.decision == "NO_GO"
    assert report.metrics["unsupported_critique_rate"] == 1.0
    assert report.metrics["revision_degradation_rate"] == 1.0


def test_canary_is_default_off_allowlisted_and_rollback_safe() -> None:
    observation = _case(
        "real-case",
        "academic_solver",
        critic_status="revise",
        labeled_issue=True,
        issue_detected=True,
        revision_attempted=True,
        revision_status="verified",
        improved=True,
        verification_before="fail",
        verification_after="pass",
        evidence_level="real_provider_test",
    )
    report = ReflectionEvaluationService().evaluate([observation])
    canary = ReflectionControlledCanary()
    disabled = canary.decide(report, ["academic_solver"])
    assert disabled.status == "disabled"

    approved = canary.decide(
        report,
        ["academic_solver"],
        ReflectionCanaryConfig(
            enabled=True,
            allowlist=["academic_solver"],
            rollback_enabled=True,
            automatic_expansion=False,
        ),
    )
    assert approved.status == "approved"
    rolled_back = canary.rollback(approved)
    assert rolled_back.status == "rolled_back"
    assert rolled_back.capabilities == []
    assert rolled_back.rollback_integrity is True
