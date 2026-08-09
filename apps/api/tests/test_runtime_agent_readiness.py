from __future__ import annotations

from app.agents import AgentRegistry
from app.runtime import (
    AgentRun,
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

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled


class _GoalService:
    agent_id = "*"
    runtime_option_key = "runtime_goal_runtime"


def _readiness(
    services: list[object],
    *,
    launch_modes: str = "",
    release_gate_required: bool = False,
    handler_registry: RuntimeHandlerRegistry | None = None,
) -> RuntimeAgentReadinessService:
    registry = (
        RuntimeHandlerRegistry()
        if handler_registry is None
        else handler_registry
    )
    return RuntimeAgentReadinessService(
        AgentRegistry(),
        RuntimeBusinessRegistry(services),  # type: ignore[arg-type]
        RuntimeLaunchPolicy(
            launch_modes,
            release_registry=RuntimeCanaryReleaseRegistry(),
            release_gate_required=release_gate_required,
        ),
        lifecycle_enabled=True,
        release_registry=RuntimeCanaryReleaseRegistry(),
        handler_registry=registry,
    )


def test_direct_runtime_service_is_reported_as_implemented() -> None:
    readiness = _readiness([_RuntimeService()])

    item = readiness.inspect("GENERAL_QUESTION_V1")

    assert item.status == "runtime_implemented"
    assert item.runtime_plan_available is True
    assert item.runtime_services == ("_RuntimeService",)
    assert item.blockers == ()


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


def test_runtime_readiness_endpoint_is_provider_free(client) -> None:
    response = client.get("/api/v1/agents/runtime-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_called"] is False
    assert payload["agents"]
    assert all("status" in item and "blockers" in item for item in payload["agents"])
