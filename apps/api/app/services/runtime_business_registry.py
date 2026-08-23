from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol, cast

from app.contracts import AgentRequest, AgentResult
from app.core.internal_workflows import LOCAL_AGENT_IMPLEMENTATIONS
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

    _CANONICAL_INTERNAL_HANDLERS = frozenset(
        {
            *LOCAL_AGENT_IMPLEMENTATIONS,
        }
    )

    def __init__(self, services: Iterable[RuntimeBusinessService]) -> None:
        self._services = tuple(services)

    def resolve(
        self, agent_id: str, request: AgentRequest
    ) -> RuntimeBusinessService | None:
        # A completed CanonicalPlan is already the authoritative Runtime
        # envelope.  Route it through the generic handler executor instead of
        # letting a legacy business adapter reinterpret its node shape.
        if self._has_authoritative_canonical_plan(request):
            generic = next(
                (
                    service
                    for service in self._services
                    if getattr(service, "agent_id", "") == "*"
                    and service.supports(agent_id, request)
                ),
                None,
            )
            if generic is not None:
                return generic
        # An explicitly declared Goal Runtime is a request-level override. It
        # must win over the routed business adapter for the same Agent; the
        # wildcard service is the only implementation allowed to interpret
        # that option.
        goal_options = request.options.get("runtime_goal_runtime")
        if isinstance(goal_options, dict) and goal_options.get("execute") is True:
            generic = next(
                (
                    service
                    for service in self._services
                    if getattr(service, "agent_id", "") == "*"
                    and service.supports(agent_id, request)
                ),
                None,
            )
            if generic is not None:
                return generic
        return next(
            (
                service
                for service in self._services
                if service.supports(agent_id, request)
            ),
            None,
        )

    @staticmethod
    def is_authoritative_canonical_plan(request: AgentRequest) -> bool:
        snapshot = request.options.get("_planner_snapshot")
        canonical_plan = RuntimeBusinessRegistry._canonical_plan_data(request)
        if not (
            request.options.get("_scenario_catalog_bound") is not True
            and isinstance(snapshot, dict)
            and snapshot.get("mode") in {"controlled", "active", "takeover"}
            and snapshot.get("status") == "completed"
            and isinstance(canonical_plan, dict)
        ):
            return False
        bindings = canonical_plan.get("capability_bindings", [])
        if not isinstance(bindings, list):
            return False
        handler_ids: set[str] = set()
        for item in bindings:
            if not isinstance(item, dict):
                continue
            handler_id = item.get("handler_id")
            if isinstance(handler_id, str):
                handler_ids.add(handler_id)
        return bool(handler_ids) and all(
            handler_id in RuntimeBusinessRegistry._CANONICAL_INTERNAL_HANDLERS
            or handler_id.startswith("tool.")
            for handler_id in handler_ids
        )

    @staticmethod
    def _canonical_plan_data(request: AgentRequest) -> dict[str, Any] | None:
        direct = request.options.get("_canonical_plan")
        if isinstance(direct, dict):
            return direct
        snapshot = request.options.get("_planner_snapshot")
        if isinstance(snapshot, dict):
            nested = snapshot.get("canonical_plan")
            if isinstance(nested, dict):
                return nested
        return None

    @staticmethod
    def _has_authoritative_canonical_plan(request: AgentRequest) -> bool:
        return RuntimeBusinessRegistry.is_authoritative_canonical_plan(request)

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
                "source": (
                    "canonical_plan"
                    if RuntimeBusinessRegistry._canonical_plan_data(request)
                    is not None
                    and isinstance(request.options.get("_planner_snapshot"), dict)
                    and request.options["_planner_snapshot"].get("mode")
                    in {"controlled", "active", "takeover"}
                    and request.options["_planner_snapshot"].get("status")
                    == "completed"
                    else goal.source or "runtime_business"
                ),
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
                if (
                    getattr(service, "agent_id", "") == agent_id
                    or agent_id in getattr(service, "supported_agent_ids", ())
                )
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

        service = self._service_for_agent(agent_id)
        option_key = getattr(service, "runtime_option_key", None) or ""
        if not option_key:
            return request
        options = dict(request.options)
        current = options.get(option_key)
        if current is None:
            value: dict[str, Any] = {"execute": True}
            if getattr(service, "allow_default_incomplete_evidence", False):
                value["allow_incomplete_evidence"] = True
            options[option_key] = value
        elif isinstance(current, dict):
            options[option_key] = {**current, "execute": True}
        return request.model_copy(update={"options": options})
