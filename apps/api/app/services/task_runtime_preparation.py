from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents import AgentDefinition, AgentRegistry
from app.application.tasks import TaskLeaseManager
from app.contracts import (
    AgentEventType,
    AgentExecutionPlan,
    AgentRequest,
    IntentExecutionPlan,
    RouteDecision,
)
from app.contracts.conversation import ConversationContextBundle
from app.core.errors import NotConfiguredError
from app.models import TaskStatus
from app.providers.base import AgentProvider
from app.repositories import AgentRunRepository, TaskRepository
from app.runtime import AgentRun, AgentRunPlan
from app.services.event_service import append_task_event
from app.services.internal_agent_execution import InternalAgentExecutionService
from app.services.runtime_execution_boundary import RuntimeExecutionBoundary
from app.services.runtime_launch_policy import (
    RuntimeLaunchDecision,
    RuntimeLaunchMode,
    RuntimeLaunchPolicy,
)
from app.services.runtime_run_lifecycle import RuntimeRunLifecycleService
from app.services.task_failure_service import TaskFailureService
from app.services.task_progress import TaskProgressReporter


@dataclass(frozen=True, slots=True)
class PreparedRuntimeTask:
    request: AgentRequest
    runtime_run: AgentRun
    runtime_plan: AgentRunPlan
    launch_decision: RuntimeLaunchDecision
    agent_id: str
    agent_definition: AgentDefinition
    execution_plan: AgentExecutionPlan
    intent_plan: IntentExecutionPlan | None
    conversation_bundle: ConversationContextBundle | None
    route_latency_ms: int
    route_metadata: dict[str, object]


class TaskRuntimePreparationService:
    """Claim a task and prepare its immutable Runtime execution envelope."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: AgentProvider,
        agent_registry: AgentRegistry,
        internal_agents: InternalAgentExecutionService | None,
        task_leases: TaskLeaseManager,
        task_failures: TaskFailureService,
        runtime_boundary: RuntimeExecutionBoundary,
        launch_policy: RuntimeLaunchPolicy,
        runtime_lifecycle: RuntimeRunLifecycleService,
        progress: TaskProgressReporter,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self.agent_registry = agent_registry
        self.internal_agents = internal_agents
        self.task_leases = task_leases
        self.task_failures = task_failures
        self.runtime_boundary = runtime_boundary
        self.launch_policy = launch_policy
        self.runtime_lifecycle = runtime_lifecycle
        self.progress = progress

    async def prepare(
        self,
        task_id: str,
        *,
        started_at: datetime,
        now: datetime,
    ) -> PreparedRuntimeTask | None:
        async with self.session_factory() as db:
            task = await TaskRepository(db).get(task_id, for_update=True)
            if task is None or task.status != TaskStatus.QUEUED:
                return None
            if not self.task_leases.can_start(task, now):
                return None
            if task.cancellation_requested:
                await self.task_failures.mark_cancelled(
                    db,
                    task_id,
                    "任务在执行前已取消",
                )
                return None

            existing_runtime = await AgentRunRepository(db).get_for_task(
                task_id,
                for_update=True,
            )
            runtime_resume = existing_runtime is not None and (
                RuntimeExecutionBoundary.is_resumable(existing_runtime.status)
            )
            agent_id = task.agent_id
            agent_definition = self.agent_registry.get(agent_id)
            internal_available = bool(
                self.internal_agents and self.internal_agents.available(agent_id)
            )
            active_provider = (
                "external_retrieval"
                if agent_definition.mode == "external_search"
                else "local"
                if agent_definition.mode == "retrieval_only"
                else "local_agent"
                if internal_available
                else self.provider.provider_name
            )
            await self.task_leases.mark_running(
                db,
                task,
                started_at=started_at,
                active_provider=active_provider,
            )
            runtime_snapshot, request_payload = (
                await self.runtime_boundary.restore_request_payload(
                    db,
                    runtime_id=(
                        existing_runtime.id
                        if existing_runtime is not None and runtime_resume
                        else None
                    ),
                    fallback=dict(task.input_content),
                )
            )
            request = AgentRequest.model_validate(request_payload)
            launch_decision = RuntimeLaunchDecision(
                agent_id=task.agent_id,
                mode=RuntimeLaunchMode.DEFAULT,
                source="runtime_registry",
                reason="registered_runtime_required",
            )
            if runtime_snapshot is not None and runtime_snapshot.launch_decision:
                launch_decision = RuntimeLaunchDecision.from_snapshot(
                    runtime_snapshot.launch_decision
                )
            decision = RouteDecision.model_validate(
                request.options.get("_routing", {})
            )
            intent_plan = self._intent_plan_from_request(request)
            route_metadata: dict[str, object] = {
                "status": "restored" if runtime_resume else "not_configured",
                "model_calls": 0,
            }
            route_stage_started = perf_counter()
            if not runtime_resume:
                await self.progress.append(
                    task_id,
                    agent_id,
                    db=db,
                    stage_id="route_refinement",
                    status="started",
                    label="正在确认执行路径",
                    progress=0.05,
                )
            preparation = await self.runtime_boundary.prepare_request(
                db,
                request=request,
                decision=decision,
                agent_id=agent_id,
                session_id=task.session_id,
                user_id=task.user_id,
                current_message_id=task.user_message_id,
                course_id=task.course_id,
                fallback_task_family=task.intent,
                runtime_resume=runtime_resume,
            )
            request = preparation.request
            decision = preparation.decision
            agent_id = preparation.agent_id
            agent_definition = self.agent_registry.get(agent_id)
            route_metadata = preparation.route_metadata
            compatibility_snapshot = (
                runtime_snapshot.compatibility_snapshot
                if (
                    runtime_resume
                    and runtime_snapshot is not None
                    and runtime_snapshot.compatibility_snapshot is not None
                )
                else preparation.to_snapshot()
            )
            if preparation.route_reevaluated is not None:
                task.agent_id = agent_id
                task.course_id = decision.course_id
                task.intent = decision.intent
                task.route_status = decision.route_status.value
                task.route_reason = decision.reason
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.ROUTE_REEVALUATED,
                    agent_id=agent_id,
                    data=preparation.route_reevaluated,
                )
            if not runtime_resume:
                await self.progress.append(
                    task_id,
                    agent_id,
                    db=db,
                    stage_id="route_refinement",
                    status="completed",
                    label="执行路径已确认",
                    progress=0.12,
                    elapsed_ms=int((perf_counter() - route_stage_started) * 1000),
                    detail=str(route_metadata.get("status", "completed")),
                )
            execution_plan = preparation.execution_plan
            if runtime_resume and runtime_snapshot is not None:
                self.runtime_boundary.validate_resume_invariants(
                    runtime_snapshot,
                    task_agent_id=task.agent_id,
                    request=request,
                    execution_plan=execution_plan,
                )
            if intent_plan is not None and not runtime_resume:
                await self._append_initial_plan_events(
                    db,
                    task.id,
                    task.agent_id,
                    intent_plan,
                )
            runtime_goal = (
                intent_plan.goal
                if intent_plan is not None and intent_plan.goal.strip()
                else str(
                    request.canonical_input.get(
                        "text",
                        request.canonical_input.get("question", ""),
                    )
                )
            )
            if not (
                runtime_resume
                and runtime_snapshot is not None
                and runtime_snapshot.launch_decision is not None
            ):
                launch_decision = self.launch_policy.resolve(
                    task.agent_id,
                    request,
                    lifecycle_enabled=self.runtime_lifecycle.enabled,
                    runtime_option_key=(
                        self.runtime_boundary.runtime_option_key_for_request(
                            task.agent_id,
                            request,
                        )
                    ),
                    expected_agent_version=self.agent_registry.get(
                        task.agent_id
                    ).version,
                    expected_runtime_plan_version=(
                        self.runtime_boundary.runtime_plan_version(task.agent_id)
                    ),
                )
            if not runtime_resume:
                request = self.runtime_boundary.prepare_request_for_launch(
                    task.agent_id,
                    request,
                    launch_decision.mode,
                )
            runtime_plan = (
                runtime_snapshot.plan
                if runtime_resume and runtime_snapshot is not None
                else self.runtime_boundary.build_plan(task.agent_id, request)
            )
            if runtime_plan is None:
                # Keep published legacy agents executable while their
                # business Runtime adapter is migrated.  The compatibility
                # plan uses the registered provider handler and remains
                # observable through the same durable Runtime envelope.
                runtime_plan = RuntimeRunLifecycleService._build_legacy_plan(
                    task.agent_id,
                    runtime_goal,
                )
                launch_decision = RuntimeLaunchDecision(
                    agent_id=task.agent_id,
                    mode=RuntimeLaunchMode.DEFAULT,
                    source="legacy_compatibility",
                    reason="registered_agent_runtime_plan_pending",
                )
            runtime_run = await self.runtime_boundary.start_or_restore(
                db,
                task_id=task.id,
                agent_id=task.agent_id,
                provider=active_provider,
                goal=runtime_goal,
                intent_plan=intent_plan,
                runtime_plan=runtime_plan,
                request=request,
                launch_decision=launch_decision.to_snapshot(),
                compatibility_snapshot=compatibility_snapshot,
            )
            if runtime_run is None:
                raise NotConfiguredError("registered Agent Runtime is unavailable")
            await db.commit()
            return PreparedRuntimeTask(
                request=request,
                runtime_run=runtime_run,
                runtime_plan=runtime_plan,
                launch_decision=launch_decision,
                agent_id=agent_id,
                agent_definition=agent_definition,
                execution_plan=execution_plan,
                intent_plan=intent_plan,
                conversation_bundle=preparation.conversation_bundle,
                route_latency_ms=preparation.route_latency_ms,
                route_metadata=route_metadata,
            )

    @staticmethod
    def _intent_plan_from_request(
        request: AgentRequest,
    ) -> IntentExecutionPlan | None:
        raw_plan = request.options.get("_intent_plan")
        if not isinstance(raw_plan, dict):
            return None
        try:
            return IntentExecutionPlan.model_validate(raw_plan)
        except ValueError:
            return None

    @staticmethod
    async def _append_initial_plan_events(
        db: AsyncSession,
        task_id: str,
        agent_id: str,
        intent_plan: IntentExecutionPlan,
    ) -> None:
        for node in intent_plan.nodes:
            if node.depends_on:
                continue
            await append_task_event(
                db,
                task_id,
                AgentEventType.PLAN_NODE_STARTED,
                agent_id=agent_id,
                data={
                    "plan_id": intent_plan.plan_id,
                    "node_id": node.node_id,
                    "node_type": node.node_type,
                    "target_id": node.target_id,
                },
            )
