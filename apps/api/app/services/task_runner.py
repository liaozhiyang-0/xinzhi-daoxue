from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents import AgentDefinition, AgentRegistry, TaskRouter
from app.contracts import (
    AgentEventType,
    AgentExecutionPlan,
    AgentRequest,
    AgentResult,
    Artifact,
    Intent,
    KnowledgeHit,
    RAGInteractionMode,
    RetrievalContextPacket,
    RetrievalResult,
    RouteDecision,
    RouteStatus,
    WorkflowContextBundle,
)
from app.contracts.conversation import (
    ConversationContextBundle,
    MessageRole,
    MessageStatus,
)
from app.contracts.learning import StudentAttempt, TeachingMode
from app.contracts.solver import AcademicProblem, SolverResult
from app.core.errors import AppError, NotConfiguredError, ProviderCancelledError
from app.courses import CourseRegistry
from app.models import AgentRunModel, ArtifactModel, TaskModel, TaskStatus
from app.providers.base import AgentProvider
from app.repositories import SessionRepository, TaskRepository
from app.services.agent_result_governance import (
    AgentResultValidatorRegistry,
    BusinessResultRendererRegistry,
)
from app.services.agent_runtime import AgentExecutionPlanner
from app.services.citation_validator import CitationValidator
from app.services.context_assembly import ContextAssemblyService
from app.services.conversation_message_service import ConversationMessageService
from app.services.event_service import append_task_event
from app.services.internal_agent_execution import InternalAgentExecutionService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_qa_service import (
    KnowledgeQAExecution,
    KnowledgeQAService,
)
from app.services.learning_outcome import LearningOutcomeService
from app.services.math_formatting_service import MathFormattingService
from app.services.memory_service import MemoryService
from app.services.rag_retrieval import RAGRetrievalService
from app.services.session_compaction import SessionCompactionService
from app.services.session_context import SessionContextService
from app.services.session_working_state import SessionWorkingStateService
from app.services.solver_boundary_policy import BoundaryDecision, SolverBoundaryPolicy
from app.services.solver_quality_gate import SolverQualityGateService
from app.services.storage import StorageService
from app.services.student_attempts import StudentAttemptService
from app.services.task_presentation import build_task_views
from app.services.teaching_foundation import TeachingFoundationService

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def elapsed_ms(started: datetime, completed: datetime) -> int:
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=UTC)
    return max(0, int((completed - started).total_seconds() * 1000))


class TaskRunner:
    """In-process runner with a submit API that a future worker can replace."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: AgentProvider,
        knowledge_base: KnowledgeBaseService,
        agent_registry: AgentRegistry,
        knowledge_qa: KnowledgeQAService,
        rag_retrieval: RAGRetrievalService | None = None,
        internal_agents: InternalAgentExecutionService | None = None,
        course_registry: CourseRegistry | None = None,
        *,
        context_assembly: ContextAssemblyService | None = None,
        session_compaction: SessionCompactionService | None = None,
        teaching_foundation: TeachingFoundationService | None = None,
        learning_outcome: LearningOutcomeService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self.knowledge_base = knowledge_base
        self.agent_registry = agent_registry
        self.knowledge_qa = knowledge_qa
        self.rag_retrieval = rag_retrieval
        self.internal_agents = internal_agents
        self.course_registry = course_registry
        self.context_assembly = context_assembly
        self.session_compaction = session_compaction
        self.teaching_foundation = teaching_foundation
        self.learning_outcome = learning_outcome
        self.student_attempts = StudentAttemptService()
        self.solver_quality_gate = SolverQualityGateService()
        self.citation_validator = CitationValidator()
        self.result_validators = AgentResultValidatorRegistry()
        self.business_renderers = BusinessResultRendererRegistry()
        self.math_formatting = MathFormattingService()
        self.execution_planner = AgentExecutionPlanner(
            agent_registry, knowledge_base.settings
        )
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._post_tasks: dict[str, asyncio.Task[None]] = {}
        self._summary_locks: dict[str, asyncio.Lock] = {}
        self.execution_owner = f"local-{uuid4().hex[:12]}"

    def submit(self, task_id: str) -> bool:
        existing = self._tasks.get(task_id)
        if existing is not None and not existing.done():
            return False
        background = asyncio.create_task(self.run(task_id), name=f"xzd-task-{task_id}")
        self._tasks[task_id] = background
        background.add_done_callback(lambda _: self._tasks.pop(task_id, None))
        return True

    async def shutdown(self) -> None:
        active = [
            task
            for task in [*self._tasks.values(), *self._post_tasks.values()]
            if not task.done()
        ]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        if self.rag_retrieval is not None:
            await asyncio.to_thread(self.rag_retrieval.close)

    async def run(self, task_id: str) -> None:
        request: AgentRequest
        conversation_bundle: ConversationContextBundle | None = None
        runner_started = perf_counter()
        started_at = utc_now()
        try:
            async with self.session_factory() as db:
                repository = TaskRepository(db)
                task = await repository.get(task_id, for_update=True)
                if task is None or task.status != TaskStatus.QUEUED:
                    return
                if task.cancellation_requested:
                    await self._mark_cancelled(db, task_id, "任务在执行前已取消")
                    return
                agent_id = task.agent_id
                agent_definition = self.agent_registry.get(agent_id)
                internal_available = bool(
                    self.internal_agents and self.internal_agents.available(agent_id)
                )
                active_provider = (
                    "local"
                    if agent_definition.mode == "retrieval_only"
                    else "local_agent"
                    if internal_available
                    else self.provider.provider_name
                )
                task.status = TaskStatus.RUNNING
                task.started_at = started_at
                task.updated_at = started_at
                task.execution_owner = self.execution_owner
                task.heartbeat_at = started_at
                task.lease_expires_at = started_at + timedelta(seconds=60)
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.TASK_RUNNING,
                    agent_id=task.agent_id,
                    data={"attempt": task.attempt},
                )
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.AGENT_STARTED,
                    agent_id=task.agent_id,
                    data={"provider": active_provider},
                )
                request = AgentRequest.model_validate(task.input_content)
                if self.context_assembly is not None:
                    conversation_bundle = await self.context_assembly.assemble(
                        db,
                        session_id=task.session_id,
                        user_id=task.user_id,
                        current_message_id=task.user_message_id,
                        course_id=task.course_id,
                        task_family=task.intent,
                        agent_id=task.agent_id,
                    )
                    request = self._with_conversation_context(
                        request, conversation_bundle
                    )
                cloud_workflow_allowed = self._cloud_workflow_allowed(request)
                decision = RouteDecision.model_validate(
                    request.options.get("_routing", {})
                )
                execution_plan = self.execution_planner.build(decision, request)
                request = self._with_execution_plan(request, execution_plan)
                await db.commit()

            knowledge_hits: list[KnowledgeHit] = []
            retrieval_result: RetrievalResult | None = None
            retrieval_attempted = False
            retrieval_packet: RetrievalContextPacket | None = None
            workflow_bundle: WorkflowContextBundle | None = None
            provider_latency_ms = 0
            context_latency_ms = 0
            citation_latency_ms = 0
            context_injected = False
            if agent_definition.mode == "routing_only":
                if (
                    self.provider.provider_name == "xingchen"
                    and not cloud_workflow_allowed
                ):
                    raise NotConfiguredError("星辰调度未获本次请求授权，未发送外部请求")
                dispatch_started = perf_counter()
                dispatch_result = await self.provider.run(
                    agent_id, self._cloud_safe_request(request), stream=False
                )
                provider_latency_ms += int((perf_counter() - dispatch_started) * 1000)
                decision = TaskRouter(
                    self.agent_registry, self.knowledge_base.settings
                ).route_cloud_response(dispatch_result.answer, request)
                agent_id = decision.agent_id
                agent_definition = self.agent_registry.get(agent_id)
                options = dict(request.options)
                options["_routing"] = decision.model_dump(mode="json")
                request = request.model_copy(update={"options": options})
                await self._append_cloud_route_event(task_id, decision)
                execution_plan = self.execution_planner.build(decision, request)
                request = self._with_execution_plan(request, execution_plan)

            workflow_definition = agent_definition
            internal_available = bool(
                self.internal_agents and self.internal_agents.available(agent_id)
            )
            boundary_preflight = self._academic_boundary_preflight(
                request,
                agent_id,
            )

            if agent_definition.mode == "retrieval_only":
                if self.knowledge_base.settings.enable_local_knowledge_qa:
                    execution = await self.knowledge_qa.run_with_generation(
                        agent_id, request
                    )
                else:
                    execution = await asyncio.to_thread(
                        self.knowledge_qa.run, agent_id, request
                    )
                await self._append_local_knowledge_events(task_id, agent_id, execution)
                result = execution.result
                retrieval_result = execution.retrieval
                retrieval_packet = execution.context
                knowledge_hits = list(execution.context.evidence)
                retrieval_attempted = True
            else:
                if execution_plan.use_rag and boundary_preflight is None:
                    (
                        retrieval_result,
                        retrieval_attempted,
                    ) = await self._retrieve_knowledge(
                        request, agent_definition, execution_plan
                    )
                    knowledge_hits = (
                        retrieval_result.hits if retrieval_result is not None else []
                    )
                if retrieval_attempted:
                    await self._append_retrieval_event(
                        task_id, agent_id, request.course_id, len(knowledge_hits)
                    )
                if retrieval_result is not None:
                    context_started = perf_counter()
                    retrieval_packet = self.knowledge_qa.context_service.build(
                        retrieval_result,
                        course_id=request.course_id,
                        intent=request.intent.value,
                    )
                    context_latency_ms += int((perf_counter() - context_started) * 1000)
                provider_started = perf_counter()
                provider_request = self._cloud_safe_request(request)
                if (
                    self.provider.provider_name == "xingchen"
                    and retrieval_result is not None
                    and agent_definition.retrieval_policy.generation_injection
                ):
                    assert retrieval_packet is not None
                    provider_request = self._with_learning_context(
                        provider_request, retrieval_packet
                    )
                    context_injected = True
                cloud_error: AppError | None = None
                cloud_response_failed = False
                try:
                    if internal_available and self.internal_agents is not None:
                        request = self._with_upstream_elapsed(
                            request,
                            runner_started,
                        )
                        internal_context = (
                            retrieval_packet
                            if agent_definition.retrieval_policy.generation_injection
                            else None
                        )
                        try:
                            result = await self.internal_agents.run(
                                agent_id, request, internal_context
                            )
                            result = await self._maybe_run_academic_ct_fallback(
                                result, request
                            )
                            result = await self._maybe_run_direct_model_fallback(
                                result,
                                request,
                                internal_context,
                            )
                            context_injected = internal_context is not None
                        except AppError as internal_error:
                            if not cloud_workflow_allowed:
                                raise NotConfiguredError(
                                    "本地内部能力失败，星辰回退未获本次请求授权"
                                ) from internal_error
                            if not self._legacy_provider_available(agent_id):
                                raise
                            result = await self.provider.run(
                                agent_id, provider_request, stream=False
                            )
                    else:
                        if (
                            self.provider.provider_name == "xingchen"
                            and agent_definition.provider == "xingchen"
                            and not cloud_workflow_allowed
                        ):
                            raise NotConfiguredError(
                                "星辰工作流未获本次请求授权，未发送外部请求"
                            )
                        if (
                            self.provider.provider_name == "xingchen"
                            and agent_definition.provider == "xingchen"
                            and not execution_plan.configured
                        ):
                            raise NotConfiguredError(
                                "Agent执行能力未配置，未发送外部请求"
                            )
                        result = await self.provider.run(
                            agent_id, provider_request, stream=False
                        )
                except AppError as exc:
                    cloud_opt_out = (
                        self.provider.provider_name == "xingchen"
                        and agent_definition.provider == "xingchen"
                        and not cloud_workflow_allowed
                    )
                    fallback_reason = "cloud_opt_out" if cloud_opt_out else exc.code
                    fallback_trigger = (
                        "not_configured"
                        if cloud_opt_out
                        else self._fallback_trigger(exc.code)
                    )
                    if (
                        agent_definition.fallback.handler == "no_fallback"
                        or fallback_trigger not in agent_definition.fallback.trigger_on
                    ):
                        raise
                    cloud_error = exc
                    fallback = self.agent_registry.resolve_fallback(agent_id)
                    if self._uses_local_retrieval_fallback(agent_definition):
                        if fallback is None or fallback.mode != "retrieval_only":
                            raise
                        execution = (
                            self.knowledge_qa.from_retrieval(
                                fallback.agent_id, request, retrieval_result
                            )
                            if retrieval_result is not None
                            else await asyncio.to_thread(
                                self.knowledge_qa.run, fallback.agent_id, request
                            )
                        )
                        retrieval_result = execution.retrieval
                        retrieval_packet = execution.context
                        knowledge_hits = list(execution.context.evidence)
                        await self._append_local_knowledge_events(
                            task_id, fallback.agent_id, execution
                        )
                        result = execution.result
                        result.warnings.append(
                            "按本地优先策略直接使用本地检索回答"
                            if cloud_opt_out
                            else f"云端工作流失败，已降级到本地检索回答: {exc.code}"
                        )
                    else:
                        result = self._non_cloud_fallback_result(
                            agent_definition,
                            request,
                            reason=fallback_reason,
                            cloud_status=(
                                "not_requested" if cloud_opt_out else "cloud_failed"
                            ),
                        )
                    routing = dict(request.options.get("_routing", {}))
                    routing.update(
                        {
                            "fallback_used": True,
                            "fallback_reason": fallback_reason,
                            "original_agent_id": agent_id,
                            "cloud_status": (
                                "not_requested" if cloud_opt_out else "cloud_failed"
                            ),
                        }
                    )
                    options = dict(request.options)
                    options["_routing"] = routing
                    request = request.model_copy(update={"options": options})
                    if fallback is not None and fallback.mode == "retrieval_only":
                        agent_id = fallback.agent_id
                        agent_definition = fallback
                if cloud_error is None:
                    upstream_status = str(
                        result.structured_result.get("status", "success")
                    ).casefold()
                    routing = dict(request.options.get("_routing", {}))
                    routing["cloud_status"] = (
                        "not_requested"
                        if result.provider in {"local", "local_agent", "local_graph"}
                        else f"cloud_{upstream_status}"
                    )
                    options = dict(request.options)
                    options["_routing"] = routing
                    request = request.model_copy(update={"options": options})
                    if upstream_status == "failed" and (
                        agent_definition.fallback.handler != "no_fallback"
                    ):
                        fallback = self.agent_registry.resolve_fallback(agent_id)
                        if (
                            self._uses_local_retrieval_fallback(agent_definition)
                            and fallback is not None
                            and fallback.mode == "retrieval_only"
                        ):
                            execution = (
                                self.knowledge_qa.from_retrieval(
                                    fallback.agent_id, request, retrieval_result
                                )
                                if retrieval_result is not None
                                else await asyncio.to_thread(
                                    self.knowledge_qa.run, fallback.agent_id, request
                                )
                            )
                            retrieval_result = execution.retrieval
                            retrieval_packet = execution.context
                            knowledge_hits = list(execution.context.evidence)
                            await self._append_local_knowledge_events(
                                task_id, fallback.agent_id, execution
                            )
                            result = execution.result
                            result.warnings.append(
                                "云端LEARN返回failed，已明确降级到本地检索回答"
                            )
                            routing.update(
                                {
                                    "fallback_used": True,
                                    "fallback_reason": "cloud_failed_status",
                                    "original_agent_id": agent_id,
                                    "cloud_status": "cloud_failed",
                                }
                            )
                            options["_routing"] = routing
                            request = request.model_copy(update={"options": options})
                            agent_id = fallback.agent_id
                            agent_definition = fallback
                            cloud_response_failed = True
                        elif not self._uses_local_retrieval_fallback(agent_definition):
                            result = self._non_cloud_fallback_result(
                                agent_definition,
                                request,
                                reason="cloud_failed_status",
                            )
                            routing.update(
                                {
                                    "fallback_used": True,
                                    "fallback_reason": "cloud_failed_status",
                                    "original_agent_id": agent_id,
                                    "cloud_status": "cloud_failed",
                                }
                            )
                            options["_routing"] = routing
                            request = request.model_copy(update={"options": options})
                            cloud_response_failed = True
                    if (
                        upstream_status == "misrouted"
                        and agent_definition.agent_id == "LEARN_01_KNOWLEDGE_QA_V1"
                        and request.course_id == "CT"
                        and int(routing.get("reroute_count", 0)) < 1
                        and self._is_ct_solver_reroute(result, request)
                    ):
                        target_rule = next(
                            rule
                            for rule in self.agent_registry.routing_rules
                            if "CT" in rule.course_ids
                            and Intent.SOLVE_PROBLEM.value in rule.intents
                        )
                        target = self.agent_registry.get(target_rule.agent_id)
                        if target.enabled and (
                            target.route_when_unconfigured
                            or self.agent_registry.is_runtime_available(
                                target.agent_id, self.knowledge_base.settings
                            )
                        ):
                            visited = [
                                str(item) for item in routing.get("visited_agents", [])
                            ]
                            visited.append(target.agent_id)
                            decision = RouteDecision(
                                agent_id=target.agent_id,
                                scene=target.scene,
                                course_id="CT",
                                intent=Intent.SOLVE_PROBLEM.value,
                                route_status=RouteStatus.SELECTED,
                                reason="LEARN明确misrouted，自动改投唯一CT求解工作流",
                                retrieval_required=True,
                                provider_required=True,
                                route_source="automatic_reroute",
                                route_confidence=1.0,
                                fallback_used=False,
                                original_agent_id=agent_definition.agent_id,
                                reason_codes=["learn_misrouted", "unique_ct_solver"],
                                local_confidence=1.0,
                                visited_agents=visited,
                                reroute_count=1,
                            )
                            routing = decision.model_dump(mode="json")
                            options["_routing"] = routing
                            request = request.model_copy(
                                update={
                                    "intent": Intent.SOLVE_PROBLEM,
                                    "options": options,
                                }
                            )
                            agent_id = target.agent_id
                            agent_definition = target
                            workflow_definition = target
                            execution_plan = self.execution_planner.build(
                                decision, request
                            )
                            request = self._with_execution_plan(request, execution_plan)
                            await self._append_cloud_route_event(task_id, decision)
                            (
                                retrieval_result,
                                retrieval_attempted,
                            ) = await self._retrieve_knowledge(
                                request, target, execution_plan
                            )
                            knowledge_hits = (
                                retrieval_result.hits
                                if retrieval_result is not None
                                else []
                            )
                            retrieval_packet = (
                                self.knowledge_qa.context_service.build(
                                    retrieval_result,
                                    course_id="CT",
                                    intent=Intent.SOLVE_PROBLEM.value,
                                )
                                if retrieval_result is not None
                                else None
                            )
                            result = await self.provider.run(
                                target.agent_id, request, stream=False
                            )
                provider_latency_ms += int((perf_counter() - provider_started) * 1000)
                pipeline_requested = bool(
                    request.options.get("_routing", {}).get("requires_pipeline", False)
                )
                if (
                    pipeline_requested
                    and agent_definition.agent_id == "RESEARCH_03_DATA_ANALYSIS_V1"
                    and str(
                        result.structured_result.get("status", "completed")
                    ).casefold()
                    not in {"failed", "misrouted"}
                ):
                    first_validation = self.result_validators.validate(
                        agent_definition, result, request, None
                    )
                    writing = self.agent_registry.get("RESEARCH_02_ACADEMIC_WRITING_V1")
                    if first_validation.response_usable and (
                        writing.route_when_unconfigured
                        or self.agent_registry.is_runtime_available(
                            writing.agent_id, self.knowledge_base.settings
                        )
                    ):
                        first_result = result
                        original_text = self._knowledge_query(request)
                        analysis_status = str(
                            first_result.business_data.get(
                                "analysis_status",
                                first_result.structured_result.get(
                                    "business_data", {}
                                ).get("analysis_status", "plan"),
                            )
                        )
                        canonical = dict(request.canonical_input)
                        canonical.update(
                            {
                                "text": original_text,
                                "writing_task": (
                                    "根据前一阶段输出完成用户明确要求的学术写作"
                                ),
                                "source_text": (
                                    f"analysis_status={analysis_status}\n"
                                    f"{first_result.answer}"
                                ),
                            }
                        )
                        pipeline_route = RouteDecision(
                            agent_id=writing.agent_id,
                            scene=writing.scene,
                            course_id=request.course_id,
                            intent=Intent.ACADEMIC_WRITING.value,
                            route_status=RouteStatus.SELECTED,
                            reason="用户明确要求数据分析后继续学术写作",
                            retrieval_required=False,
                            provider_required=(
                                cloud_workflow_allowed
                                and not (
                                    self.internal_agents is not None
                                    and self.internal_agents.available(writing.agent_id)
                                )
                            ),
                            route_source="sequential_pipeline",
                            route_confidence=1.0,
                            secondary_intents=[],
                            requires_pipeline=True,
                            reason_codes=["data_analysis_then_academic_writing"],
                            local_confidence=1.0,
                            visited_agents=[
                                agent_definition.agent_id,
                                writing.agent_id,
                            ],
                        )
                        pipeline_options = dict(request.options)
                        pipeline_options["_routing"] = pipeline_route.model_dump(
                            mode="json"
                        )
                        pipeline_request = request.model_copy(
                            update={
                                "intent": Intent.ACADEMIC_WRITING,
                                "canonical_input": canonical,
                                "options": pipeline_options,
                            }
                        )
                        pipeline_plan = self.execution_planner.build(
                            pipeline_route, pipeline_request
                        )
                        pipeline_request = self._with_execution_plan(
                            pipeline_request, pipeline_plan
                        )
                        await self._append_cloud_route_event(task_id, pipeline_route)
                        pipeline_started = perf_counter()
                        if (
                            self.internal_agents is not None
                            and self.internal_agents.available(writing.agent_id)
                        ):
                            result = await self.internal_agents.run(
                                writing.agent_id, pipeline_request
                            )
                        elif not cloud_workflow_allowed:
                            result = self._non_cloud_fallback_result(
                                writing,
                                pipeline_request,
                                reason="cloud_opt_out",
                                cloud_status="not_requested",
                            )
                        else:
                            result = await self.provider.run(
                                writing.agent_id,
                                self._cloud_safe_request(pipeline_request),
                                stream=False,
                            )
                        provider_latency_ms += int(
                            (perf_counter() - pipeline_started) * 1000
                        )
                        result.structured_result["pipeline_stages"] = [
                            {
                                "agent_id": agent_definition.agent_id,
                                "status": first_validation.result_status,
                                "analysis_status": analysis_status,
                            },
                            {
                                "agent_id": writing.agent_id,
                                "status": str(
                                    result.structured_result.get("status", "completed")
                                ),
                            },
                        ]
                        request = pipeline_request
                        execution_plan = pipeline_plan
                        agent_id = writing.agent_id
                        agent_definition = writing
                        workflow_definition = writing
                if boundary_preflight is not None:
                    result.structured_result["retrieval_preflight"] = {
                        "status": "skipped",
                        "reason": boundary_preflight.reason,
                        "saved_stage": "knowledge_retrieval",
                    }
                if retrieval_attempted:
                    result.metrics.retrieval_calls += 1
                if (
                    retrieval_packet is not None
                    and cloud_error is None
                    and not cloud_response_failed
                    and workflow_definition.retrieval_policy.interaction_mode
                    == "grounded_generation"
                    and str(result.structured_result.get("status", "")).casefold()
                    != "misrouted"
                ):
                    citation_started = perf_counter()
                    declared_refs = result.structured_result.get(
                        "source_references", []
                    )
                    citation_validation = self.citation_validator.validate(
                        result.answer,
                        retrieval_packet,
                        declared_references=(
                            declared_refs if isinstance(declared_refs, list) else []
                        ),
                    )
                    result.structured_result["citation_validation"] = {
                        "status": "passed" if citation_validation.valid else "failed",
                        "referenced_ids": list(citation_validation.referenced_ids),
                        "valid_ids": list(citation_validation.valid_ids),
                        "invalid_ids": list(citation_validation.invalid_ids),
                        "missing": citation_validation.missing,
                    }
                    source_by_id = {
                        item.evidence_id: item.source_ref
                        for item in retrieval_packet.evidence
                    }
                    result.citations = [
                        source_by_id[item]
                        for item in citation_validation.valid_ids
                        if item in source_by_id
                    ]
                    if not citation_validation.valid:
                        result.warnings.extend(citation_validation.warnings)
                        for invalid_id in citation_validation.invalid_ids:
                            result.answer = result.answer.replace(
                                f"[{invalid_id}]", "[引用无效]"
                            )
                    citation_latency_ms += int(
                        (perf_counter() - citation_started) * 1000
                    )
            if retrieval_result is not None:
                hit_payloads = [hit.model_dump(mode="json") for hit in knowledge_hits]
                result.structured_result["knowledge"] = {
                    "mode": retrieval_result.retrieval_mode,
                    "hits": hit_payloads,
                    "images": [
                        item.model_dump(mode="json")
                        for item in retrieval_result.image_hits
                    ],
                    "trace": retrieval_result.trace,
                }
                result.rag_status = retrieval_result.rag_status
                result.evidence_status = (
                    retrieval_packet.evidence_status
                    if retrieval_packet is not None
                    else (
                        "partial"
                        if retrieval_result.hits or retrieval_result.image_hits
                        else "insufficient"
                    )
                )
                result.related_images = [
                    item.model_dump(mode="json") for item in retrieval_result.image_hits
                ]
                result.retrieval_trace_id = retrieval_result.retrieval_trace_id
                result.retrieval_latency_ms = retrieval_result.latency_ms
                result.index_version = retrieval_result.index_version
                if retrieval_packet is not None:
                    workflow_bundle = WorkflowContextBundle.from_packet(
                        retrieval_packet,
                        request_id=str(
                            request.options.get("request_id", request.task_id)
                        ),
                        task_id=request.task_id,
                        agent_id=workflow_definition.agent_id,
                        retrieval_policy=(
                            workflow_definition.retrieval_policy.policy_name
                        ),
                        rag_mode=RAGInteractionMode(
                            workflow_definition.retrieval_policy.interaction_mode
                        ),
                        related_images=retrieval_result.image_hits,
                    )
                    if not context_injected:
                        workflow_bundle.workflow_evidence_ids = []
            execution_plan.evidence_count = len(knowledge_hits)
            execution_plan.context_injected = context_injected
            if knowledge_hits and (
                retrieval_packet is None or agent_definition.mode == "retrieval_only"
            ):
                result.citations = list(
                    dict.fromkeys(
                        [*result.citations, *(hit.source_ref for hit in knowledge_hits)]
                    )
                )
                for artifact in result.artifacts:
                    artifact.source_refs = list(
                        dict.fromkeys(
                            [
                                *artifact.source_refs,
                                *(hit.source_ref for hit in knowledge_hits),
                            ]
                        )
                    )
                    artifact.content["knowledge_sources"] = artifact.source_refs

            routing = request.options.get("_routing", {})
            result.course_id = request.course_id
            result.intent = request.intent.value
            result.request_id = str(request.options.get("request_id", request.task_id))
            result.task_id = request.task_id
            result.trace_id = str(request.options.get("trace_id", ""))
            result.cloud_status = str(
                routing.get(
                    "cloud_status",
                    (
                        "cloud_success"
                        if (
                            agent_definition.provider == "xingchen"
                            and result.provider == "xingchen"
                        )
                        else "not_required"
                    ),
                )
            )
            result.fallback_used = bool(
                result.fallback_used or routing.get("fallback_used", False)
            )
            result.fallback_reason = result.fallback_reason or str(
                routing.get("fallback_reason", "")
            )
            result = self._apply_solver_quality_gate(result, request, agent_id)
            if self.teaching_foundation is not None:
                try:
                    result = self.teaching_foundation.enrich(
                        result,
                        request,
                        retrieval_packet,
                        query=self._knowledge_query(request),
                    )
                except Exception:
                    logger.exception(
                        "teaching_foundation_unexpected_error task_id=%s",
                        request.task_id,
                    )
                    result = self._teaching_degraded_result(result, request)
            if result.fallback_used and not result.fallback_reason:
                result.fallback_reason = "route_cloud_unavailable"
            result_validation = self.result_validators.validate(
                workflow_definition, result, request, workflow_bundle
            )
            result.structured_result["validation"] = result_validation.model_dump(
                mode="json"
            )
            result.structured_result["result_status"] = result_validation.result_status
            result.structured_result["business_view"] = self.business_renderers.render(
                workflow_definition, result, result_validation
            )
            result.structured_result["material_extraction"] = request.options.get(
                "_material_extraction", {}
            )
            result.structured_result.update(
                {
                    "scene": agent_definition.scene,
                    "mode": agent_definition.mode,
                    "course": request.course_id,
                    "intent": request.intent.value,
                    "route_source": routing.get("route_source", "local_fast"),
                    "route_confidence": routing.get("route_confidence", 1.0),
                    "target_agent_id": agent_id,
                    "flow_configured": bool(
                        self.agent_registry.resolve_flow_id(
                            agent_id, self.knowledge_base.settings
                        )
                    ),
                    "knowledge_hit_count": len(knowledge_hits),
                    "rag_status": result.rag_status,
                    "evidence_status": result.evidence_status,
                    "related_images": result.related_images,
                    "retrieval_trace_id": result.retrieval_trace_id,
                    "retrieval_latency_ms": result.retrieval_latency_ms,
                    "index_version": result.index_version,
                    "solver_rag_generation_injection": (
                        agent_definition.retrieval_policy.generation_injection
                        and retrieval_packet is not None
                    ),
                    "execution_plan": execution_plan.model_dump(mode="json"),
                    "fallback_used": routing.get("fallback_used", False),
                    "fallback_reason": routing.get("fallback_reason", ""),
                    "cloud_status": routing.get("cloud_status", result.cloud_status),
                    "execution_source": (
                        "internal_agent"
                        if result.provider == "local_agent"
                        else "local_rag"
                        if result.provider == "local"
                        else "provider"
                    ),
                    "original_agent_id": routing.get("original_agent_id"),
                    "workflow_context": (
                        workflow_bundle.model_dump(mode="json")
                        if workflow_bundle is not None
                        else None
                    ),
                }
            )

            async with self.session_factory() as db:
                repository = TaskRepository(db)
                task = await repository.get(task_id, for_update=True)
                if task is None:
                    return
                if task.cancellation_requested:
                    await self._mark_cancelled(
                        db, task_id, "任务在 Provider 返回前收到取消请求"
                    )
                    return

                completed_at = utc_now()
                total_latency_ms = elapsed_ms(started_at, completed_at)
                result.metrics.latency_ms = total_latency_ms
                result.metrics.queue_latency_ms = elapsed_ms(
                    task.created_at, started_at
                )
                result.metrics.provider_latency_ms = provider_latency_ms
                result.metrics.total_latency_ms = total_latency_ms
                result.metrics.route_latency_ms = 0
                result.metrics.retrieval_latency_ms = result.retrieval_latency_ms
                result.metrics.context_latency_ms = context_latency_ms
                result.metrics.citation_latency_ms = citation_latency_ms
                result.metrics.model_latency_ms = provider_latency_ms
                result.metrics.verification_latency_ms = int(
                    result_validation.latency_ms
                )
                result.metrics.retry_count = max(0, task.attempt - 1)
                result.metrics.provider_used = result.provider
                result.metrics.fallback_used = result.fallback_used
                result.metrics.degraded_reason = result.fallback_reason
                quality_gate = result.structured_result.get("quality_gate", {})
                result.metrics.quality_status = (
                    str(quality_gate.get("status", "not_checked"))
                    if isinstance(quality_gate, dict)
                    else "not_checked"
                )
                result.metrics.final_confidence = result.confidence
                timings = {
                    "route_ms": 0,
                    "retrieval_ms": result.retrieval_latency_ms,
                    "context_ms": context_latency_ms,
                    "cloud_ms": provider_latency_ms,
                    "model_ms": provider_latency_ms,
                    "citation_ms": citation_latency_ms,
                    "validation_ms": int(result_validation.latency_ms),
                    "total_ms": total_latency_ms,
                }
                result.timings = timings
                presentation_started = perf_counter()
                presentation, execution_summary, evidence_view = build_task_views(
                    definition=workflow_definition,
                    result=result,
                    bundle=workflow_bundle,
                    routing=dict(routing),
                    timings=timings,
                )
                result.metrics.presentation_latency_ms = int(
                    (perf_counter() - presentation_started) * 1000
                )
                result.structured_result.update(
                    {
                        "presentation": presentation.model_dump(mode="json"),
                        "execution_summary": execution_summary.model_dump(mode="json"),
                        "evidence_view": [
                            item.model_dump(mode="json") for item in evidence_view
                        ],
                        "workflow_context": (
                            workflow_bundle.model_dump(mode="json")
                            if workflow_bundle is not None
                            else None
                        ),
                    }
                )
                math_source = dict(result.structured_result)
                math_source["answer_text"] = result.answer
                math_content = self.math_formatting.build_from_structured_result(
                    math_source
                )
                result.answer = math_content.markdown
                result.math_content = math_content
                result.structured_result["answer_text"] = math_content.markdown
                result.structured_result["math_content"] = math_content.model_dump(
                    mode="json"
                )
                if request.options.get("debug") is True:
                    result.structured_result["math_debug"] = (
                        self.math_formatting.debug_summary(math_content)
                    )
                for artifact in result.artifacts:
                    if "answer" in artifact.content:
                        artifact.content["answer"] = math_content.markdown
                    if "answer_text" in artifact.content:
                        artifact.content["answer_text"] = math_content.markdown
                    artifact.content["math_content"] = math_content.model_dump(
                        mode="json"
                    )
                task.agent_id = agent_id
                task.provider = result.provider
                task.status = TaskStatus.COMPLETED
                task.completed_at = completed_at
                task.updated_at = completed_at
                task.heartbeat_at = completed_at
                task.lease_expires_at = None
                context_usage: dict[str, object] = {}
                session = await SessionRepository(db).get_for_user(
                    task.session_id, task.user_id, for_update=True
                )
                if session is not None:
                    SessionContextService(self.knowledge_base.settings).update(
                        session, request, result
                    )
                    await SessionWorkingStateService(db).update_from_result(
                        request, result
                    )
                    await self._record_initial_attempt(
                        db,
                        task=task,
                        request=request,
                        result=result,
                    )
                    assistant_message = await ConversationMessageService(
                        db
                    ).append_assistant_for_task(task, result, session=session)
                    task.assistant_message_id = assistant_message.id
                    memory_started = perf_counter()
                    memory_writes = 0
                    memory_action = "none"
                    try:
                        memory_writes, memory_action = await MemoryService(
                            db
                        ).process_explicit_intent(
                            user_id=task.user_id,
                            session_id=task.session_id,
                            message_id=task.user_message_id or "",
                            text=ConversationMessageService.question_text(request),
                            course_id=task.course_id,
                            memory_enabled=session.memory_enabled,
                            auto_memory_enabled=session.auto_memory_enabled,
                        )
                        if memory_action in {"remembered", "forgotten"}:
                            confirmation = (
                                "已按你的要求保存这项偏好。"
                                if memory_action == "remembered"
                                else (
                                    f"已忘记 {memory_writes} 项相关记忆。"
                                    if memory_writes
                                    else "没有找到需要忘记的匹配记忆。"
                                )
                            )
                            await ConversationMessageService(db).append(
                                session=session,
                                user_id=task.user_id,
                                role=MessageRole.SYSTEM_EVENT,
                                status=MessageStatus.COMPLETED,
                                content_text=confirmation,
                                source_task_id=task.id,
                                reply_to_message_id=task.user_message_id,
                                metadata={
                                    "course_id": task.course_id,
                                    "memory_action": memory_action,
                                },
                            )
                    except AppError:
                        logger.info(
                            "memory_write_rejected task_id=%s reason=policy",
                            task.id,
                        )
                    memory_latency_ms = (perf_counter() - memory_started) * 1000
                    compaction_count = 0
                    compaction_latency_ms = 0.0
                    if conversation_bundle is not None:
                        result.metrics = result.metrics.model_copy(
                            update={
                                "message_count": session.message_count,
                                "recent_message_count": len(
                                    conversation_bundle.recent_messages
                                ),
                                "older_message_count": len(
                                    conversation_bundle.relevant_earlier_messages
                                ),
                                "session_summary_used": bool(
                                    conversation_bundle.session_summary
                                ),
                                "summary_version": conversation_bundle.summary_version,
                                "context_estimated_tokens": (
                                    conversation_bundle.token_estimate
                                ),
                                "context_budget_tokens": conversation_bundle.budget,
                                "context_budget_ratio": (
                                    conversation_bundle.token_estimate
                                    / max(1, conversation_bundle.budget)
                                ),
                                "context_trimmed": (
                                    conversation_bundle.context_trimmed
                                ),
                                "compaction_count": compaction_count,
                                "memory_enabled": session.memory_enabled,
                                "memory_retrieval_count": len(
                                    conversation_bundle.active_memories
                                ),
                                "memory_write_count": memory_writes,
                                "context_cache_hit": (
                                    conversation_bundle.cache_status == "hit"
                                ),
                                "context_cache_backend": (
                                    conversation_bundle.cache_backend
                                ),
                                "context_build_latency_ms": (
                                    conversation_bundle.build_latency_ms
                                ),
                                "compaction_latency_ms": compaction_latency_ms,
                                "memory_latency_ms": memory_latency_ms,
                            }
                        )
                        context_usage = {
                            "memory_enabled": session.memory_enabled,
                            "auto_memory_enabled": session.auto_memory_enabled,
                            "active_memory_count": len(
                                conversation_bundle.active_memories
                            ),
                            "active_memory_ids": list(
                                conversation_bundle.source_memory_ids
                            ),
                            "memory_write_count": memory_writes,
                            "memory_action": memory_action,
                            "recent_message_count": len(
                                conversation_bundle.recent_messages
                            ),
                            "older_message_count": len(
                                conversation_bundle.relevant_earlier_messages
                            ),
                            "summary_used": bool(
                                conversation_bundle.session_summary
                            ),
                            "summary_version": conversation_bundle.summary_version,
                            "estimated_tokens": conversation_bundle.token_estimate,
                            "budget_tokens": conversation_bundle.budget,
                            "budget_ratio": (
                                conversation_bundle.token_estimate
                                / max(1, conversation_bundle.budget)
                            ),
                            "trimmed": conversation_bundle.context_trimmed,
                            "compaction_count": compaction_count,
                            "summary_refresh_status": (
                                "queued"
                                if (
                                    self.session_compaction is not None
                                    and session.memory_enabled
                                )
                                else "disabled"
                            ),
                            "cache_status": conversation_bundle.cache_status,
                            "build_latency_ms": (
                                conversation_bundle.build_latency_ms
                            ),
                        }
                result_payload = result.model_dump(mode="json")
                if context_usage:
                    result_payload["context_usage"] = context_usage
                task.result_content = result_payload

                for artifact in result.artifacts:
                    db.add(
                        ArtifactModel(
                            id=artifact.artifact_id,
                            task_id=task.id,
                            artifact_type=artifact.artifact_type.value,
                            version=artifact.version,
                            content=artifact.content,
                            confidence=artifact.confidence,
                            created_at=artifact.created_at,
                        )
                    )
                    await append_task_event(
                        db,
                        task.id,
                        AgentEventType.ARTIFACT_CREATED,
                        agent_id=task.agent_id,
                        data={"artifact_id": artifact.artifact_id},
                    )

                db.add(
                    AgentRunModel(
                        task_id=task.id,
                        agent_id=task.agent_id,
                        provider=result.provider,
                        status=result.status.value,
                        latency_ms=total_latency_ms,
                        model_calls=result.metrics.model_calls,
                        tool_calls=result.metrics.tool_calls,
                        retrieval_calls=result.metrics.retrieval_calls,
                        trace_id=result.trace_id or result.request_id or None,
                        metrics_data=result.metrics.model_dump(mode="json"),
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                )
                await append_task_event(
                    db,
                    task.id,
                    AgentEventType.AGENT_OUTPUT,
                    agent_id=task.agent_id,
                    data={
                        "provider": result.provider,
                        "mock": result.provider == "mock",
                        "scene": agent_definition.scene,
                        "mode": agent_definition.mode,
                        "course": request.course_id,
                        "intent": request.intent.value,
                        "route_source": routing.get("route_source", "local_fast"),
                        "route_confidence": routing.get("route_confidence", 1.0),
                        "target_agent_id": agent_id,
                        "fallback_used": routing.get("fallback_used", False),
                    },
                )
                await append_task_event(
                    db,
                    task.id,
                    AgentEventType.TASK_COMPLETED,
                    agent_id=task.agent_id,
                    data={
                        "artifact_count": len(result.artifacts),
                        "latency_ms": total_latency_ms,
                    },
                )
                await db.commit()
                if self.session_compaction is not None:
                    self._schedule_memory_summary(task.id, task.session_id)
        except ProviderCancelledError as exc:
            await self._cancel_after_exception(task_id, exc.message)
        except asyncio.CancelledError:
            await self._fail_after_exception(
                task_id, "进程内任务因应用关闭而中断", "runner_shutdown"
            )
            raise
        except Exception as exc:
            logger.exception(
                "task_runner_unhandled task_id=%s error_type=%s",
                task_id,
                type(exc).__name__,
            )
            message = exc.message if isinstance(exc, AppError) else "后台任务执行失败"
            code = exc.code if isinstance(exc, AppError) else "background_task_error"
            await self._fail_after_exception(task_id, message, code)

    def _schedule_memory_summary(self, task_id: str, session_id: str) -> None:
        existing = self._post_tasks.get(task_id)
        if existing is not None and not existing.done():
            return
        background = asyncio.create_task(
            self._summarize_completed_task(task_id, session_id),
            name=f"xzd-memory-{task_id}",
        )
        self._post_tasks[task_id] = background
        background.add_done_callback(lambda _: self._post_tasks.pop(task_id, None))

    async def _summarize_completed_task(
        self, task_id: str, session_id: str
    ) -> None:
        if self.session_compaction is None:
            return
        lock = self._summary_locks.setdefault(session_id, asyncio.Lock())
        try:
            async with lock:
                async with self.session_factory() as db:
                    task = await TaskRepository(db).get(task_id)
                    if task is None or task.status != TaskStatus.COMPLETED:
                        return
                    session = await SessionRepository(db).get_for_user(
                        session_id, task.user_id, for_update=True
                    )
                    if session is None:
                        return
                    summary, latency_ms = (
                        await self.session_compaction.summarize_completed_turn(
                            db,
                            session=session,
                            source_task_id=task_id,
                        )
                    )
                    payload = dict(task.result_content or {})
                    usage = dict(payload.get("context_usage") or {})
                    usage.update(
                        {
                            "summary_refresh_status": (
                                "completed"
                                if summary is not None
                                else "not_required"
                            ),
                            "summary_refresh_latency_ms": latency_ms,
                            "generated_summary_version": (
                                summary.version if summary is not None else 0
                            ),
                            "summary_generation_method": (
                                summary.generation_method
                                if summary is not None
                                else ""
                            ),
                        }
                    )
                    payload["context_usage"] = usage
                    task.result_content = payload
                    await db.commit()
        except Exception:
            logger.warning(
                "post_answer_memory_degraded task_id=%s",
                task_id,
                exc_info=True,
            )
            await self._mark_summary_refresh_failed(task_id)
        finally:
            if not lock.locked():
                self._summary_locks.pop(session_id, None)

    async def _mark_summary_refresh_failed(self, task_id: str) -> None:
        try:
            async with self.session_factory() as db:
                task = await TaskRepository(db).get(task_id)
                if task is None:
                    return
                payload = dict(task.result_content or {})
                usage = dict(payload.get("context_usage") or {})
                usage["summary_refresh_status"] = "failed"
                payload["context_usage"] = usage
                task.result_content = payload
                await db.commit()
        except Exception:
            logger.warning(
                "summary_refresh_status_update_failed task_id=%s",
                task_id,
                exc_info=True,
            )

    async def _maybe_run_academic_ct_fallback(
        self, result: AgentResult, request: AgentRequest
    ) -> AgentResult:
        """Run the frozen CT cloud baseline only for an explicit graph decision."""

        raw_decision = result.structured_result.get("fallback_decision")
        decision = raw_decision if isinstance(raw_decision, dict) else {}
        if not decision.get("approved"):
            return result
        target = str(
            decision.get("target_agent")
            or result.structured_result.get("fallback_target")
            or ""
        )
        fallback_count = int(decision.get("fallback_count", 0) or 0)
        if fallback_count < 1 or fallback_count > 1:
            return result
        settings = self.knowledge_base.settings
        try:
            fallback_definition = self.agent_registry.get(target)
        except KeyError:
            return result
        if (
            result.agent_id != "ACADEMIC_PROBLEM_SOLVER"
            or request.course_id != "CT"
            or fallback_definition.provider != "xingchen"
            or "CT" not in fallback_definition.course_ids
            or not settings.enable_xingchen_fallback
            or not self._cloud_workflow_allowed(request)
            or self.provider.provider_name != "xingchen"
            or not self.agent_registry.is_runtime_available(target, settings)
        ):
            return result
        try:
            fallback_result = await self.provider.run(
                target, self._cloud_safe_request(request), stream=False
            )
        except AppError as exc:
            return result.model_copy(
                update={
                    "warnings": [
                        *result.warnings,
                        f"CT云端基线回退失败，保留本地条件化结果: {exc.code}",
                    ],
                    "fallback_reason": exc.code,
                    "cloud_status": "cloud_fallback_failed",
                }
            )
        structured = dict(result.structured_result)
        structured.update(
            {
                "status": "success",
                "final_answer": fallback_result.answer,
                "fallback_used": True,
                "fallback_target": target,
                "fallback_result": fallback_result.structured_result,
                "fallback_reason": decision.get("fallback_reason"),
                "fallback_stage": decision.get("fallback_stage"),
                "fallback_count": fallback_count,
            }
        )
        return result.model_copy(
            update={
                "provider": "hybrid",
                "answer": fallback_result.answer,
                "structured_result": structured,
                "business_data": structured,
                "artifacts": [*result.artifacts, *fallback_result.artifacts],
                "citations": fallback_result.citations,
                "warnings": [
                    *result.warnings,
                    *fallback_result.warnings,
                    f"已按CT CoursePack回退到{target}云端基线",
                ],
                "confidence": (
                    fallback_result.confidence
                    if fallback_result.confidence is not None
                    else result.confidence
                ),
                "metrics": result.metrics.model_copy(
                    update={
                        "model_calls": (
                            result.metrics.model_calls
                            + fallback_result.metrics.model_calls
                        ),
                        "provider_latency_ms": (
                            (result.metrics.provider_latency_ms or 0)
                            + (fallback_result.metrics.provider_latency_ms or 0)
                        ),
                        "fallback_count": fallback_count,
                        "route_path": list(
                            (
                                result.structured_result.get(
                                    "solver_observability", {}
                                )
                                or {}
                            ).get("route_path", [])
                        ),
                    }
                ),
                "cloud_status": "cloud_fallback_completed",
                "fallback_used": True,
                "fallback_reason": str(
                    decision.get("fallback_reason") or "high_risk_problem"
                ),
            }
        )

    async def _maybe_run_direct_model_fallback(
        self,
        result: AgentResult,
        request: AgentRequest,
        context: RetrievalContextPacket | None,
    ) -> AgentResult:
        """Replace an unusable solver placeholder with one direct model answer."""

        if (
            self.internal_agents is None
            or not self.internal_agents.available("GENERAL_QUESTION_V1")
            or not self._needs_direct_model_fallback(result)
            or request.options.get("_direct_model_fallback_attempted")
        ):
            return result

        primary_execution = result.structured_result.get("model_execution")
        primary_execution = (
            dict(primary_execution) if isinstance(primary_execution, dict) else {}
        )
        method_reference = (
            context.to_retrieved_context() if context is not None else ""
        )
        options = dict(request.options)
        options["_direct_model_fallback_attempted"] = True
        options["_direct_model_fallback"] = {
            "source_agent": result.agent_id,
            "reason": str(
                primary_execution.get("error_type")
                or primary_execution.get("output_status")
                or "solver_answer_unusable"
            ),
            "method_reference": method_reference[:6000],
        }
        fallback_request = request.model_copy(update={"options": options})
        direct = await self.internal_agents.run(
            "GENERAL_QUESTION_V1",
            fallback_request,
        )
        direct_execution = direct.structured_result.get("model_execution")
        direct_execution = (
            dict(direct_execution) if isinstance(direct_execution, dict) else {}
        )
        direct_completed = (
            str(direct_execution.get("status", "")).casefold() == "success"
            and bool(direct.answer.strip())
        )
        fallback_reason = (
            "academic_generation_direct_model"
            if direct_completed
            else "direct_general_model_unavailable"
        )
        structured = dict(result.structured_result)
        structured.update(
            {
                "status": "completed" if direct_completed else "failed",
                "final_answer": direct.answer,
                "answer_text": direct.answer,
                "primary_model_execution": primary_execution,
                "model_execution": direct_execution,
                "direct_model_fallback": {
                    "attempted": True,
                    "completed": direct_completed,
                    "source_agent": result.agent_id,
                    "target_agent": "GENERAL_QUESTION_V1",
                    "reason": options["_direct_model_fallback"]["reason"],
                },
                "fallback_used": True,
                "fallback_reason": fallback_reason,
            }
        )
        filtered_risks = [
            item
            for item in result.remaining_risks
            if "统一模型服务不可用" not in item
            and "模型输出达到续答上限" not in item
        ]
        return result.model_copy(
            update={
                "provider": direct.provider,
                "answer": direct.answer,
                "structured_result": structured,
                "business_data": structured,
                "artifacts": [*result.artifacts, *direct.artifacts],
                "citations": [],
                "warnings": [*result.warnings, *direct.warnings],
                "remaining_risks": [*filtered_risks, *direct.remaining_risks],
                "metrics": result.metrics.model_copy(
                    update={
                        "provider_latency_ms": self._sum_optional_metrics(
                            result.metrics.provider_latency_ms,
                            direct.metrics.provider_latency_ms,
                        ),
                        "model_calls": (
                            result.metrics.model_calls + direct.metrics.model_calls
                        ),
                        "input_tokens": self._sum_optional_metrics(
                            result.metrics.input_tokens,
                            direct.metrics.input_tokens,
                        ),
                        "output_tokens": self._sum_optional_metrics(
                            result.metrics.output_tokens,
                            direct.metrics.output_tokens,
                        ),
                        "fallback_used": True,
                        "fallback_count": min(
                            2, result.metrics.fallback_count + 1
                        ),
                        "route_path": [
                            *result.metrics.route_path,
                            "GENERAL_QUESTION_V1",
                        ],
                    }
                ),
                "cloud_status": direct.cloud_status,
                "fallback_used": True,
                "fallback_reason": fallback_reason,
            }
        )

    @staticmethod
    def _needs_direct_model_fallback(result: AgentResult) -> bool:
        if result.agent_id != "ACADEMIC_PROBLEM_SOLVER":
            return False
        execution = result.structured_result.get("model_execution")
        if not isinstance(execution, dict):
            return not bool(result.answer.strip())
        status = str(execution.get("status", "")).casefold()
        output_status = str(execution.get("output_status", "")).casefold()
        return status == "failed" or output_status in {"partial", "incomplete"}

    @staticmethod
    def _sum_optional_metrics(
        first: int | None,
        second: int | None,
    ) -> int | None:
        if first is None and second is None:
            return None
        return (first or 0) + (second or 0)

    def _teaching_degraded_result(
        self,
        result: AgentResult,
        request: AgentRequest,
    ) -> AgentResult:
        assert self.teaching_foundation is not None
        try:
            mode = TeachingMode(
                str(
                    request.options.get(
                        "teaching_mode",
                        TeachingMode.DIRECT_ANSWER,
                    )
                )
            )
        except ValueError:
            mode = TeachingMode.DIRECT_ANSWER
        policy = self.teaching_foundation.disclosure.policy(mode)
        structured = dict(result.structured_result)
        structured["teaching"] = {
            "teaching_mode": mode.value,
            "mode_status": "degraded",
            "warning": "学习步骤核对暂时不可用，已保留本次求解结果。",
            "student_attempt_present": isinstance(
                request.options.get("student_attempt"),
                dict,
            ),
            "requires_manual_review": True,
        }
        structured["teaching_loop"] = {
            "version": "v1",
            "status": "degraded",
            "error_type": "teaching_enrichment_unexpected_error",
            "disclosure_policy": policy.model_dump(mode="json"),
        }
        degraded = result.model_copy(
            update={
                "structured_result": structured,
                "warnings": list(
                    dict.fromkeys(
                        [
                            *result.warnings,
                            "学习步骤核对暂时不可用，任务已安全降级。",
                        ]
                    )
                ),
            }
        )
        if mode == TeachingMode.DIRECT_ANSWER:
            return degraded
        filtered, disclosure_ms = self.teaching_foundation.disclosure.apply(
            degraded,
            policy=policy,
            hint=None,
            next_check=None,
            verification=None,
        )
        return filtered.model_copy(
            update={
                "metrics": filtered.metrics.model_copy(
                    update={
                        "teaching_mode": mode.value,
                        "manual_review_required": True,
                        "answer_disclosure_mode": policy.mode.value,
                        "full_solution_disclosed": False,
                        "disclosure_filter_ms": disclosure_ms,
                    }
                )
            }
        )

    def _apply_solver_quality_gate(
        self, result: AgentResult, request: AgentRequest, agent_id: str
    ) -> AgentResult:
        try:
            definition = self.agent_registry.get(agent_id)
        except KeyError:
            return result
        if (
            self.course_registry is None
            or "ACADEMIC_SOLVING" not in definition.task_families
        ):
            return result
        structured = dict(result.structured_result)
        payload = {
            key: value
            for key, value in structured.items()
            if key in SolverResult.model_fields
        }
        payload.setdefault("status", structured.get("status", "partial"))
        payload.setdefault("course", request.course_id)
        payload.setdefault("problem_summary", self._knowledge_query(request)[:500])
        payload.setdefault(
            "final_answer", structured.get("final_answer", result.answer)
        )
        payload.setdefault(
            "execution_path", structured.get("execution_path", "STANDARD")
        )
        try:
            solver_result = SolverResult.model_validate(payload)
        except ValueError:
            return result
        checked = self.solver_quality_gate.evaluate(
            solver_result, self.course_registry.get(request.course_id)
        )
        structured.update(checked.model_dump(mode="json"))
        return result.model_copy(update={"structured_result": structured})

    @classmethod
    def _academic_boundary_preflight(
        cls,
        request: AgentRequest,
        agent_id: str,
    ) -> BoundaryDecision | None:
        if agent_id != "ACADEMIC_PROBLEM_SOLVER":
            return None
        problem = AcademicProblem(
            course=request.course_id,
            problem_text=cls._knowledge_query(request),
            figures_given=[
                {
                    "file_id": item.file_id,
                    "filename": item.filename,
                    "content_type": item.content_type,
                }
                for item in request.attachments
                if item.content_type.startswith("image/")
            ],
        )
        decision = SolverBoundaryPolicy().evaluate(problem)
        if decision.intercepted and not decision.can_continue:
            return decision
        return None

    async def _retrieve_knowledge(
        self,
        request: AgentRequest,
        agent_definition: AgentDefinition,
        execution_plan: AgentExecutionPlan,
    ) -> tuple[RetrievalResult | None, bool]:
        if not self.knowledge_base.settings.knowledge_enabled:
            return None, False
        query = self._knowledge_query(request)
        if not query and not request.attachments:
            return None, False
        plan = execution_plan
        if not plan.use_rag:
            return None, False
        top_k = agent_definition.retrieval_policy.text_top_k
        if top_k <= 0:
            return None, False
        try:
            content_types = agent_definition.knowledge_content_types
            image: bytes | None = None
            if request.attachments:
                attachment = request.attachments[0]
                if attachment.content_type.startswith("image/"):
                    image = await StorageService(self.knowledge_base.settings).read(
                        attachment.storage_key
                    )
            if self.rag_retrieval is not None:
                result = await asyncio.to_thread(
                    self.rag_retrieval.search,
                    query_text=query,
                    query_image=image,
                    course_id=request.course_id,
                    intent=request.intent.value,
                    target_agent_id=agent_definition.agent_id,
                    top_k=top_k,
                    content_types=tuple(content_types),
                    include_images=plan.use_images,
                    session_context=str(
                        request.options.get("conversation_summary", "")
                    ),
                    use_reranker=plan.reranker_mode,
                    policy_name=agent_definition.retrieval_policy.policy_name,
                    image_top_k=agent_definition.retrieval_policy.image_top_k,
                    allow_generation_injection=(
                        agent_definition.retrieval_policy.generation_injection
                    ),
                    local_budget_ms=plan.budget.retrieval_p95_target_ms,
                )
                return result, True
            return (
                await asyncio.to_thread(
                    self.knowledge_base.search_result,
                    query,
                    [request.course_id],
                    top_k * 3 if content_types else top_k,
                ),
                True,
            )
        except Exception as exc:
            logger.warning(
                "knowledge_retrieval_failed task_id=%s session_id=%s "
                "course_id=%s error=%s",
                request.task_id,
                request.session_id,
                request.course_id,
                type(exc).__name__,
            )
            return None, True

    @staticmethod
    def _uses_local_retrieval_fallback(
        definition: AgentDefinition,
    ) -> bool:
        return definition.fallback.handler == "local_retrieval_answer"

    def _legacy_provider_available(self, agent_id: str) -> bool:
        settings = self.knowledge_base.settings
        return bool(
            self.provider.provider_name == "xingchen"
            and settings.xingchen_enabled
            and settings.xingchen_api_key.get_secret_value()
            and settings.xingchen_api_secret.get_secret_value()
            and self.agent_registry.resolve_flow_id(agent_id, settings)
        )

    @staticmethod
    def _fallback_trigger(error_code: str) -> str:
        return {
            "xingchen_timeout": "cloud_timeout",
            "provider_timeout": "cloud_timeout",
            "xingchen_response_parse_error": "cloud_parse_error",
            "provider_circuit_open": "open_circuit",
            "not_configured": "not_configured",
        }.get(error_code, "cloud_http_error")

    @classmethod
    def _is_ct_solver_reroute(cls, result: AgentResult, request: AgentRequest) -> bool:
        returned_intent = str(result.structured_result.get("intent", ""))
        if returned_intent == Intent.SOLVE_PROBLEM.value:
            return True
        question = cls._knowledge_query(request)
        return any(
            token in question
            for token in (
                "完整解答",
                "列方程",
                "求数值",
                "计算",
                "求响应",
                "节点电压法",
                "网孔电流法",
            )
        )

    @classmethod
    def _non_cloud_fallback_result(
        cls,
        definition: AgentDefinition,
        request: AgentRequest,
        *,
        reason: str,
        cloud_status: str = "cloud_failed",
    ) -> AgentResult:
        messages = {
            "planned_response": "该工作流尚未发布，当前仅提供规划状态。",
            "manual_review": "该请求需要人工复核，未自动生成业务结论。",
        }
        business_data: dict[str, object] = {}
        if definition.fallback.handler == "static_template":
            answer, business_data = cls._lesson_prep_fallback_template(request)
        else:
            answer = messages.get(
                definition.fallback.handler,
                "当前工作流不可用，且未配置自动降级回答。",
            )
        artifact = Artifact(
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content={
                "answer": answer,
                "fallback_handler": definition.fallback.handler,
                "fallback_reason": reason,
            },
        )
        return AgentResult(
            agent_id=definition.agent_id,
            agent_version=definition.version,
            provider="local",
            course_id=request.course_id,
            intent=request.intent.value,
            answer=answer,
            structured_result={
                "status": "partial",
                "business_data": business_data,
                "fallback_handler": definition.fallback.handler,
            },
            artifacts=[artifact],
            warnings=[f"fallback_used:{definition.fallback.handler}:{reason}"],
            fallback_used=True,
            fallback_reason=reason,
            business_data=business_data,
            cloud_status=cloud_status,
            request_id=str(request.options.get("request_id", request.task_id)),
            task_id=request.task_id,
        )

    def _cloud_workflow_allowed(self, request: AgentRequest) -> bool:
        value = request.options.get(
            "allow_cloud",
            self.knowledge_base.settings.xingchen_workflows_default_enabled,
        )
        return value is True or self.provider.provider_name != "xingchen"

    @classmethod
    def _lesson_prep_fallback_template(
        cls, request: AgentRequest
    ) -> tuple[str, dict[str, object]]:
        topic = cls._knowledge_query(request) or "本次课程主题"
        topic = " ".join(topic.split())[:180]
        course = {
            "CT": "电路理论",
            "AE": "模拟电子技术",
            "DE": "数字电子技术",
        }.get(request.course_id, request.course_id or "当前课程")
        business_data: dict[str, object] = {
            "learning_objectives": [
                "明确本课核心概念、适用条件与常见误区（需教师结合学情细化）",
                "完成一次可观察的概念解释或问题分析活动",
                "通过形成性评价确认学生是否达到本课目标",
            ],
            "prerequisites": ["根据学生已有知识补充先修概念与诊断问题"],
            "lesson_flow": [
                {
                    "stage": "导入与诊断",
                    "duration": "约 5 分钟",
                    "task": "用一个现象或问题了解学生前概念",
                },
                {
                    "stage": "概念建构",
                    "duration": "约 15 分钟",
                    "task": "讲解定义、条件和关键关系",
                },
                {
                    "stage": "示例与练习",
                    "duration": "约 15 分钟",
                    "task": "完成示例、同伴讨论和即时纠错",
                },
                {
                    "stage": "总结与评价",
                    "duration": "约 10 分钟",
                    "task": "回扣目标并完成出口条评价",
                },
            ],
            "activities": [
                "让学生先独立作答，再比较不同解释或解题路径",
                "针对高频误区设计追问，并记录需要二次讲解的知识点",
            ],
            "formative_assessment": [
                "设置一道概念辨析题和一道迁移题",
                "用出口条记录学生结论、理由及仍不确定之处",
            ],
            "homework": (
                "根据课堂达成情况补充分层练习；题量、难度和评分规则由教师确认。"
            ),
            "teacher_notes": [
                "这是云端结果未通过校验时生成的本地可编辑框架，不是已完成教案。",
                "右侧课程资料为检索候选；只有教师核对后才能写入正式教案。",
            ],
        }
        answer = (
            "## 本地教案框架\n\n"
            "> 云端结果未通过格式校验。以下为可编辑的安全后备框架，"
            "不把检索候选资料冒充为已引用依据。\n\n"
            f"- **课程**：{course}\n"
            f"- **主题**：{topic}\n"
            "- **使用方式**：请结合班级学情、课时长度和右侧资料候选继续完善。"
        )
        return answer, business_data

    @staticmethod
    def _with_execution_plan(
        request: AgentRequest, plan: AgentExecutionPlan
    ) -> AgentRequest:
        options = dict(request.options)
        options["_execution_plan"] = plan.model_dump(mode="json")
        return request.model_copy(update={"options": options})

    @staticmethod
    def _with_upstream_elapsed(
        request: AgentRequest,
        runner_started: float,
    ) -> AgentRequest:
        options = dict(request.options)
        options["_upstream_elapsed_seconds"] = max(
            0.0,
            perf_counter() - runner_started,
        )
        return request.model_copy(update={"options": options})

    @staticmethod
    def _with_conversation_context(
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
    def _knowledge_query(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _cloud_safe_request(request: AgentRequest) -> AgentRequest:
        """Never upload unsupported local documents through an image-only contract."""

        images = [
            item
            for item in request.attachments
            if item.content_type.startswith("image/")
        ]
        options = dict(request.options)
        for key in (
            "conversation_context",
            "recent_messages",
            "active_memories",
            "working_state",
        ):
            options.pop(key, None)
        options["conversation_summary"] = str(
            options.get("conversation_summary", "")
        )[:4000]
        options["local_only_attachments"] = [
            {
                "file_id": item.file_id,
                "filename": item.filename,
                "content_type": item.content_type,
            }
            for item in request.attachments
            if not item.content_type.startswith("image/")
        ]
        return request.model_copy(update={"attachments": images, "options": options})

    @classmethod
    def _with_xingchen_context(
        cls, request: AgentRequest, hits: list[KnowledgeHit]
    ) -> AgentRequest:
        question = cls._knowledge_query(request)
        prefix = f"【用户题目】\n{question}\n\n【本地知识库方法参考】\n"
        suffix = (
            "\n【使用约束】\n"
            "本地知识库仅用于方法参考。\n"
            "题目参数、电路连接和参考方向以用户输入为准。\n"
            "不得使用知识库内容覆盖题目事实。\n"
            "信息不足时请条件化作答，并明确说明假设。"
        )
        context_limit = 2000
        blocks: list[str] = []
        used = 0
        limit = int(request.options.get("_knowledge_top_k", 3))
        for index, hit in enumerate(hits[:limit], start=1):
            block = f"{index}. {hit.content.strip()}\n来源：{hit.source_ref}\n\n"
            available = context_limit - used
            if available <= 0:
                break
            blocks.append(block[:available])
            used += min(len(block), available)
        augmented = prefix + "".join(blocks) + suffix
        canonical_input = dict(request.canonical_input)
        for field in ("text", "question", "problem", "query", "prompt"):
            value = canonical_input.get(field)
            if isinstance(value, str) and value.strip():
                canonical_input[field] = augmented
                break
        options = dict(request.options)
        options["xingchen_knowledge_sources"] = [hit.source_ref for hit in hits[:limit]]
        return request.model_copy(
            update={"canonical_input": canonical_input, "options": options}
        )

    @classmethod
    def _with_learning_context(
        cls, request: AgentRequest, packet: RetrievalContextPacket
    ) -> AgentRequest:
        context = packet.to_retrieved_context()
        options = dict(request.options)
        packet_payload = packet.model_dump(mode="json")
        packet_payload["formatted_context"] = context
        options["retrieval_context_packet"] = packet_payload
        options["retrieved_context"] = context
        options.setdefault("request_id", request.task_id)
        options["xingchen_knowledge_sources"] = packet.source_refs
        return request.model_copy(update={"options": options})

    async def _append_retrieval_event(
        self, task_id: str, agent_id: str, course_id: str, hit_count: int
    ) -> None:
        async with self.session_factory() as db:
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_RETRIEVED,
                agent_id=agent_id,
                data={"course_id": course_id, "hit_count": hit_count},
            )
            await db.commit()

    async def _append_cloud_route_event(
        self, task_id: str, decision: RouteDecision
    ) -> None:
        async with self.session_factory() as db:
            await append_task_event(
                db,
                task_id,
                AgentEventType.ROUTE_SELECTED,
                agent_id=decision.agent_id,
                data=decision.model_dump(mode="json"),
            )
            await db.commit()

    async def _append_local_knowledge_events(
        self,
        task_id: str,
        agent_id: str,
        execution: KnowledgeQAExecution,
    ) -> None:
        async with self.session_factory() as db:
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_QUERY_NORMALIZED,
                agent_id=agent_id,
                data={"normalized_query": execution.retrieval.normalized_query},
            )
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_RETRIEVED,
                agent_id=agent_id,
                data={
                    "course_id": execution.context.course_id,
                    "hit_count": len(execution.retrieval.hits),
                    "confidence": execution.retrieval.confidence,
                    "retrieval_mode": execution.retrieval.retrieval_mode,
                },
            )
            await append_task_event(
                db,
                task_id,
                AgentEventType.KNOWLEDGE_CONTEXT_BUILT,
                agent_id=agent_id,
                data={
                    "evidence_count": len(execution.context.evidence),
                    "evidence_status": execution.context.evidence_status,
                    "source_refs": execution.context.source_refs,
                },
            )
            if execution.context.evidence_status in {"insufficient", "failed"}:
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.KNOWLEDGE_INSUFFICIENT,
                    agent_id=agent_id,
                    data={"warnings": execution.context.warnings},
                )
            await append_task_event(
                db,
                task_id,
                AgentEventType.ANSWER_RETRIEVAL_ONLY_CREATED,
                agent_id=agent_id,
                data={"mode": "retrieval_only"},
            )
            await db.commit()

    async def _record_initial_attempt(
        self,
        db: AsyncSession,
        *,
        task: TaskModel,
        request: AgentRequest,
        result: AgentResult,
    ) -> None:
        """Persist explicit student work without copying it into session state."""

        raw_attempt = request.options.get("student_attempt")
        if self.learning_outcome is None or not isinstance(raw_attempt, dict):
            return
        attempt = StudentAttempt.model_validate(raw_attempt)
        structured = result.structured_result
        raw_report = structured.get("verification_report_v1")
        teaching_loop = structured.get("teaching_loop")
        if not isinstance(raw_report, dict) and isinstance(teaching_loop, dict):
            raw_report = teaching_loop.get("verification")
        verification_report = (
            dict(raw_report) if isinstance(raw_report, dict) else {}
        )
        model = await self.student_attempts.create(
            db,
            task=task,
            user_id=task.user_id,
            idempotency_key=f"{task.id}:initial-attempt",
            attempt=attempt,
            teaching_mode=TeachingMode(
                str(
                    request.options.get(
                        "teaching_mode", TeachingMode.DIRECT_ANSWER
                    )
                )
            ),
            # The response hint is generated after this first submission.
            hint_level_used=None,
            full_solution_seen=False,
            verification_report=verification_report,
        )
        packet = structured.get("solution_packet")
        skill_ids = (
            [str(item) for item in packet.get("skill_ids", [])]
            if isinstance(packet, dict)
            else []
        )
        outcome = await self.learning_outcome.process_attempt(
            db,
            task=task,
            attempt=model,
            skill_ids=skill_ids,
        )
        due_retests = await self.learning_outcome.retests.list(
            db,
            user_id=task.user_id,
            status="due",
            offset=0,
            limit=100,
        )
        result.metrics = result.metrics.model_copy(
            update={
                "attempt_sequence": int(model.attempt_sequence or 0),
                "attempt_revision_created": False,
                "due_retest_count": len(due_retests),
                **outcome.metrics,
            }
        )
        result.structured_result["learning_outcome"] = {
            "attempt_id": model.id,
            "attempt_sequence": model.attempt_sequence,
            "mastery_evidence_types": [
                item.evidence_type.value for item in outcome.evidence
            ],
            "retest_plan_ids": [
                item.retest_plan_id for item in outcome.retest_plans
            ],
        }
        await SessionWorkingStateService(db).update_phase3(
            task,
            current_attempt_id=model.id,
            previous_attempt_id=None,
            attempt_sequence=int(model.attempt_sequence or 0),
            feedback_uptake_status=None,
            mastery_evidence_type=(
                outcome.evidence[0].evidence_type.value
                if outcome.evidence
                else None
            ),
            pending_retest_plan_ids=[
                item.retest_plan_id for item in outcome.retest_plans
            ],
        )

    async def _mark_cancelled(
        self, db: AsyncSession, task_id: str, reason: str
    ) -> None:
        task = await TaskRepository(db).get(task_id, for_update=True)
        if task is None:
            return
        now = utc_now()
        task.status = TaskStatus.CANCELLED
        task.completed_at = now
        task.updated_at = now
        task.error_message = reason
        task.failure_category = "cancelled"
        task.lease_expires_at = None
        if task.started_at:
            db.add(
                AgentRunModel(
                    task_id=task.id,
                    agent_id=task.agent_id,
                    provider=self.provider.provider_name,
                    status=TaskStatus.CANCELLED.value,
                    latency_ms=elapsed_ms(task.started_at, now),
                    started_at=task.started_at,
                    completed_at=now,
                )
            )
        await append_task_event(
            db,
            task_id,
            AgentEventType.TASK_CANCELLED,
            agent_id=task.agent_id,
            data={"reason": reason},
        )
        message = await ConversationMessageService(db).append_terminal_failure(
            task,
            status=MessageStatus.CANCELLED,
            reason="任务已取消。",
        )
        task.assistant_message_id = message.id if message is not None else None
        await db.commit()

    async def _cancel_after_exception(self, task_id: str, reason: str) -> None:
        async with self.session_factory() as db:
            await self._mark_cancelled(db, task_id, reason)

    async def _fail_after_exception(
        self, task_id: str, message: str, code: str
    ) -> None:
        async with self.session_factory() as db:
            task = await TaskRepository(db).get(task_id, for_update=True)
            if task is None or task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
            }:
                return
            if task.cancellation_requested:
                await self._mark_cancelled(
                    db,
                    task_id,
                    "任务在后台异常发生前已收到取消请求",
                )
                return
            now = utc_now()
            task.status = TaskStatus.FAILED
            task.error_message = message
            task.failure_category = code
            task.completed_at = now
            task.updated_at = now
            task.heartbeat_at = now
            task.lease_expires_at = None
            db.add(
                AgentRunModel(
                    task_id=task.id,
                    agent_id=task.agent_id,
                    provider=self.provider.provider_name,
                    status=TaskStatus.FAILED.value,
                    latency_ms=(
                        elapsed_ms(task.started_at, now) if task.started_at else None
                    ),
                    started_at=task.started_at,
                    completed_at=now,
                )
            )
            await append_task_event(
                db,
                task.id,
                AgentEventType.TASK_FAILED,
                agent_id=task.agent_id,
                data={"error_code": code},
            )
            message_model = await ConversationMessageService(
                db
            ).append_terminal_failure(
                task,
                status=MessageStatus.FAILED,
                reason=message,
            )
            task.assistant_message_id = (
                message_model.id if message_model is not None else None
            )
            await db.commit()
            logger.warning(
                "task_failed task_id=%s session_id=%s agent_id=%s "
                "provider=%s attempt=%s error_code=%s",
                task.id,
                task.session_id,
                task.agent_id,
                self.provider.provider_name,
                task.attempt,
                code,
            )
