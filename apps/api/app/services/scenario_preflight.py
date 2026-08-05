from __future__ import annotations

from typing import Literal

from app.agents import AgentRegistry
from app.contracts.scenarios import ScenarioDefinition, ScenarioPreflightResponse
from app.core.config import Settings


class ScenarioPreflightService:
    """Build a no-network readiness report for one commercial scenario."""

    def check(
        self,
        scenario: ScenarioDefinition,
        *,
        registry: AgentRegistry,
        settings: Settings,
        mock_available: bool = False,
    ) -> ScenarioPreflightResponse:
        definition = registry.get(scenario.agent_id)
        configured = registry.is_configured(scenario.agent_id, settings)
        runtime_available = registry.is_runtime_available(scenario.agent_id, settings)
        commercialization = scenario.commercialization
        commercialization_complete = all(
            (
                commercialization.buyer,
                commercialization.delivery_unit,
                commercialization.value_capture,
                commercialization.expansion_path,
            )
        )
        blockers: list[str] = []
        warnings: list[str] = []
        if not definition.enabled:
            blockers.append("agent_disabled")
        if not runtime_available and not mock_available:
            blockers.append("no_runtime_or_mock_available")
        if not commercialization_complete:
            blockers.append("commercialization_plan_incomplete")
        if scenario.evidence_policy.manual_review_required:
            warnings.append("evidence_requires_manual_review")
        if not runtime_available and mock_available:
            warnings.append("demo_uses_mock_or_local_fallback")
        if definition.publication_status != "published":
            warnings.append(
                f"agent_publication_status:{definition.publication_status}"
            )
        agent_status: Literal[
            "runtime_available", "mock_only", "configured_unavailable", "unavailable"
        ]
        if runtime_available:
            agent_status = "runtime_available"
        elif mock_available:
            agent_status = "mock_only"
        elif configured:
            agent_status = "configured_unavailable"
        else:
            agent_status = "unavailable"
        return ScenarioPreflightResponse(
            scenario_id=scenario.id,
            scenario_version=scenario.version,
            agent_id=scenario.agent_id,
            agent_status=agent_status,
            runtime_available=runtime_available,
            configured=configured,
            mock_available=mock_available,
            demo_ready=not blockers and (runtime_available or mock_available),
            production_ready=not blockers and runtime_available,
            commercialization_complete=commercialization_complete,
            evidence_review_required=scenario.evidence_policy.manual_review_required,
            input_modes=list(scenario.input_modes),
            blockers=blockers,
            warnings=warnings,
        )
