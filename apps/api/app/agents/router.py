from __future__ import annotations

from app.agents.registry import AgentRegistry
from app.contracts.agent import AgentRequest
from app.contracts.routing import RouteDecision, RouteStatus


class TaskRouter:
    """Select an explicit registered agent; unknown work never falls back."""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    def route(self, request: AgentRequest) -> RouteDecision:
        intent = request.intent.value
        course_id = request.course_id.upper()
        for rule in self.registry.routing_rules:
            if course_id in rule.course_ids and intent in rule.intents:
                agent = self.registry.get(rule.agent_id)
                return RouteDecision(
                    agent_id=agent.agent_id,
                    scene=rule.scene,
                    course_id=course_id,
                    intent=intent,
                    route_status=RouteStatus.SELECTED,
                    reason=(
                        f"matched configured route course_id={course_id}, "
                        f"intent={intent}"
                    ),
                    retrieval_required=rule.retrieval_required,
                    provider_required=rule.provider_required,
                )
        return RouteDecision(
            agent_id="UNSUPPORTED",
            scene=request.scene.value,
            course_id=course_id,
            intent=intent,
            route_status=RouteStatus.UNSUPPORTED,
            reason=f"no configured route for course_id={course_id}, intent={intent}",
            retrieval_required=False,
            provider_required=False,
        )
