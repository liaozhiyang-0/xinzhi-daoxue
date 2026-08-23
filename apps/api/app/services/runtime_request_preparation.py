"""Prepare the immutable request envelope for a durable Runtime launch.

This service owns conversation context assembly, bounded route refinement, and
the immutable execution plan. It does not invoke a Provider and does not mutate
the Task row; callers apply the returned route decision in their transaction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import (
    AgentExecutionPlan,
    AgentRequest,
    Intent,
    IntentExecutionPlan,
    RouteDecision,
)
from app.contracts.conversation import ConversationContextBundle
from app.runtime import RuntimeCompatibilitySnapshot
from app.services.agent_runtime import AgentExecutionPlanner
from app.services.context_assembly import ContextAssemblyService
from app.services.fallback_routing import FallbackRoutingService
from app.services.intent_plan import IntentPlanCompiler
from app.services.overall_routing import OverallRoutingService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RuntimeRequestPreparation:
    """Prepared request, routing, context, and execution plan."""

    request: AgentRequest
    decision: RouteDecision
    agent_id: str
    conversation_bundle: ConversationContextBundle | None
    route_latency_ms: int
    route_metadata: dict[str, object]
    route_reevaluated: dict[str, object] | None
    execution_plan: AgentExecutionPlan

    def to_snapshot(self) -> RuntimeCompatibilitySnapshot:
        bundle = self.conversation_bundle
        if bundle is None:
            context_status = (
                "restored"
                if self.route_metadata.get("status") == "restored"
                else "not_configured"
            )
            cache_status = "none"
            cache_backend = "none"
            source_message_ids: list[str] = []
            context_trimmed = False
            estimated_tokens = 0
        else:
            context_status = "assembled"
            cache_status = bundle.cache_status
            cache_backend = bundle.cache_backend
            source_message_ids = list(bundle.source_message_ids[:200])
            context_trimmed = bundle.context_trimmed
            estimated_tokens = bundle.token_estimate
        return RuntimeCompatibilitySnapshot(
            preparation_status=(
                "restored"
                if self.route_metadata.get("status") == "restored"
                else "prepared"
            ),
            agent_id=self.agent_id,
            route_source=self.decision.route_source,
            route_status=self.decision.route_status.value,
            route_revision=self.decision.route_revision,
            route_confidence=self.decision.route_confidence,
            route_reason=self.decision.reason,
            context_status=context_status,
            context_cache_status=cache_status,
            context_cache_backend=cache_backend,
            context_source_message_ids=source_message_ids,
            context_trimmed=context_trimmed,
            context_estimated_tokens=estimated_tokens,
            execution_plan_agent_id=self.execution_plan.agent_id,
            execution_plan_provider_type=self.execution_plan.provider_type,
            execution_plan_route_status=self.execution_plan.route_status,
            execution_plan_input_mode=self.execution_plan.input_mode,
            execution_plan_context_budget=self.execution_plan.context_budget,
            route_capability_checks={
                key: value
                for key, value in self.decision.availability.items()
                if isinstance(value, bool)
            },
            execution_plan_capability_checks=dict(
                self.execution_plan.availability_checks
            ),
        )


class RuntimeRequestPreparationService:
    """Prepare route and context inputs outside the Runtime executor."""

    def __init__(
        self,
        execution_planner: AgentExecutionPlanner,
        overall_router: OverallRoutingService | None,
        context_assembly: ContextAssemblyService | None,
        fallback_router: FallbackRoutingService | None = None,
        intent_plan_compiler: IntentPlanCompiler | None = None,
    ) -> None:
        self.execution_planner = execution_planner
        self.overall_router = overall_router
        self.context_assembly = context_assembly
        self.fallback_router = fallback_router
        self.intent_plan_compiler = intent_plan_compiler or IntentPlanCompiler()

    async def prepare(
        self,
        db: AsyncSession,
        *,
        request: AgentRequest,
        decision: RouteDecision,
        agent_id: str,
        session_id: str,
        user_id: str,
        current_message_id: str | None,
        course_id: str,
        fallback_task_family: str,
        runtime_resume: bool,
    ) -> RuntimeRequestPreparation:
        """Prepare or restore the request used by the selected execution path.

        A resumed Runtime uses the request and execution plan captured in its
        checkpoint. It therefore skips context rebuilding and route refinement,
        preventing a changed model/configuration from rewriting an in-flight
        Run's control inputs.
        """

        conversation_bundle: ConversationContextBundle | None = None
        if not runtime_resume:
            request, conversation_bundle = await self._assemble_context(
                db,
                request,
                decision,
                session_id=session_id,
                user_id=user_id,
                current_message_id=current_message_id,
                course_id=course_id,
                task_family=fallback_task_family,
                agent_id=agent_id,
            )

        route_metadata: dict[str, object] = {
            "status": "restored" if runtime_resume else "not_configured",
            "model_calls": 0,
        }
        route_reevaluated: dict[str, object] | None = None
        final_agent_id = agent_id
        route_latency_ms = 0
        planner_snapshot = request.options.get("_planner_snapshot", {})
        planner_takeover = (
            isinstance(planner_snapshot, dict)
            and planner_snapshot.get("mode") in {"controlled", "active", "takeover"}
            and planner_snapshot.get("status") == "completed"
        )
        if planner_takeover:
            route_metadata = {
                "status": f"planner_{planner_snapshot.get('mode', 'controlled')}",
                "model_calls": 0,
                "planner_version": planner_snapshot.get("planner_version", ""),
            }
        if (
            self.overall_router is not None
            and not runtime_resume
            and not planner_takeover
        ):
            outcome = await self.overall_router.route(request, decision)
            route_latency_ms = outcome.latency_ms
            route_metadata = dict(outcome.metadata)
            if outcome.used:
                previous_agent_id = final_agent_id
                decision = outcome.decision
                final_agent_id = decision.agent_id
                request = self.with_routing_context(request, decision)
                # The authoritative route may change the context family,
                # course, or target Agent, so rebuild it once.
                request, conversation_bundle = await self._assemble_context(
                    db,
                    request,
                    decision,
                    session_id=session_id,
                    user_id=user_id,
                    current_message_id=current_message_id,
                    course_id=decision.course_id,
                    task_family=decision.intent,
                    agent_id=final_agent_id,
                )
                route_reevaluated = {
                    "previous_agent_id": previous_agent_id,
                    "routing": decision.model_dump(mode="json"),
                    "overall_router": route_metadata,
                }

        if (
            self.fallback_router is not None
            and not runtime_resume
            and self.fallback_router.required(decision)
        ):
            previous_agent_id = final_agent_id
            fallback_outcome = await self.fallback_router.resolve(
                request,
                decision,
            )
            decision = fallback_outcome.decision
            final_agent_id = decision.agent_id
            request = self.with_routing_context(request, decision)
            route_latency_ms += fallback_outcome.latency_ms
            previous_model_calls = route_metadata.get("model_calls", 0)
            if not isinstance(previous_model_calls, int):
                previous_model_calls = 0
            route_metadata = {
                **route_metadata,
                "fallback_router": {
                    "status": "completed",
                    "provider": fallback_outcome.provider,
                    "elapsed_ms": fallback_outcome.latency_ms,
                    "model_calls": 1,
                },
                "model_calls": previous_model_calls + 1,
            }
            request, conversation_bundle = await self._assemble_context(
                db,
                request,
                decision,
                session_id=session_id,
                user_id=user_id,
                current_message_id=current_message_id,
                course_id=decision.course_id,
                task_family=decision.intent,
                agent_id=final_agent_id,
            )
            route_reevaluated = {
                "previous_agent_id": previous_agent_id,
                "routing": decision.model_dump(mode="json"),
                "fallback_router": route_metadata["fallback_router"],
            }

        if not runtime_resume and route_reevaluated is not None:
            # Task creation persists the first-pass plan.  A later overall or
            # fallback route can change the target and intent, so refresh the
            # plan before the immutable Runtime request is handed off.
            request = self.with_intent_plan(
                request,
                self.intent_plan_compiler.compile(request, decision),
            )

        execution_plan = (
            self.execution_plan_from_request(request)
            if runtime_resume
            else None
        ) or self.execution_planner.build(decision, request)
        if not runtime_resume:
            request = self.with_execution_plan(request, execution_plan)

        return RuntimeRequestPreparation(
            request=request,
            decision=decision,
            agent_id=final_agent_id,
            conversation_bundle=conversation_bundle,
            route_latency_ms=route_latency_ms,
            route_metadata=route_metadata,
            route_reevaluated=route_reevaluated,
            execution_plan=execution_plan,
        )

    async def _assemble_context(
        self,
        db: AsyncSession,
        request: AgentRequest,
        decision: RouteDecision,
        *,
        session_id: str,
        user_id: str,
        current_message_id: str | None,
        course_id: str,
        task_family: str,
        agent_id: str,
    ) -> tuple[AgentRequest, ConversationContextBundle | None]:
        if self.context_assembly is None:
            return request, None
        bundle = await self.context_assembly.assemble(
            db,
            session_id=session_id,
            user_id=user_id,
            current_message_id=current_message_id,
            course_id=course_id,
            task_family=self._route_task_family(decision, task_family),
            agent_id=agent_id,
        )
        return self.with_conversation_context(request, bundle), bundle

    @staticmethod
    def with_execution_plan(
        request: AgentRequest, plan: AgentExecutionPlan
    ) -> AgentRequest:
        options = dict(request.options)
        options["_execution_plan"] = plan.model_dump(mode="json")
        return request.model_copy(update={"options": options})

    @staticmethod
    def with_intent_plan(
        request: AgentRequest, plan: IntentExecutionPlan
    ) -> AgentRequest:
        options = dict(request.options)
        options["_intent_plan"] = plan.model_dump(mode="json")
        return request.model_copy(update={"options": options})

    @staticmethod
    def execution_plan_from_request(
        request: AgentRequest,
    ) -> AgentExecutionPlan | None:
        raw_plan = request.options.get("_execution_plan")
        if not isinstance(raw_plan, dict):
            return None
        try:
            return AgentExecutionPlan.model_validate(raw_plan)
        except ValueError:
            logger.warning(
                "execution_plan_invalid_on_runtime_resume task_id=%s",
                request.task_id,
                exc_info=True,
            )
            return None

    @staticmethod
    def with_conversation_context(
        request: AgentRequest, bundle: ConversationContextBundle
    ) -> AgentRequest:
        options = dict(request.options)
        options.update(
            {
                "conversation_context": bundle.model_dump(mode="json"),
                "conversation_summary": bundle.safe_prompt_text(),
                "recent_messages": [
                    item.model_dump(mode="json")
                    for item in bundle.recent_messages[-12:]
                ],
                "active_memories": list(bundle.active_memories),
                "working_state": bundle.working_state.model_dump(mode="json"),
            }
        )
        return request.model_copy(update={"options": options})

    @staticmethod
    def with_routing_context(
        request: AgentRequest, decision: RouteDecision
    ) -> AgentRequest:
        options = dict(request.options)
        options.update(
            {
                "_routing": decision.model_dump(mode="json"),
                "task_subtype": decision.task_subtype,
                "secondary_intents": list(decision.secondary_intents),
                "requires_pipeline": decision.requires_pipeline,
                "available_agents": [
                    item.agent_id
                    for item in decision.candidate_agents
                    if item.available
                ],
                "candidate_agents": [
                    item.model_dump(mode="json")
                    for item in decision.candidate_agents
                ],
                "local_confidence": decision.local_confidence,
                "_material_extraction": dict(decision.material_extraction),
            }
        )
        return request.model_copy(
            update={
                "options": options,
                "course_id": decision.course_id,
                "intent": Intent(decision.intent),
            }
        )

    @staticmethod
    def _route_task_family(
        decision: RouteDecision, fallback: str
    ) -> str:
        family = decision.intent_recognition.get("task_family")
        return (
            family.strip()
            if isinstance(family, str) and family.strip()
            else fallback
        )
