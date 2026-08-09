from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from app.agents import AgentRegistry
from app.runtime import (
    AgentRun,
    RuntimeCanaryEvidence,
    RuntimeCanaryReport,
    RuntimeCanaryThresholds,
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeNode,
    RuntimeObservation,
)
from app.services.runtime_agent_readiness import RuntimeAgentReadinessService
from app.services.runtime_business_registry import RuntimeBusinessRegistry
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from app.services.runtime_launch_policy import RuntimeLaunchPolicy


class _RuntimeService:
    agent_id = "GENERAL_QUESTION_V1"
    runtime_option_key = "general_question_runtime"
    runtime_plan_version = "general-qa-v1"

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled


class _GoalService:
    agent_id = "*"
    runtime_option_key = "runtime_goal_runtime"


class _LegacyPlanVersionService:
    agent_id = "GENERAL_QUESTION_V1"
    runtime_option_key = "general_question_runtime"
    plan_version = "general-qa-v1"


class _UnversionedRuntimeService:
    agent_id = "GENERAL_QUESTION_V1"
    runtime_option_key = "general_question_runtime"

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled


def _readiness(
    services: list[object],
    *,
    agent_registry: AgentRegistry | None = None,
    launch_modes: str = "",
    release_gate_required: bool = False,
    handler_registry: RuntimeHandlerRegistry | None = None,
    release_registry: RuntimeCanaryReleaseRegistry | None = None,
) -> RuntimeAgentReadinessService:
    registry = (
        RuntimeHandlerRegistry()
        if handler_registry is None
        else handler_registry
    )
    release = (
        RuntimeCanaryReleaseRegistry()
        if release_registry is None
        else release_registry
    )
    return RuntimeAgentReadinessService(
        agent_registry or AgentRegistry(),
        RuntimeBusinessRegistry(services),  # type: ignore[arg-type]
        RuntimeLaunchPolicy(
            launch_modes,
            release_registry=release,
            release_gate_required=release_gate_required,
        ),
        lifecycle_enabled=True,
        release_registry=release,
        handler_registry=registry,
    )


def _release_registry(
    *, agent_version: str = "1.0", plan_version: str = "general-qa-v1"
) -> RuntimeCanaryReleaseRegistry:
    return RuntimeCanaryReleaseRegistry(
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
                    agent_version=agent_version,
                    runtime_plan_version=plan_version,
                    authorization_ref="change-123",
                    captured_at=datetime(2026, 8, 9, tzinfo=UTC),
                    redaction_status="redacted",
                ),
            )
        }
    )


def test_direct_runtime_service_is_reported_as_implemented() -> None:
    readiness = _readiness([_RuntimeService()])

    item = readiness.inspect("GENERAL_QUESTION_V1")

    assert item.status == "runtime_implemented"
    assert item.runtime_plan_available is True
    assert item.runtime_services == ("_RuntimeService",)
    assert item.blockers == ()
    assert item.recommended_actions == ("configure_canary_launch",)
    assert item.to_dict()["recommended_actions"] == ["configure_canary_launch"]


def test_disabled_agent_with_runtime_service_is_not_reported_ready() -> None:
    readiness = _readiness([_RuntimeService()])
    definition = readiness.agent_registry.get("GENERAL_QUESTION_V1")
    readiness.agent_registry._agents[definition.agent_id] = replace(
        definition, enabled=False
    )

    item = readiness.inspect(definition.agent_id)

    assert item.status == "blocked"
    assert item.effective_launch_mode == "legacy"
    assert item.runtime_plan_available is True
    assert "agent_disabled" in item.blockers
    assert item.canary_release_eligible is False
    assert item.recommended_actions == (
        "enable_agent",
        "review_agent_eligibility",
    )


def test_unpublished_agent_with_runtime_service_is_not_reported_ready() -> None:
    registry = AgentRegistry()
    definition = registry.get("GENERAL_QUESTION_V1")
    registry._agents[definition.agent_id] = replace(
        definition, publication_status="planned"
    )

    item = _readiness(
        [_RuntimeService()], agent_registry=registry
    ).inspect(definition.agent_id)

    assert item.status == "blocked"
    assert item.effective_launch_mode == "legacy"
    assert item.runtime_plan_available is True
    assert "agent_unpublished:planned" in item.blockers
    assert item.canary_release_eligible is False


def test_configured_default_without_canary_is_blocked() -> None:
    readiness = _readiness(
        [_RuntimeService()],
        launch_modes="GENERAL_QUESTION_V1=default",
        release_gate_required=True,
    )

    item = readiness.inspect("GENERAL_QUESTION_V1")

    assert item.status == "blocked"
    assert item.effective_launch_mode == "legacy"
    assert "canary_release_evidence_missing" in item.blockers
    assert item.recommended_actions == (
        "run_provider_free_release_preflight",
        "collect_authorized_paired_trace",
    )


def test_business_registry_reads_legacy_plan_version_declaration() -> None:
    registry = RuntimeBusinessRegistry(
        [_LegacyPlanVersionService()]  # type: ignore[list-item]
    )

    assert registry.runtime_plan_version("GENERAL_QUESTION_V1") == "general-qa-v1"


@pytest.mark.parametrize(
    ("artifact_agent_version", "artifact_plan_version", "reason"),
    [
        ("0.9", "general-qa-v1", "canary_artifact_agent_version_mismatch"),
        ("1.0", "general-qa-v0", "canary_artifact_runtime_plan_version_mismatch"),
    ],
)
def test_readiness_blocks_stale_release_artifact(
    artifact_agent_version: str,
    artifact_plan_version: str,
    reason: str,
) -> None:
    readiness = _readiness(
        [_RuntimeService()],
        launch_modes="GENERAL_QUESTION_V1=default",
        release_gate_required=True,
        release_registry=_release_registry(
            agent_version=artifact_agent_version,
            plan_version=artifact_plan_version,
        ),
    )

    item = readiness.inspect("GENERAL_QUESTION_V1")

    assert item.status == "blocked"
    assert item.effective_launch_mode == "legacy"
    assert reason in item.blockers
    assert item.recommended_actions == (
        "refresh_canary_artifact_for_current_versions",
        "run_provider_free_release_preflight",
        "collect_authorized_paired_trace",
    )


@pytest.mark.parametrize(
    ("launch_mode", "expected_status"),
    [
        ("canary", "canary_ready"),
        ("default", "default_ready"),
    ],
)
def test_readiness_accepts_matching_release_artifact(
    launch_mode: str, expected_status: str
) -> None:
    readiness = _readiness(
        [_RuntimeService()],
        launch_modes=f"GENERAL_QUESTION_V1={launch_mode}",
        release_gate_required=True,
        release_registry=_release_registry(),
    )

    item = readiness.inspect("GENERAL_QUESTION_V1")

    assert item.status == expected_status
    assert item.effective_launch_mode == launch_mode
    assert item.canary_release_eligible is True
    assert item.canary_reason == "canary_release_evidence_approved"


def test_default_ready_recommends_canary_observation_and_approval() -> None:
    readiness = _readiness(
        [_RuntimeService()],
        launch_modes="GENERAL_QUESTION_V1=default",
        release_gate_required=True,
        release_registry=_release_registry(),
    )

    item = readiness.inspect("GENERAL_QUESTION_V1")

    assert item.status == "default_ready"
    assert item.blockers == ()
    assert item.recommended_actions == (
        "observe_canary_before_default_approval",
        "approve_default_promotion",
    )


def test_readiness_blocks_release_gate_without_plan_version_expectation() -> None:
    readiness = _readiness(
        [_UnversionedRuntimeService()],
        launch_modes="GENERAL_QUESTION_V1=default",
        release_gate_required=True,
        release_registry=_release_registry(),
    )

    item = readiness.inspect("GENERAL_QUESTION_V1")

    assert item.status == "blocked"
    assert item.effective_launch_mode == "legacy"
    assert item.canary_release_eligible is False
    assert item.canary_reason == "canary_artifact_version_expectation_missing"
    assert item.blockers == ("canary_artifact_version_expectation_missing",)


def test_wildcard_goal_runtime_is_explicit_only() -> None:
    handlers = RuntimeHandlerRegistry()

    async def handler(_run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        return RuntimeObservation(node_id=node.node_id)

    handlers.register(
        RuntimeHandlerDescriptor(handler_id="tool.read", kind="tool"),
        handler,
    )
    readiness = _readiness([_GoalService()], handler_registry=handlers)

    item = readiness.inspect("GENERAL_QUESTION_V1")

    assert item.status == "explicit_goal_only"
    assert item.explicit_goal_runtime_available is True
    assert item.runtime_plan_available is False
    assert "runtime_service_missing" in item.blockers
    assert item.recommended_actions == ("register_runtime_business_service",)


def test_runtime_readiness_endpoint_is_provider_free(client) -> None:
    response = client.get("/api/v1/agents/runtime-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_called"] is False
    assert payload["agents"]
    assert all(
        "status" in item
        and "blockers" in item
        and "recommended_actions" in item
        for item in payload["agents"]
    )
