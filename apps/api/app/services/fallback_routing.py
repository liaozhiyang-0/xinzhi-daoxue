from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, RouteDecision
from app.observability.architecture_telemetry import architecture_telemetry
from app.providers.base import AgentProvider


@dataclass(frozen=True, slots=True)
class FallbackRoutingOutcome:
    decision: RouteDecision
    latency_ms: int
    provider: str


class FallbackRoutingService:
    """Resolve a routing-only target before business Runtime creation."""

    def __init__(
        self,
        registry: AgentRegistry,
        router: TaskRouter,
        provider: AgentProvider,
    ) -> None:
        self.registry = registry
        self.router = router
        self.provider = provider

    def required(self, decision: RouteDecision) -> bool:
        return self.registry.get(decision.agent_id).mode == "routing_only"

    async def resolve(
        self,
        request: AgentRequest,
        decision: RouteDecision,
    ) -> FallbackRoutingOutcome:
        if not self.required(decision):
            return FallbackRoutingOutcome(decision, 0, "not_required")
        # Routing is intentionally deterministic. A routing-only registry
        # entry is a compatibility marker, not an invitation to call a
        # remote workflow or a second model.
        started = perf_counter()
        architecture_telemetry.increment("fallback_route_count")
        fallback = self.router.route(request)
        if self.required(fallback):
            fallback = fallback.model_copy(
                update={
                    "agent_id": "GENERAL_QUESTION_V1",
                    "provider_required": False,
                    "route_source": "local_router_fallback",
                    "reason": "routing-only target collapsed to local general runtime",
                }
            )
        return FallbackRoutingOutcome(
            decision=fallback,
            latency_ms=max(0, int((perf_counter() - started) * 1_000)),
            provider="local",
        )
