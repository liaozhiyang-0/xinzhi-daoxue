from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

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
from app.services.runtime_launch_policy import RuntimeLaunchMode, RuntimeLaunchPolicy
from app.services.runtime_release_authorization import (
    RuntimeReleaseAuthorizationRegistry,
)

AGENT_ID = "GENERAL_QUESTION_V1"
AGENT_VERSION = "1.0"
PLAN_VERSION = "general-qa-v1"
SUITE_ID = "general-canary"


def _release_registry() -> RuntimeCanaryReleaseRegistry:
    report = RuntimeCanaryReport(
        suite_id=SUITE_ID,
        suite_version="1",
        canary_eligible=True,
        release_eligible=True,
        thresholds=RuntimeCanaryThresholds(),
        evidence=RuntimeCanaryEvidence(
            kind="authorized_paired",
            agent_id=AGENT_ID,
            agent_version=AGENT_VERSION,
            runtime_plan_version=PLAN_VERSION,
            authorization_ref="structural-auth",
            captured_at=datetime(2026, 8, 11, tzinfo=UTC),
            redaction_status="redacted",
        ),
    )
    semantic = RuntimeSemanticEvidence(
        suite_id=SUITE_ID,
        case_id="general-case",
        agent_id=AGENT_ID,
        agent_version=AGENT_VERSION,
        runtime_plan_version=PLAN_VERSION,
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
        reviewed_at=datetime(2026, 8, 11, tzinfo=UTC),
        redaction_status="redacted",
        authorization_ref="semantic-auth",
    )
    return RuntimeCanaryReleaseRegistry(
        {AGENT_ID: report}, semantic_evidence={AGENT_ID: semantic}
    )


def _request() -> AgentRequest:
    return AgentRequest(
        task_id="release-auth-task",
        session_id="release-auth-session",
        user_id="release-auth-user",
        user_role=UserRole.STUDENT,
        scene=Scene.LEARNING,
        course_id="CT",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": "test"},
        options={"general_question_runtime": {"execute": True}},
    )


def _authorization_file(
    path: Path,
    *,
    launch_mode: str = "canary",
    agent_version: str = AGENT_VERSION,
    plan_version: str = PLAN_VERSION,
    status: str = "approved",
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "runtime_release_authorization.v1",
                "agent_id": AGENT_ID,
                "suite_id": SUITE_ID,
                "agent_version": agent_version,
                "runtime_plan_version": plan_version,
                "launch_mode": launch_mode,
                "authorization_ref": "release-auth-123",
                "approver_ref": "release-reviewer-123",
                "approved_at": "2026-08-11T00:00:00+00:00",
                "status": status,
            }
        ),
        encoding="utf-8",
    )


def test_empty_authorization_registry_fails_closed() -> None:
    registry = RuntimeReleaseAuthorizationRegistry()

    assert (
        registry.reason(
            AGENT_ID,
            suite_id=SUITE_ID,
            launch_mode="canary",
            expected_agent_version=AGENT_VERSION,
            expected_runtime_plan_version=PLAN_VERSION,
        )
        == "release_authorization_missing"
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("launch_mode", "default", "release_authorization_launch_mode_mismatch"),
        (
            "agent_version",
            "0.9",
            "release_authorization_agent_version_mismatch",
        ),
        (
            "runtime_plan_version",
            "general-qa-v0",
            "release_authorization_runtime_plan_version_mismatch",
        ),
        ("status", "revoked", "release_authorization_revoked"),
    ],
)
def test_authorization_is_bound_to_release_identity(
    tmp_path: Path, field: str, value: str, reason: str
) -> None:
    path = tmp_path / "release.json"
    overrides = {field: value}
    if field == "runtime_plan_version":
        overrides = {"plan_version": value}
    _authorization_file(path, **overrides)
    registry = RuntimeReleaseAuthorizationRegistry.from_paths(
        f"{AGENT_ID}={path}"
    )

    assert (
        registry.reason(
            AGENT_ID,
            suite_id=SUITE_ID,
            launch_mode="canary",
            expected_agent_version=AGENT_VERSION,
            expected_runtime_plan_version=PLAN_VERSION,
        )
        == reason
    )


def test_launch_policy_requires_and_accepts_explicit_authorization(
    tmp_path: Path,
) -> None:
    path = tmp_path / "release.json"
    _authorization_file(path)
    authorization = RuntimeReleaseAuthorizationRegistry.from_paths(
        f"{AGENT_ID}={path}"
    )
    policy = RuntimeLaunchPolicy(
        f"{AGENT_ID}=canary",
        release_registry=_release_registry(),
        release_authorization_registry=authorization,
        release_gate_required=True,
    )

    decision = policy.resolve(
        AGENT_ID,
        _request(),
        lifecycle_enabled=True,
        runtime_option_key="general_question_runtime",
        expected_agent_version=AGENT_VERSION,
        expected_runtime_plan_version=PLAN_VERSION,
    )

    assert decision.mode == RuntimeLaunchMode.CANARY
    assert decision.source == "configured_launch_mode"


def test_launch_policy_rejects_missing_explicit_authorization() -> None:
    policy = RuntimeLaunchPolicy(
        f"{AGENT_ID}=canary",
        release_registry=_release_registry(),
        release_authorization_registry=RuntimeReleaseAuthorizationRegistry(),
        release_gate_required=True,
    )

    decision = policy.resolve(
        AGENT_ID,
        _request(),
        lifecycle_enabled=True,
        runtime_option_key="general_question_runtime",
        expected_agent_version=AGENT_VERSION,
        expected_runtime_plan_version=PLAN_VERSION,
    )

    assert decision.mode == RuntimeLaunchMode.LEGACY
    assert decision.source == "canary_release_gate"
    assert decision.reason == "release_authorization_missing"
