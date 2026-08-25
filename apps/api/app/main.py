from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI

from app.agents import AgentRegistry, TaskRouter
from app.agents.internal import InternalAgentHub
from app.api.http_app import configure_http_app
from app.application import ApplicationContainer
from app.application.tasks import TaskExecutionCoordinator, TaskLeaseManager
from app.bootstrap import (
    ApplicationLifecycleResources,
    build_app_lifespan,
    build_runtime_task_engine,
)
from app.capabilities import default_capability_registry
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.courses import default_course_registry
from app.database.session import create_engine_and_session
from app.infrastructure import build_runtime_handler_registry
from app.observability import ModelTracer, TraceStore
from app.orchestrator import GraphFactory, XZDSupervisor
from app.providers.development_mock import DevelopmentMockProvider
from app.providers.factory import get_agent_provider
from app.providers.llm import DashScopeQwenProvider, IflytekSparkProvider
from app.providers.retrieval import create_external_search_service
from app.runtime import RuntimeSubagentDefinition, RuntimeSubagentRegistry
from app.services.academic_paper_review import AcademicPaperReviewService
from app.services.academic_search_planner import AcademicSearchPlannerService
from app.services.academic_solver_service import AcademicProblemSolverService
from app.services.answer_disclosure import AnswerDisclosureService
from app.services.auth_service import LoginRateLimiter
from app.services.context_assembly import ContextAssemblyService
from app.services.context_budget import ContextBudgetManager
from app.services.context_cache import ContextAssemblyCache
from app.services.error_pool import ErrorPoolRegistry
from app.services.evidence_packet_adapter import EvidencePacketAdapterService
from app.services.external_retrieval import ExternalContentFetcher
from app.services.general_question_service import GeneralQuestionService
from app.services.hint_policy import HintPolicyService
from app.services.internal_agent_execution import InternalAgentExecutionService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_ocr_review_cache import KnowledgeOCRReviewSnapshotCache
from app.services.knowledge_qa_service import KnowledgeQAService
from app.services.learning_loop import LearningLoopService
from app.services.learning_outcome import LearningOutcomeService
from app.services.learning_progress_runtime import (
    LearningProgressRuntimeService,
)
from app.services.model_registry import ModelRegistry
from app.services.model_service import ModelService
from app.services.next_check_question import NextCheckQuestionService
from app.services.overall_routing import OverallRoutingService
from app.services.planner import PlannerService
from app.services.production_execution_manifest import ProductionExecutionManifest
from app.services.rag_debug import RAGDebugService
from app.services.rag_retrieval import RAGRetrievalService
from app.services.rag_runtime import (
    create_image_embedding_provider,
    create_reranker_provider,
    create_text_embedding_provider,
    create_vector_store,
)
from app.services.research_frontier_service import ResearchFrontierService
from app.services.research_knowledge import ResearchKnowledgeService
from app.services.retrieval_context import (
    EvidenceQualityEvaluator,
    RetrievalContextService,
)
from app.services.runtime_agent_readiness import RuntimeAgentReadinessService
from app.services.runtime_capability_descriptor import (
    descriptors_from_learning_loop_services,
    descriptors_from_task_runtime_services,
)
from app.services.scenario_catalog import ScenarioCatalog
from app.services.scenario_evidence_review import ScenarioEvidenceReviewService
from app.services.session_compaction import SessionCompactionService
from app.services.skill_binding import SkillBindingService
from app.services.skill_registry import SkillRegistry
from app.services.solution_packet_adapter import SolutionPacketAdapterService
from app.services.storage import StorageService
from app.services.student_verification import StudentVerificationService
from app.services.task_executor import (
    LocalTaskExecutor,
    QueueTaskExecutor,
    TaskExecutor,
)
from app.services.task_queue import RedisTaskQueue
from app.services.teaching_execution_planner import TeachingExecutionPlanner
from app.services.teaching_foundation import TeachingFoundationService
from app.services.teaching_interaction import TeachingInteractionService
from app.services.teaching_interaction_runtime import (
    TeachingInteractionRuntimeService,
)
from app.tools import default_tool_registry

logger = logging.getLogger(__name__)


def _create_graph_checkpointer(settings: Settings) -> Any:
    if (
        not settings.langgraph_checkpoint_enabled
        or settings.langgraph_checkpoint_backend == "disabled"
    ):
        return None
    try:
        from langgraph.checkpoint.memory import InMemorySaver
    except ImportError:
        logger.warning("langgraph_checkpoint_unavailable")
        return None
    logger.info("langgraph_checkpoint_enabled backend=memory")
    return InMemorySaver()


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings)
    engine, session_factory = create_engine_and_session(
        app_settings.active_database_url
    )
    agent_registry = AgentRegistry()
    provider = get_agent_provider(app_settings, agent_registry)
    development_mock_provider = DevelopmentMockProvider(app_settings, agent_registry)
    trace_store = TraceStore(
        max_records=app_settings.rag_debug_trace_max_records,
        ttl_seconds=int(app_settings.rag_debug_trace_ttl_seconds),
    )
    spark_provider = IflytekSparkProvider(app_settings)
    qwen_provider = DashScopeQwenProvider(app_settings)
    model_registry = ModelRegistry(app_settings)
    model_tracer = ModelTracer()
    model_service = ModelService(
        app_settings,
        model_registry,
        {
            "iflytek_spark": spark_provider,
            "dashscope": qwen_provider,
        },
        model_tracer,
    )
    task_router = TaskRouter(
        agent_registry,
        app_settings,
        model_preflight=model_service.preflight,
    )
    planner = PlannerService()
    course_registry = default_course_registry()
    capability_registry = default_capability_registry()
    skill_registry = SkillRegistry(course_registry, capability_registry)
    planner.configure_skill_registry(skill_registry)
    error_pool = ErrorPoolRegistry()
    solution_packets = SolutionPacketAdapterService(skill_registry)
    evidence_packets = EvidencePacketAdapterService()
    teaching_planner = TeachingExecutionPlanner()
    student_verification = StudentVerificationService()
    hint_policy = HintPolicyService(error_pool, skill_registry)
    next_checks = NextCheckQuestionService()
    answer_disclosure = AnswerDisclosureService()
    teaching_foundation = TeachingFoundationService(
        solution_packets,
        evidence_packets,
        error_pool,
        teaching_planner,
        student_verification,
        hint_policy,
        next_checks,
        answer_disclosure,
    )
    teaching_interactions = TeachingInteractionService(
        student_verification,
        hint_policy,
        next_checks,
        answer_disclosure,
    )
    teaching_interaction_runtime = TeachingInteractionRuntimeService(
        teaching_interactions,
        enabled=True,
    )
    tool_registry = default_tool_registry(
        circuit_render_enabled=app_settings.circuit_visualization_mode != "off"
    )
    graph_checkpointer = _create_graph_checkpointer(app_settings)
    graph_factory = GraphFactory(
        courses=course_registry,
        capabilities=capability_registry,
        tools=tool_registry,
        model_service=model_service,
        checkpointer=graph_checkpointer,
    )
    storage = StorageService(app_settings)
    academic_solver = AcademicProblemSolverService(
        graph_factory.create("academic_problem_solver"), model_service, storage
    )
    internal_agent_hub = InternalAgentHub(model_service)
    academic_paper_review = AcademicPaperReviewService(
        internal_agent_hub, app_settings
    )
    academic_search_planner = AcademicSearchPlannerService(
        internal_agent_hub, app_settings
    )
    general_question = GeneralQuestionService(model_service)
    overall_router = (
        OverallRoutingService(
            internal_agent_hub,
            task_router,
            app_settings,
        )
        if app_settings.planner_mode == "shadow"
        else None
    )
    knowledge_base = KnowledgeBaseService(app_settings)
    text_embedding = create_text_embedding_provider(app_settings)
    image_embedding = create_image_embedding_provider(app_settings)
    reranker = create_reranker_provider(app_settings)
    vector_store = create_vector_store(app_settings)
    research_knowledge = ResearchKnowledgeService(
        app_settings,
        session_factory,
        text_embedding,
        vector_store,
    )
    research_frontier = ResearchFrontierService(
        internal_agent_hub,
        research_knowledge=research_knowledge,
    )
    internal_agent_execution = InternalAgentExecutionService(
        internal_agent_hub,
        academic_solver,
        general_question,
        research_frontier,
        settings=app_settings,
        storage=storage,
    )
    runtime_subagent_registry = RuntimeSubagentRegistry()
    for definition in agent_registry.list_agents():
        if not definition.enabled or definition.provider != "local":
            continue
        runtime_subagent_registry.register(
            RuntimeSubagentDefinition(
                subagent_id=definition.agent_id,
                target_agent_id=definition.agent_id,
                version=definition.version,
                max_timeout_ms=max(
                    100,
                    min(900_000, int(definition.timeout_seconds * 1000)),
                ),
            )
        )
    runtime_handler_registry = build_runtime_handler_registry(
        tool_registry,
        provider,
        internal_agent_execution,
        subagent_registry=runtime_subagent_registry,
    )
    planner.configure_skill_binding_service(
        SkillBindingService(
            skill_registry,
            runtime_handler_registry,
        )
    )
    rag_retrieval = RAGRetrievalService(
        app_settings,
        knowledge_base,
        text_embedding,
        image_embedding,
        reranker,
        vector_store,
    )
    external_search = create_external_search_service(app_settings)
    external_fetcher = ExternalContentFetcher(
        max_bytes=app_settings.external_retrieval_max_content_chars * 8,
    )
    context_service = RetrievalContextService(
        app_settings.knowledge_max_context_chars,
        evaluator=EvidenceQualityEvaluator(
            sufficient_min_score=app_settings.rag_sufficient_min_score,
            partial_min_score=app_settings.rag_partial_min_score,
            sufficient_min_sources=app_settings.rag_sufficient_min_sources,
        ),
    )
    knowledge_qa = KnowledgeQAService(
        knowledge_base,
        context_service,
        rag_retrieval=rag_retrieval,
        model_service=model_service,
    )
    supervisor = XZDSupervisor(
        agent_registry,
        task_router,
        trace_store,
        model_service=model_service,
    )
    context_budget = ContextBudgetManager(app_settings)
    context_cache = ContextAssemblyCache(app_settings)
    scenario_catalog = ScenarioCatalog(app_settings.scenario_catalog_path)
    scenario_evidence_review = ScenarioEvidenceReviewService()
    knowledge_ocr_review_cache = KnowledgeOCRReviewSnapshotCache(app_settings)
    context_assembly = ContextAssemblyService(
        app_settings, context_cache, context_budget
    )
    session_compaction = SessionCompactionService(
        app_settings,
        context_budget,
        None if app_settings.app_env == "test" else model_service,
    )
    learning_outcome = LearningOutcomeService()
    task_leases = TaskLeaseManager(session_factory, app_settings)
    task_engine = build_runtime_task_engine(
        session_factory,
        provider,
        knowledge_base,
        agent_registry,
        knowledge_qa,
        rag_retrieval,
        internal_agent_execution,
        course_registry,
        context_assembly=context_assembly,
        session_compaction=session_compaction,
        teaching_foundation=teaching_foundation,
        learning_outcome=learning_outcome,
        external_search=external_search,
        external_fetcher=external_fetcher,
        external_paper_reviewer=academic_paper_review,
        external_search_planner=academic_search_planner,
        research_frontier=research_frontier,
        research_knowledge=research_knowledge,
        overall_router=overall_router,
        tool_registry=tool_registry,
        runtime_subagent_registry=runtime_subagent_registry,
        runtime_handler_registry=runtime_handler_registry,
        development_mock_provider=development_mock_provider,
        task_leases=task_leases,
    )
    production_manifest = ProductionExecutionManifest.build(
        planner_version=planner.VERSION,
        capability_bindings=planner.capability_bindings.list(),
        tool_registry=tool_registry,
        runtime_handler_registry=runtime_handler_registry,
        business_services=task_engine.runtime_boundary.business_registry.services(),
        provider_mode=provider.provider_name,
    )
    task_engine.bind_manifest(production_manifest)
    planner.bind_manifest(production_manifest)
    context_cache.bind_version_fence(
        runtime_generation=production_manifest.runtime_generation,
        build_id=production_manifest.build_id,
    )
    rag_retrieval.bind_version_fence(
        runtime_generation=production_manifest.runtime_generation,
        build_id=production_manifest.build_id,
    )
    runtime_handler_registry.freeze()
    runtime_subagent_registry.freeze()
    tool_registry.freeze()
    task_leases.bind_manifest(production_manifest)
    task_coordinator = TaskExecutionCoordinator(
        app_settings,
        task_engine,
        task_leases,
    )
    learning_loop = LearningLoopService(
        teaching_interactions=teaching_interactions,
        teaching_interaction_runtime=teaching_interaction_runtime,
        learning_outcome=learning_outcome,
    )
    learning_progress_runtime = LearningProgressRuntimeService(
        learning_loop.execute_phase3_action,
        enabled=True,
    )
    learning_loop.learning_progress_runtime = learning_progress_runtime
    task_runtime_services = tuple(
        service
        for service in task_engine.runtime_boundary.business_registry.services()
        if getattr(service, "agent_id", "") != "*"
    )
    runtime_capability_descriptors = (
        descriptors_from_task_runtime_services(
            task_runtime_services,
            agent_versions={
                definition.agent_id: definition.version
                for definition in agent_registry.list_agents()
            },
        )
        + descriptors_from_learning_loop_services(
            teaching_interaction=teaching_interaction_runtime,
            learning_progress=learning_progress_runtime,
        )
    )
    runtime_agent_readiness = RuntimeAgentReadinessService(
        agent_registry,
        task_engine.runtime_boundary.business_registry,
        task_engine.runtime_launch_policy,
        lifecycle_enabled=task_engine.runtime_lifecycle.enabled,
        release_registry=task_engine.runtime_canary_release,
        release_authorization_registry=task_engine.runtime_release_authorizations,
        handler_registry=runtime_handler_registry,
        capability_descriptors=runtime_capability_descriptors,
    )
    task_queue = None
    task_executor: TaskExecutor
    if app_settings.task_executor_mode == "redis":
        task_queue = RedisTaskQueue(
            app_settings.redis_url,
            queue_name=app_settings.task_queue_name,
            worker_lock_ttl_seconds=app_settings.task_worker_lock_ttl_seconds,
            dead_letter_max_attempts=app_settings.task_queue_dead_letter_max_attempts,
            dead_letter_enabled=app_settings.task_queue_dead_letter_enabled,
        )
        task_executor = QueueTaskExecutor(task_queue)
    else:
        task_executor = LocalTaskExecutor(task_coordinator)
    rag_debug = RAGDebugService(
        app_settings,
        task_router,
        agent_registry,
        provider,
        rag_retrieval,
        context_service,
        knowledge_qa,
    )
    auth_rate_limiter = LoginRateLimiter()

    container = ApplicationContainer(
        settings=app_settings,
        engine=engine,
        session_factory=session_factory,
        provider=provider,
        development_mock_provider=development_mock_provider,
        agent_contract_results={},
        agent_registry=agent_registry,
        task_router=task_router,
        planner=planner,
        production_manifest=production_manifest,
        trace_store=trace_store,
        spark_provider=spark_provider,
        qwen_provider=qwen_provider,
        model_registry=model_registry,
        model_tracer=model_tracer,
        model_service=model_service,
        course_registry=course_registry,
        capability_registry=capability_registry,
        skill_registry=skill_registry,
        error_pool=error_pool,
        solution_packets=solution_packets,
        evidence_packets=evidence_packets,
        teaching_foundation=teaching_foundation,
        teaching_planner=teaching_planner,
        student_verification=student_verification,
        hint_policy=hint_policy,
        next_checks=next_checks,
        answer_disclosure=answer_disclosure,
        teaching_interactions=teaching_interactions,
        teaching_interaction_runtime=teaching_interaction_runtime,
        learning_progress_runtime=learning_progress_runtime,
        tool_registry=tool_registry,
        runtime_subagent_registry=runtime_subagent_registry,
        runtime_handler_registry=runtime_handler_registry,
        runtime_agent_readiness=runtime_agent_readiness,
        graph_factory=graph_factory,
        graph_checkpointer=graph_checkpointer,
        academic_solver=academic_solver,
        storage=storage,
        internal_agent_hub=internal_agent_hub,
        general_question=general_question,
        research_frontier=research_frontier,
        internal_agent_execution=internal_agent_execution,
        supervisor=supervisor,
        knowledge_base=knowledge_base,
        rag_retrieval=rag_retrieval,
        external_search=external_search,
        external_fetcher=external_fetcher,
        research_knowledge=research_knowledge,
        context_service=context_service,
        knowledge_qa=knowledge_qa,
        rag_debug=rag_debug,
        auth_rate_limiter=auth_rate_limiter,
        task_engine=task_engine,
        task_coordinator=task_coordinator,
        task_executor=task_executor,
        task_queue=task_queue,
        learning_loop=learning_loop,
        context_budget=context_budget,
        context_cache=context_cache,
        scenario_catalog=scenario_catalog,
        scenario_evidence_review=scenario_evidence_review,
        knowledge_ocr_review_cache=knowledge_ocr_review_cache,
        context_assembly=context_assembly,
        session_compaction=session_compaction,
    )
    lifespan = build_app_lifespan(
        ApplicationLifecycleResources(
            settings=app_settings,
            engine=engine,
            session_factory=session_factory,
            container=container,
            task_executor=task_executor,
            context_cache=context_cache,
            external_search=external_search,
            external_fetcher=external_fetcher,
            provider=provider,
            model_service=model_service,
            rag_retrieval=rag_retrieval,
            research_knowledge=research_knowledge,
        )
    )



    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description=(
            "芯智导学阶段 2.2 API。统一 Agent 注册、快速路由、受控降级与"
            "本地 Runtime 共用同一执行边界。"
        ),
        lifespan=lifespan,
    )
    configure_http_app(app)


    return app


app = None if os.getenv("XZD_SKIP_DEFAULT_APP") == "1" else create_app()
