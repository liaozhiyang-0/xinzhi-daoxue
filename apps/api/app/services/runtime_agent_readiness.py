"""Provider-free, per-Agent Runtime migration readiness reporting."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.agents.registry import AgentRegistry
from app.contracts import AgentRequest
from app.runtime import RuntimeHandlerRegistry
from app.services.runtime_business_registry import RuntimeBusinessRegistry
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from app.services.runtime_launch_policy import RuntimeLaunchMode, RuntimeLaunchPolicy


@dataclass(frozen=True, slots=True)
class RuntimeAgentReadiness:
    """Auditable readiness state for one registered Agent."""

    agent_id: str
    runtime_services: tuple[str, ...]
    runtime_option_keys: tuple[str, ...]
    runtime_plan_available: bool
    explicit_goal_runtime_available: bool
    configured_launch_mode: str
    effective_launch_mode: str
    launch_source: str
    launch_reason: str
    canary_release_eligible: bool
    canary_reason: str
    status: str
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "runtime_services": list(self.runtime_services),
            "runtime_option_keys": list(self.runtime_option_keys),
            "runtime_plan_available": self.runtime_plan_available,
            "explicit_goal_runtime_available": self.explicit_goal_runtime_available,
            "configured_launch_mode": self.configured_launch_mode,
            "effective_launch_mode": self.effective_launch_mode,
            "launch_source": self.launch_source,
            "launch_reason": self.launch_reason,
            "canary_release_eligible": self.canary_release_eligible,
            "canary_reason": self.canary_reason,
            "status": self.status,
            "blockers": list(self.blockers),
        }


class RuntimeAgentReadinessService:
    """Compute Runtime readiness without calling business services or Providers."""

    def __init__(
        self,
        agent_registry: AgentRegistry,
        business_registry: RuntimeBusinessRegistry,
        launch_policy: RuntimeLaunchPolicy,
        *,
        lifecycle_enabled: bool,
        release_registry: RuntimeCanaryReleaseRegistry,
        handler_registry: RuntimeHandlerRegistry | None = None,
    ) -> None:
        self.agent_registry = agent_registry
        self.business_registry = business_registry
        self.launch_policy = launch_policy
        self.lifecycle_enabled = lifecycle_enabled
        self.release_registry = release_registry
        self.handler_registry = handler_registry

    def list_all(self) -> list[RuntimeAgentReadiness]:
        return [
            self.inspect(definition.agent_id)
            for definition in self.agent_registry.list_agents()
        ]

    def inspect(self, agent_id: str) -> RuntimeAgentReadiness:
        definition = self.agent_registry.get(agent_id)
        services = self.business_registry.services()
        direct_services = tuple(
            service
            for service in services
            if getattr(service, "agent_id", None) == agent_id
        )
        wildcard_services = tuple(
            service
            for service in services
            if getattr(service, "agent_id", None) == "*"
        )
        enabled_services = tuple(
            service
            for service in direct_services
            if bool(getattr(service, "enabled", True))
        )
        runtime_plan_available = bool(enabled_services)
        explicit_goal_available = bool(wildcard_services) and bool(
            self.handler_registry is not None
            and self.handler_registry.descriptors()
        )
        option_keys = tuple(
            sorted(
                {
                    str(option_key)
                    for service in direct_services
                    for option_key in [getattr(service, "runtime_option_key", "")]
                    if option_key
                }
            )
        )
        service_names = tuple(
            sorted(type(service).__name__ for service in direct_services)
        )
        request = AgentRequest(
            session_id="runtime-readiness",
            user_id="runtime-readiness",
        )
        execution_blockers: list[str] = []
        if not definition.enabled:
            execution_blockers.append("agent_disabled")
        if definition.execution_mode == "disabled":
            execution_blockers.append("agent_execution_disabled")
        if definition.publication_status not in {"published", "local"}:
            execution_blockers.append(
                f"agent_unpublished:{definition.publication_status}"
            )
        decision = self.launch_policy.resolve(
            agent_id,
            request,
            lifecycle_enabled=self.lifecycle_enabled,
            runtime_option_key=(option_keys[0] if option_keys else None),
            expected_agent_version=definition.version,
            expected_runtime_plan_version=(
                self.business_registry.runtime_plan_version(agent_id)
            ),
            execution_allowed=not execution_blockers,
            execution_block_reason=(
                execution_blockers[0]
                if execution_blockers
                else "agent_execution_unavailable"
            ),
        )
        configured = self.launch_policy.configured_mode(agent_id)
        expected_plan_version = self.business_registry.runtime_plan_version(
            agent_id
        )
        version_expectations_available = bool(
            definition.version.strip()
            and expected_plan_version
            and expected_plan_version.strip()
        )
        canary_eligible = self.release_registry.release_eligible(
            agent_id,
            expected_agent_version=definition.version,
            expected_runtime_plan_version=expected_plan_version,
        )
        canary_reason = (
            "canary_artifact_version_expectation_missing"
            if not version_expectations_available
            else self.release_registry.reason(
                agent_id,
                expected_agent_version=definition.version,
                expected_runtime_plan_version=expected_plan_version,
            )
        )
        if not version_expectations_available:
            canary_eligible = False
        if execution_blockers:
            canary_eligible = False
            canary_reason = execution_blockers[0]
        blockers: list[str] = []
        blockers.extend(execution_blockers)
        if not runtime_plan_available:
            blockers.append("runtime_service_missing")
        if direct_services and not enabled_services:
            blockers.append("runtime_service_disabled")
        if configured in {RuntimeLaunchMode.CANARY, RuntimeLaunchMode.DEFAULT}:
            if not self.lifecycle_enabled:
                blockers.append("runtime_lifecycle_disabled")
            if self.launch_policy.release_gate_required and not canary_eligible:
                blockers.append(canary_reason)
        if execution_blockers:
            status = "blocked"
        elif (
            configured in {RuntimeLaunchMode.CANARY, RuntimeLaunchMode.DEFAULT}
            and blockers
        ):
            status = "blocked"
        elif decision.mode == RuntimeLaunchMode.DEFAULT and runtime_plan_available:
            status = "default_ready"
        elif decision.mode == RuntimeLaunchMode.CANARY and runtime_plan_available:
            status = "canary_ready"
        elif decision.mode == RuntimeLaunchMode.SHADOW and runtime_plan_available:
            status = "shadow_ready"
        elif runtime_plan_available:
            status = "runtime_implemented"
        elif explicit_goal_available:
            status = "explicit_goal_only"
        else:
            status = "legacy_only"
        return RuntimeAgentReadiness(
            agent_id=agent_id,
            runtime_services=service_names,
            runtime_option_keys=option_keys,
            runtime_plan_available=runtime_plan_available,
            explicit_goal_runtime_available=explicit_goal_available,
            configured_launch_mode=(configured.value if configured else ""),
            effective_launch_mode=decision.mode.value,
            launch_source=decision.source,
            launch_reason=decision.reason,
            canary_release_eligible=canary_eligible,
            canary_reason=canary_reason,
            status=status,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    def as_dicts(
        self, agent_ids: Iterable[str] | None = None
    ) -> list[dict[str, Any]]:
        ids = (
            agent_ids
            if agent_ids is not None
            else (
                definition.agent_id
                for definition in self.agent_registry.list_agents()
            )
        )
        return [self.inspect(agent_id).to_dict() for agent_id in ids]
