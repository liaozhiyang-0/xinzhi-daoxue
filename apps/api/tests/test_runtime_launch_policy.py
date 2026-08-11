from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.contracts import AgentRequest, Intent, Scene, UserRole
from app.runtime import (
    RuntimeCanaryEvidence,
    RuntimeCanaryReport,
    RuntimeCanaryThresholds,
)
from app.runtime.semantic_evidence import (
    RuntimeSemanticDimensions,
    RuntimeSemanticEvidence,
)
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from app.services.runtime_launch_policy import (
    RuntimeLaunchMode,
    RuntimeLaunchPolicy,
)
from app.services.runtime_release_authorization import (
    RuntimeReleaseAuthorization,
    RuntimeReleaseAuthorizationRegistry,
)

AGENT_VERSION = "1.0"
RUNTIME_PLAN_VERSION = "general-qa-v1"


def _passing_semantic_evidence() -> RuntimeSemanticEvidence:
    return RuntimeSemanticEvidence(
        suite_id="general-canary",
        case_id="general-case",
        agent_id="GENERAL_QUESTION_V1",
        agent_version=AGENT_VERSION,
        runtime_plan_version=RUNTIME_PLAN_VERSION,
        input_sha256="0" * 64,
        legacy_output_sha256="1" * 64,
        runtime_output_sha256="2" * 64,
        dimensions=RuntimeSemanticDimensions(
            task_fulfillment=1.0,
            factual_correctness=1.0,
            safety=1.0,
        ),
        decision="pass",
        judge_type="human",
        rubric_version="general-question-v1",
        reviewer_ref="review-123",
        reviewed_at=datetime(2026, 8, 9, tzinfo=UTC),
        redaction_status="redacted",
        authorization_ref="change-123",
    )


def _request(options: dict[str, object] | None = None) -> AgentRequest:
    return AgentRequest(
        task_id="launch-policy-task",
        session_id="launch-policy-session",
        user_id="test-user",
        user_role=UserRole.STUDENT,
        scene=Scene.LEARNING,
        course_id="CT",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": "test"},
        options=options or {},
    )


def _matching_release_authorization(
    launch_mode: str,
) -> RuntimeReleaseAuthorizationRegistry:
    return RuntimeReleaseAuthorizationRegistry(
        {
            "GENERAL_QUESTION_V1": RuntimeReleaseAuthorization(
                agent_id="GENERAL_QUESTION_V1",
                suite_id="general-canary",
                agent_version=AGENT_VERSION,
                runtime_plan_version=RUNTIME_PLAN_VERSION,
                launch_mode=launch_mode,  # type: ignore[arg-type]
                authorization_ref="release-auth-123",
                approver_ref="release-reviewer-123",
                approved_at=datetime(2026, 8, 9, tzinfo=UTC),
            )
        }
    )


def test_configured_default_mode_requires_runtime_and_enables_lifecycle() -> None:
    policy = RuntimeLaunchPolicy("GENERAL_QUESTION_V1=default")

    decision = policy.resolve(
        "GENERAL_QUESTION_V1",
        _request(),
        lifecycle_enabled=True,
    )

    assert decision.mode == RuntimeLaunchMode.DEFAULT
    assert decision.should_execute is True
    assert decision.requires_runtime is True
    assert policy.lifecycle_enabled(False) is True


def test_explicit_opt_out_overrides_configured_default() -> None:
    policy = RuntimeLaunchPolicy("GENERAL_QUESTION_V1=default")

    decision = policy.resolve(
        "GENERAL_QUESTION_V1",
        _request({"general_question_runtime": {"execute": False}}),
        lifecycle_enabled=True,
    )

    assert decision.mode == RuntimeLaunchMode.LEGACY
    assert decision.source == "explicit_opt_out"


def test_explicit_opt_in_canary_works_without_agent_allowlist() -> None:
    policy = RuntimeLaunchPolicy()

    decision = policy.resolve(
        "GENERAL_QUESTION_V1",
        _request({"general_question_runtime": {"execute": True}}),
        lifecycle_enabled=True,
    )

    assert decision.mode == RuntimeLaunchMode.CANARY
    assert decision.explicit_opt_in is True


def test_explicit_opt_in_cannot_bypass_required_release_gate() -> None:
    policy = RuntimeLaunchPolicy(
        release_registry=RuntimeCanaryReleaseRegistry(),
        release_gate_required=True,
    )

    decision = policy.resolve(
        "GENERAL_QUESTION_V1",
        _request({"general_question_runtime": {"execute": True}}),
        lifecycle_enabled=True,
        expected_agent_version=AGENT_VERSION,
        expected_runtime_plan_version=RUNTIME_PLAN_VERSION,
    )

    assert decision.mode == RuntimeLaunchMode.LEGACY
    assert decision.source == "canary_release_gate"
    assert decision.reason == "canary_release_evidence_missing"


def test_configured_runtime_mode_fails_closed_without_canary_artifact() -> None:
    policy = RuntimeLaunchPolicy(
        "GENERAL_QUESTION_V1=canary",
        release_gate_required=True,
    )

    decision = policy.resolve(
        "GENERAL_QUESTION_V1",
        _request(),
        lifecycle_enabled=True,
        expected_agent_version=AGENT_VERSION,
        expected_runtime_plan_version=RUNTIME_PLAN_VERSION,
    )

    assert decision.mode == RuntimeLaunchMode.LEGACY
    assert decision.source == "canary_release_gate"
    assert decision.reason == "canary_release_evidence_missing"


def test_configured_runtime_mode_fails_closed_without_version_expectations() -> None:
    policy = RuntimeLaunchPolicy(
        "GENERAL_QUESTION_V1=default",
        release_registry=RuntimeCanaryReleaseRegistry(),
        release_gate_required=True,
    )

    decision = policy.resolve(
        "GENERAL_QUESTION_V1",
        _request(),
        lifecycle_enabled=True,
    )

    assert decision.mode == RuntimeLaunchMode.LEGACY
    assert decision.reason == "canary_artifact_version_expectation_missing"


@pytest.mark.parametrize(
    ("launch_mode", "expected_mode"),
    [
        (RuntimeLaunchMode.CANARY.value, RuntimeLaunchMode.CANARY),
        (RuntimeLaunchMode.DEFAULT.value, RuntimeLaunchMode.DEFAULT),
    ],
)
def test_configured_runtime_mode_accepts_matching_release_artifact(
    launch_mode: str,
    expected_mode: RuntimeLaunchMode,
) -> None:
    registry = RuntimeCanaryReleaseRegistry(
        {
            "GENERAL_QUESTION_V1": RuntimeCanaryReport(
                suite_id="general-canary",
                suite_version="1",
                canary_eligible=True,
                release_eligible=True,
                thresholds=RuntimeCanaryThresholds(),
                evidence=RuntimeCanaryEvidence(
                    kind="authorized_paired",
                    agent_id="GENERAL_QUESTION_V1",
                    agent_version=AGENT_VERSION,
                    runtime_plan_version=RUNTIME_PLAN_VERSION,
                    authorization_ref="change-123",
                    captured_at=datetime(2026, 8, 9, tzinfo=UTC),
                    redaction_status="redacted",
                ),
            )
        },
        semantic_evidence={"GENERAL_QUESTION_V1": _passing_semantic_evidence()},
    )
    policy = RuntimeLaunchPolicy(
        f"GENERAL_QUESTION_V1={launch_mode}",
        release_registry=registry,
        release_authorization_registry=_matching_release_authorization(
            launch_mode
        ),
        release_gate_required=True,
    )

    decision = policy.resolve(
        "GENERAL_QUESTION_V1",
        _request(),
        lifecycle_enabled=True,
        expected_agent_version=AGENT_VERSION,
        expected_runtime_plan_version=RUNTIME_PLAN_VERSION,
    )

    assert decision.mode == expected_mode


def test_configured_runtime_mode_requires_authorization_registry() -> None:
    registry = RuntimeCanaryReleaseRegistry(
        {
            "GENERAL_QUESTION_V1": RuntimeCanaryReport(
                suite_id="general-canary",
                suite_version="1",
                canary_eligible=True,
                release_eligible=True,
                thresholds=RuntimeCanaryThresholds(),
                evidence=RuntimeCanaryEvidence(
                    kind="authorized_paired",
                    agent_id="GENERAL_QUESTION_V1",
                    agent_version=AGENT_VERSION,
                    runtime_plan_version=RUNTIME_PLAN_VERSION,
                    authorization_ref="change-123",
                    captured_at=datetime(2026, 8, 9, tzinfo=UTC),
                    redaction_status="redacted",
                ),
            )
        },
        semantic_evidence={
            "GENERAL_QUESTION_V1": _passing_semantic_evidence()
        },
    )
    policy = RuntimeLaunchPolicy(
        "GENERAL_QUESTION_V1=canary",
        release_registry=registry,
        release_gate_required=True,
    )

    decision = policy.resolve(
        "GENERAL_QUESTION_V1",
        _request(),
        lifecycle_enabled=True,
        expected_agent_version=AGENT_VERSION,
        expected_runtime_plan_version=RUNTIME_PLAN_VERSION,
    )

    assert decision.mode == RuntimeLaunchMode.LEGACY
    assert decision.source == "canary_release_gate"
    assert decision.reason == "release_authorization_missing"


@pytest.mark.parametrize(
    ("artifact_agent_version", "artifact_plan_version", "reason"),
    [
        (
            "0.9",
            RUNTIME_PLAN_VERSION,
            "canary_artifact_agent_version_mismatch",
        ),
        (
            AGENT_VERSION,
            "general-qa-v0",
            "canary_artifact_runtime_plan_version_mismatch",
        ),
    ],
)
def test_configured_runtime_mode_fails_closed_for_stale_release_artifact(
    artifact_agent_version: str,
    artifact_plan_version: str,
    reason: str,
) -> None:
    registry = RuntimeCanaryReleaseRegistry(
        {
            "GENERAL_QUESTION_V1": RuntimeCanaryReport(
                suite_id="general-canary",
                suite_version="1",
                canary_eligible=True,
                release_eligible=True,
                thresholds=RuntimeCanaryThresholds(),
                evidence=RuntimeCanaryEvidence(
                    kind="authorized_paired",
                    agent_id="GENERAL_QUESTION_V1",
                    agent_version=artifact_agent_version,
                    runtime_plan_version=artifact_plan_version,
                    authorization_ref="change-123",
                    captured_at=datetime(2026, 8, 9, tzinfo=UTC),
                    redaction_status="redacted",
                ),
            )
        }
    )
    policy = RuntimeLaunchPolicy(
        "GENERAL_QUESTION_V1=default",
        release_registry=registry,
        release_gate_required=True,
    )

    decision = policy.resolve(
        "GENERAL_QUESTION_V1",
        _request(),
        lifecycle_enabled=True,
        expected_agent_version=AGENT_VERSION,
        expected_runtime_plan_version=RUNTIME_PLAN_VERSION,
    )

    assert decision.mode == RuntimeLaunchMode.LEGACY
    assert decision.source == "canary_release_gate"
    assert decision.reason == reason


def test_business_execute_flag_does_not_disable_runtime_launch() -> None:
    policy = RuntimeLaunchPolicy()

    decision = policy.resolve(
        "RESEARCH_03_DATA_ANALYSIS_V1",
        _request({"research_analysis_v2": {"execute": False}}),
        lifecycle_enabled=True,
        runtime_option_key="research_analysis_v2",
    )

    assert decision.mode == RuntimeLaunchMode.CANARY
    assert decision.explicit_opt_in is True


def test_launch_decision_round_trips_through_runtime_snapshot() -> None:
    policy = RuntimeLaunchPolicy("GENERAL_QUESTION_V1=default")
    decision = policy.resolve(
        "GENERAL_QUESTION_V1",
        _request(),
        lifecycle_enabled=True,
    )

    round_tripped = type(decision).from_snapshot(decision.to_snapshot())

    assert round_tripped == decision


def test_invalid_launch_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid Runtime launch mode"):
        RuntimeLaunchPolicy("GENERAL_QUESTION_V1=experimental")
