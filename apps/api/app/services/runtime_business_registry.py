from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol, cast

from app.contracts import AgentRequest, AgentResult
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    PlanProposalProvider,
    RuntimeDecision,
)


class RuntimeBusinessService(Protocol):
    """Contract implemented by a business capability backed by Runtime."""

    agent_id: str
    runtime_option_key: str

    def supports(self, agent_id: str, request: AgentRequest) -> bool: ...

    def build_plan(self, request: AgentRequest) -> AgentRunPlan: ...

    async def run(
        self,
        request: AgentRequest,
        run: AgentRun,
        context: Any = None,
        checkpoint_hook: Callable[[AgentRun], Any] | None = None,
        event_hook: Callable[[str, AgentRun, str], Any] | None = None,
        control_provider: Callable[[AgentRun], Any] | None = None,
        decision_event_hook: Callable[[AgentRun, RuntimeDecision], Any]
        | None = None,
        plan_proposal_provider: PlanProposalProvider | None = None,
    ) -> AgentResult: ...


class RuntimeBusinessRegistry:
    """Resolve Runtime business capabilities by registered Agent ID."""

    def __init__(self, services: Iterable[RuntimeBusinessService]) -> None:
        self._services = tuple(services)

    def resolve(
        self, agent_id: str, request: AgentRequest
    ) -> RuntimeBusinessService | None:
        return next(
            (
                service
                for service in self._services
                if service.supports(agent_id, request)
            ),
            None,
        )

    def services(self) -> tuple[RuntimeBusinessService, ...]:
        """Return the registered services for read-only capability inspection."""

        return self._services

    def build_plan(
        self, agent_id: str, request: AgentRequest
    ) -> AgentRunPlan | None:
        service = self.resolve(agent_id, request)
        if service is None:
            return None
        agent_builder = getattr(service, "build_plan_for_agent", None)
        if callable(agent_builder):
            typed_builder = cast(
                Callable[[str, AgentRequest], AgentRunPlan], agent_builder
            )
            plan = typed_builder(agent_id, request)
        else:
            plan = service.build_plan(request)
        return self._bind_request_goal(agent_id, request, plan)

    @staticmethod
    def _bind_request_goal(
        agent_id: str, request: AgentRequest, plan: AgentRunPlan
    ) -> AgentRunPlan:
        """Bind safe route evidence to the durable Runtime goal contract.

        Business services remain responsible for their objective and success
        criteria. The registry adds only bounded, non-sensitive routing facts
        and the declared node capabilities, so every Runtime plan has the
        same inspectable goal shape without copying this logic into each
        business adapter.
        """

        goal = plan.goal_contract
        if goal is None:
            return plan
        routing = request.options.get("_routing")
        context = dict(goal.context)
        context.setdefault("agent_id", agent_id)
        if isinstance(routing, dict):
            for key in (
                "intent",
                "route_mode",
                "route_source",
                "task_subtype",
                "complexity",
            ):
                value = routing.get(key)
                if isinstance(value, str) and value:
                    context.setdefault(key, value)
            confidence = routing.get("route_confidence", routing.get("confidence"))
            if isinstance(confidence, (int, float)) and 0 <= confidence <= 1:
                context.setdefault("route_confidence", float(confidence))
        required_capabilities = list(goal.required_capabilities)
        if not required_capabilities:
            required_capabilities = [node.handler_id for node in plan.nodes]
        bound_goal = goal.model_copy(
            update={
                "context": context,
                "required_capabilities": required_capabilities,
                "source": goal.source or "runtime_business",
            }
        )
        return plan.model_copy(update={"goal_contract": bound_goal})

    def runtime_option_key(self, agent_id: str) -> str | None:
        # Wildcard services may resolve an explicitly opted-in request, but
        # must not advertise a default option key for every Agent. Returning
        # that key would make DEFAULT launch modes inject a goal-less generic
        # request into unrelated Agents.
        service = self._service_for_agent(agent_id)
        option_key = getattr(service, "runtime_option_key", None)
        return option_key if isinstance(option_key, str) and option_key else None

    def runtime_plan_version(self, agent_id: str) -> str | None:
        """Return the declared plan version for a direct Runtime service."""

        service = self._service_for_agent(agent_id)
        for attribute in ("runtime_plan_version", "plan_version"):
            version = getattr(service, attribute, None)
            if isinstance(version, str) and version:
                return version
        return None

    def _service_for_agent(self, agent_id: str) -> RuntimeBusinessService | None:
        return next(
            (
                service
                for service in self._services
                if getattr(service, "agent_id", "") == agent_id
            ),
            None,
        )

    def prepare_default_request(
        self, agent_id: str, request: AgentRequest
    ) -> AgentRequest:
        """Enable the declared Runtime option for a default-mode Agent.

        This changes only the internal request envelope. It never bypasses a
        service's own ``enabled`` or input validation checks.
        """

        option_key = self.runtime_option_key(agent_id) or ""
        if not option_key:
            return request
        options = dict(request.options)
        current = options.get(option_key)
        if current is None:
            options[option_key] = {"execute": True}
        elif isinstance(current, dict):
            options[option_key] = {**current, "execute": True}
        return request.model_copy(update={"options": options})
