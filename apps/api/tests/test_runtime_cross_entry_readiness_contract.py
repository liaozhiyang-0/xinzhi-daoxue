from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest
from app.agents import AgentRegistry
from app.runtime import (
    RuntimeCanaryEvidence,
    RuntimeCanaryReport,
    RuntimeCanaryThresholds,
    RuntimeHandlerRegistry,
)
from app.services.runtime_agent_readiness import RuntimeAgentReadinessService
from app.services.runtime_business_registry import RuntimeBusinessRegistry
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from app.services.runtime_launch_policy import RuntimeLaunchPolicy


class _FakeAgentRuntimeService:
    agent_id = "GENERAL_QUESTION_V1"
    runtime_option_key = "general_question_runtime"
    runtime_plan_version = "general-qa-v1"
    enabled = True


class _FakeLearningLoopRuntime:
    """A LearningLoop-only runtime; it is not an AgentRequest service."""

    agent_id = "LEARNING_PROGRESS_V1"
    run_kind = "learning_progress"
    plan_version = "learning-progress-v1"
    enabled = True


def _readiness(
    services: list[object],
    *,
    launch_modes: str = "",
    release_registry: RuntimeCanaryReleaseRegistry | None = None,
) -> RuntimeAgentReadinessService:
    release = release_registry or RuntimeCanaryReleaseRegistry()
    return RuntimeAgentReadinessService(
        AgentRegistry(),
        RuntimeBusinessRegistry(services),  # type: ignore[arg-type]
        RuntimeLaunchPolicy(
            launch_modes,
            release_registry=release,
            release_gate_required=True,
        ),
        lifecycle_enabled=True,
        release_registry=release,
        handler_registry=RuntimeHandlerRegistry(),
    )


def _release_without_semantic_evidence() -> RuntimeCanaryReleaseRegistry:
    return RuntimeCanaryReleaseRegistry(
        {
            "GENERAL_QUESTION_V1": RuntimeCanaryReport(
                suite_id="contract-suite",
                suite_version="1",
                canary_eligible=True,
                release_eligible=True,
                thresholds=RuntimeCanaryThresholds(),
                evidence=RuntimeCanaryEvidence(
                    kind="authorized_paired",
                    agent_id="GENERAL_QUESTION_V1",
                    agent_version="1.0",
                    runtime_plan_version="general-qa-v1",
                    authorization_ref="contract-test",
                    captured_at=datetime(2026, 8, 9, tzinfo=UTC),
                    redaction_status="redacted",
                ),
            )
        },
        semantic_evidence={},
    )


def _assert_safe(values: tuple[str, ...]) -> None:
    action_id = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    forbidden = ("/", "\\", "password", "secret", "token", "credential")
    assert all(action_id.fullmatch(value) for value in values)
    text = " ".join(values).lower()
    assert not any(fragment in text for fragment in forbidden)


def test_formal_readiness_is_enumerated_only_from_agent_registry() -> None:
    learning_loop = _FakeLearningLoopRuntime()
    readiness = _readiness([learning_loop])

    formal_ids = {definition.agent_id for definition in AgentRegistry().list_agents()}
    reported_ids = {item.agent_id for item in readiness.list_all()}

    assert reported_ids == formal_ids
    assert learning_loop.agent_id not in reported_ids
    assert all(item.agent_id in formal_ids for item in readiness.list_all())


def test_learning_loop_runtime_is_not_an_agent_request_service() -> None:
    learning_loop = _FakeLearningLoopRuntime()
    business = RuntimeBusinessRegistry([learning_loop])  # type: ignore[arg-type]
    readiness = _readiness([learning_loop])

    assert business.services() == (learning_loop,)
    assert readiness.inspect("GENERAL_QUESTION_V1").runtime_plan_available is False
    assert readiness.inspect("GENERAL_QUESTION_V1").status == "legacy_only"
    assert "runtime_service_missing" in readiness.inspect(
        "GENERAL_QUESTION_V1"
    ).blockers


def test_missing_release_evidence_fails_closed_without_provider_access() -> None:
    item = _readiness(
        [_FakeAgentRuntimeService()],
        launch_modes="GENERAL_QUESTION_V1=default",
    ).inspect("GENERAL_QUESTION_V1")

    assert item.status == "blocked"
    assert item.effective_launch_mode == "legacy"
    assert item.canary_release_eligible is False
    assert item.blockers == ("canary_release_evidence_missing",)
    assert item.recommended_actions == (
        "run_provider_free_release_preflight",
        "collect_authorized_paired_trace",
    )
    _assert_safe(item.blockers)
    _assert_safe(item.recommended_actions)


def test_missing_semantic_evidence_fails_closed_and_outputs_safe_identifiers() -> None:
    item = _readiness(
        [_FakeAgentRuntimeService()],
        launch_modes="GENERAL_QUESTION_V1=default",
        release_registry=_release_without_semantic_evidence(),
    ).inspect("GENERAL_QUESTION_V1")

    assert item.status == "blocked"
    assert item.effective_launch_mode == "legacy"
    assert item.canary_release_eligible is False
    assert item.blockers == ("semantic_evidence_missing",)
    _assert_safe(item.blockers)
    _assert_safe(item.recommended_actions)
    assert "contract-test" not in " ".join(item.blockers + item.recommended_actions)
    assert not any("/" in value or "\\" in value for value in item.blockers)


@pytest.mark.parametrize("field", ["blockers", "recommended_actions"])
def test_readiness_public_contract_contains_no_raw_request_or_secret_data(
    field: str,
) -> None:
    item = _readiness([_FakeAgentRuntimeService()]).inspect("GENERAL_QUESTION_V1")
    values = getattr(item, field)

    _assert_safe(values)
    assert "runtime-readiness" not in " ".join(values)
