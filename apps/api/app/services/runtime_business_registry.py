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
    """Resolve Runtime business capabilities without TaskRunner branching."""

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
            return typed_builder(agent_id, request)
        return service.build_plan(request)

    def runtime_option_key(self, agent_id: str) -> str | None:
        # Wildcard services may resolve an explicitly opted-in request, but
        # must not advertise a default option key for every Agent. Returning
        # that key would make DEFAULT launch modes inject a goal-less generic
        # request into unrelated legacy Agents.
        service = next(
            (
                candidate
                for candidate in self._services
                if getattr(candidate, "agent_id", "") == agent_id
            ),
            None,
        )
        option_key = getattr(service, "runtime_option_key", None)
        return option_key if isinstance(option_key, str) and option_key else None

    def runtime_plan_version(self, agent_id: str) -> str | None:
        """Return the declared plan version for a direct Runtime service."""

        service = next(
            (
                candidate
                for candidate in self._services
                if getattr(candidate, "agent_id", "") == agent_id
            ),
            None,
        )
        version = getattr(service, "runtime_plan_version", None)
        return version if isinstance(version, str) and version else None

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
        elif isinstance(current, dict) and "execute" not in current:
            options[option_key] = {**current, "execute": True}
        return request.model_copy(update={"options": options})
