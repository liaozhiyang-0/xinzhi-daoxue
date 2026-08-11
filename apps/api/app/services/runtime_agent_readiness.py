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
from app.services.runtime_capability_descriptor import (
    RuntimeCapabilityDescriptor,
)
from app.services.runtime_launch_policy import (
    RuntimeLaunchMode,
    RuntimeLaunchPolicy,
)
from app.services.runtime_release_authorization import (
    RuntimeReleaseAuthorizationRegistry,
)

_RELEASE_EVIDENCE_BLOCKERS = frozenset(
    {
        "canary_release_evidence_missing",
        "canary_authorized_evidence_missing",
        "canary_structural_gate_failed",
        "canary_provenance_incomplete",
    }
)


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
    structural_release_eligible: bool
    semantic_release_eligible: bool
    canary_release_eligible: bool
    canary_reason: str
    status: str
    blockers: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    runtime_capabilities: tuple[dict[str, Any], ...]

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
            "structural_release_eligible": self.structural_release_eligible,
            "semantic_release_eligible": self.semantic_release_eligible,
            "canary_release_eligible": self.canary_release_eligible,
            "canary_reason": self.canary_reason,
            "status": self.status,
            "blockers": list(self.blockers),
            "recommended_actions": list(self.recommended_actions),
            "runtime_capabilities": [dict(item) for item in self.runtime_capabilities],
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
        release_authorization_registry: (
            RuntimeReleaseAuthorizationRegistry | None
        ) = None,
        handler_registry: RuntimeHandlerRegistry | None = None,
        capability_descriptors: Iterable[RuntimeCapabilityDescriptor] = (),
    ) -> None:
        self.agent_registry = agent_registry
        self.business_registry = business_registry
        self.launch_policy = launch_policy
        self.lifecycle_enabled = lifecycle_enabled
        self.release_registry = release_registry
        self.release_authorization_registry = release_authorization_registry
        self.handler_registry = handler_registry
        self.capability_descriptors = tuple(capability_descriptors)

    def capability_dicts(self) -> list[dict[str, Any]]:
        """Return the provider-free cross-entry capability projection."""

        task_readiness: dict[str, RuntimeAgentReadiness] = {}
        capabilities: list[dict[str, Any]] = []
        for descriptor in self.capability_descriptors:
            payload = descriptor.to_dict()
            if descriptor.domain == "task_agent":
                readiness = task_readiness.get(descriptor.capability_id)
                if readiness is None:
                    readiness = self.inspect(descriptor.capability_id)
                    task_readiness[descriptor.capability_id] = readiness
                payload.update(
                    {
                        "status": readiness.status,
                        "structural_release_eligible": (
                            readiness.structural_release_eligible
                        ),
                        "semantic_release_eligible": (
                            readiness.semantic_release_eligible
                        ),
                        "canary_release_eligible": readiness.canary_release_eligible,
                        "canary_reason": readiness.canary_reason,
                        "blockers": list(readiness.blockers),
                    }
                )
            else:
                payload.update(self._learning_capability_status(descriptor))
            capabilities.append(payload)
        return capabilities

    def _learning_capability_status(
        self, descriptor: RuntimeCapabilityDescriptor
    ) -> dict[str, Any]:
        """Project LearningLoop readiness without entering its execution path.

        LearningLoop capabilities are not registered ``AgentRequest`` agents,
        so their status cannot be obtained through :meth:`inspect`.  Release
        eligibility is therefore evaluated only when both explicit identity
        and plan version are present.  Missing evidence or identity always
        remains visible as a blocker and never becomes authorization.
        """

        if not descriptor.enabled:
            return {
                "status": "blocked",
                "structural_release_eligible": False,
                "semantic_release_eligible": False,
                "canary_release_eligible": False,
                "canary_reason": "runtime_capability_disabled",
                "blockers": ["runtime_capability_disabled"],
            }

        if not descriptor.agent_version or not descriptor.version:
            reason = "canary_artifact_version_expectation_missing"
            return {
                "status": "blocked",
                "structural_release_eligible": False,
                "semantic_release_eligible": False,
                "canary_release_eligible": False,
                "canary_reason": reason,
                "blockers": [reason],
            }

        structural_release_eligible = self.release_registry.structural_eligible(
            descriptor.capability_id,
            expected_agent_version=descriptor.agent_version,
            expected_runtime_plan_version=descriptor.version,
        )
        semantic_release_eligible = self.release_registry.release_eligible(
            descriptor.capability_id,
            expected_agent_version=descriptor.agent_version,
            expected_runtime_plan_version=descriptor.version,
        )
        canary_reason = self._release_reason(
            descriptor.capability_id,
            target_mode=RuntimeLaunchMode.CANARY,
            expected_agent_version=descriptor.agent_version,
            expected_runtime_plan_version=descriptor.version,
            evidence_eligible=semantic_release_eligible,
        )
        canary_eligible = (
            semantic_release_eligible
            and canary_reason == "canary_release_evidence_approved"
        )
        blockers = [] if canary_eligible else [canary_reason]
        return {
            "status": (
                "canary_ready"
                if canary_eligible
                else "runtime_implemented"
            ),
            "structural_release_eligible": structural_release_eligible,
            "semantic_release_eligible": semantic_release_eligible,
            "canary_release_eligible": canary_eligible,
            "canary_reason": canary_reason,
            "blockers": blockers,
        }

    def _capabilities_for_agent(
        self, agent_id: str
    ) -> tuple[dict[str, Any], ...]:
        return tuple(
            descriptor.to_dict()
            for descriptor in self.capability_descriptors
            if descriptor.capability_id == agent_id
        )

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
        structural_eligible = False
        semantic_eligible = False
        if version_expectations_available:
            structural_eligible = self.release_registry.structural_eligible(
                agent_id,
                expected_agent_version=definition.version,
                expected_runtime_plan_version=expected_plan_version,
            )
            semantic_eligible = self.release_registry.release_eligible(
                agent_id,
                expected_agent_version=definition.version,
                expected_runtime_plan_version=expected_plan_version,
            )
        target_mode = (
            configured
            if configured in {RuntimeLaunchMode.CANARY, RuntimeLaunchMode.DEFAULT}
            else RuntimeLaunchMode.CANARY
        )
        canary_eligible = False
        if not version_expectations_available:
            canary_reason = "canary_artifact_version_expectation_missing"
        else:
            assert expected_plan_version is not None
            canary_reason = self._release_reason(
                agent_id,
                target_mode=target_mode,
                expected_agent_version=definition.version,
                expected_runtime_plan_version=expected_plan_version,
                evidence_eligible=semantic_eligible,
            )
        if version_expectations_available:
            canary_eligible = (
                semantic_eligible
                and canary_reason == "canary_release_evidence_approved"
            )
        if execution_blockers:
            canary_eligible = False
            canary_reason = execution_blockers[0]
        blockers: list[str] = []
        blockers.extend(execution_blockers)
        if (
            configured in {RuntimeLaunchMode.CANARY, RuntimeLaunchMode.DEFAULT}
            and decision.source == "canary_release_gate"
            and decision.reason
        ):
            blockers.append(decision.reason)
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
        recommended_actions = self._recommended_actions(
            status=status,
            blockers=tuple(dict.fromkeys(blockers)),
        )
        runtime_capabilities = self._capabilities_for_agent(agent_id)
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
            structural_release_eligible=structural_eligible,
            semantic_release_eligible=semantic_eligible,
            canary_release_eligible=canary_eligible,
            canary_reason=canary_reason,
            status=status,
            blockers=tuple(dict.fromkeys(blockers)),
            recommended_actions=recommended_actions,
            runtime_capabilities=runtime_capabilities,
        )

    def _release_reason(
        self,
        agent_id: str,
        *,
        target_mode: RuntimeLaunchMode,
        expected_agent_version: str,
        expected_runtime_plan_version: str,
        evidence_eligible: bool,
    ) -> str:
        """Return the same evidence + authorization reason as launch policy."""

        if not evidence_eligible:
            return self.release_registry.reason(
                agent_id,
                expected_agent_version=expected_agent_version,
                expected_runtime_plan_version=expected_runtime_plan_version,
            )
        if self.release_authorization_registry is None:
            return "release_authorization_missing"
        report = self.release_registry.report(agent_id)
        if report is None:
            return "canary_release_evidence_missing"
        return self.release_authorization_registry.reason(
            agent_id,
            suite_id=report.suite_id,
            launch_mode=target_mode.value,
            expected_agent_version=expected_agent_version,
            expected_runtime_plan_version=expected_runtime_plan_version,
        ) or "canary_release_evidence_approved"

    @staticmethod
    def _recommended_actions(
        *, status: str, blockers: tuple[str, ...]
    ) -> tuple[str, ...]:
        """Return stable, provider-free action identifiers for operators.

        Only known blocker categories are translated.  In particular, the
        returned values never include a blocker suffix such as a publication
        status, version, path, or any other runtime-derived detail.
        """

        actions: list[str] = []
        for blocker in blockers:
            if blocker == "agent_disabled":
                actions.extend(("enable_agent", "review_agent_eligibility"))
            elif blocker == "agent_execution_disabled":
                actions.append("enable_agent_execution")
            elif blocker.startswith("agent_unpublished:"):
                actions.append("review_agent_eligibility")
            elif blocker == "runtime_service_missing":
                actions.append("register_runtime_business_service")
            elif blocker == "runtime_service_disabled":
                actions.append("enable_runtime_service")
            elif blocker == "runtime_lifecycle_disabled":
                actions.append("enable_runtime_lifecycle")
            elif blocker == "canary_artifact_version_expectation_missing":
                actions.append("declare_agent_and_runtime_plan_versions")
            elif blocker.startswith("canary_artifact_"):
                actions.append("refresh_canary_artifact_for_current_versions")
                actions.append("run_provider_free_release_preflight")
                actions.append("collect_authorized_paired_trace")
            elif blocker.startswith("semantic_"):
                actions.append("run_provider_free_release_preflight")
                actions.append("collect_semantic_evidence_for_authorized_trace")
            elif blocker.startswith("release_authorization_"):
                actions.append("obtain_version_bound_release_authorization")
            elif blocker in _RELEASE_EVIDENCE_BLOCKERS:
                actions.append("run_provider_free_release_preflight")
                actions.append("collect_authorized_paired_trace")

        if actions:
            return tuple(dict.fromkeys(actions))
        if blockers:
            return ("review_runtime_readiness",)
        if status == "default_ready":
            return (
                "observe_canary_before_default_approval",
                "approve_default_promotion",
            )
        if status == "canary_ready":
            return ("observe_canary", "review_canary_results")
        if status == "runtime_implemented":
            return ("configure_canary_launch",)
        if status in {"explicit_goal_only", "legacy_only"}:
            return ("register_runtime_business_service",)
        return ()

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
