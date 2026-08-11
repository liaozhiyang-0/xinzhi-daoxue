from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agents import AgentRegistry, TaskRouter
from app.agents.internal import InternalAgentHub
from app.api.v1.health import health as health_endpoint
from app.api.v1.router import api_router
from app.capabilities import default_capability_registry
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, reset_request_id, set_request_id
from app.courses import default_course_registry
from app.database.base import Base
from app.database.session import create_engine_and_session
from app.observability import ModelTracer, TraceStore
from app.orchestrator import GraphFactory, XZDSupervisor
from app.providers.development_mock import DevelopmentMockProvider
from app.providers.factory import get_agent_provider
from app.providers.llm import DashScopeQwenProvider, IflytekSparkProvider
from app.providers.retrieval import create_external_search_service
from app.runtime import (
    RuntimeSubagentDefinition,
    RuntimeSubagentRegistry,
    build_runtime_handler_registry,
)
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
from app.services.task_runner import TaskRunner
from app.services.teaching_execution_planner import TeachingExecutionPlanner
from app.services.teaching_foundation import TeachingFoundationService
from app.services.teaching_interaction import TeachingInteractionService
from app.services.teaching_interaction_runtime import (
    TeachingInteractionRuntimeService,
)
from app.tools import default_tool_registry

logger = logging.getLogger(__name__)
DEBUG_ROOT = Path(__file__).resolve().parent / "static" / "debug"


async def _research_maintenance_loop(
    research_knowledge: ResearchKnowledgeService, interval_seconds: int
) -> None:
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await research_knowledge.maintain()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("research_knowledge_maintenance_failed")


def error_payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


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
    task_router = TaskRouter(agent_registry, app_settings)
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
    course_registry = default_course_registry()
    capability_registry = default_capability_registry()
    skill_registry = SkillRegistry(course_registry, capability_registry)
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
        enabled=app_settings.agent_runtime_teaching_interaction_enabled,
    )
    tool_registry = default_tool_registry()
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
    overall_router = OverallRoutingService(
        internal_agent_hub,
        task_router,
        app_settings,
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
    task_runner = TaskRunner(
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
        scenario_evidence_review=scenario_evidence_review,
        tool_registry=tool_registry,
        runtime_subagent_registry=runtime_subagent_registry,
        runtime_handler_registry=runtime_handler_registry,
        development_mock_provider=development_mock_provider,
    )
    learning_loop = LearningLoopService(
        teaching_interactions=teaching_interactions,
        teaching_interaction_runtime=teaching_interaction_runtime,
        learning_outcome=learning_outcome,
    )
    learning_progress_runtime = LearningProgressRuntimeService(
        learning_loop.execute_phase3_action,
        enabled=app_settings.agent_runtime_learning_progress_enabled,
    )
    learning_loop.learning_progress_runtime = learning_progress_runtime
    task_runtime_services = tuple(
        service
        for service in task_runner.runtime_boundary.business_registry.services()
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
        task_runner.runtime_boundary.business_registry,
        task_runner.runtime_launch_policy,
        lifecycle_enabled=task_runner.runtime_lifecycle.enabled,
        release_registry=task_runner.runtime_canary_release,
        release_authorization_registry=task_runner.runtime_release_authorizations,
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
        )
        task_executor = QueueTaskExecutor(task_queue)
    else:
        task_executor = LocalTaskExecutor(task_runner)
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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = app_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.provider = provider
        app.state.development_mock_provider = development_mock_provider
        app.state.agent_contract_results = {}
        app.state.agent_registry = agent_registry
        app.state.task_router = task_router
        app.state.trace_store = trace_store
        app.state.spark_provider = spark_provider
        app.state.qwen_provider = qwen_provider
        app.state.model_registry = model_registry
        app.state.model_tracer = model_tracer
        app.state.model_service = model_service
        app.state.course_registry = course_registry
        app.state.capability_registry = capability_registry
        app.state.skill_registry = skill_registry
        app.state.error_pool = error_pool
        app.state.solution_packets = solution_packets
        app.state.evidence_packets = evidence_packets
        app.state.teaching_foundation = teaching_foundation
        app.state.teaching_planner = teaching_planner
        app.state.student_verification = student_verification
        app.state.hint_policy = hint_policy
        app.state.next_checks = next_checks
        app.state.answer_disclosure = answer_disclosure
        app.state.teaching_interactions = teaching_interactions
        app.state.teaching_interaction_runtime = teaching_interaction_runtime
        app.state.learning_progress_runtime = learning_progress_runtime
        app.state.tool_registry = tool_registry
        app.state.runtime_subagent_registry = runtime_subagent_registry
        app.state.runtime_handler_registry = runtime_handler_registry
        app.state.runtime_agent_readiness = runtime_agent_readiness
        app.state.graph_factory = graph_factory
        app.state.graph_checkpointer = graph_checkpointer
        app.state.academic_solver = academic_solver
        app.state.storage = storage
        app.state.internal_agent_hub = internal_agent_hub
        app.state.general_question = general_question
        app.state.research_frontier = research_frontier
        app.state.internal_agent_execution = internal_agent_execution
        app.state.supervisor = supervisor
        app.state.knowledge_base = knowledge_base
        app.state.rag_retrieval = rag_retrieval
        app.state.external_search = external_search
        app.state.external_fetcher = external_fetcher
        app.state.research_knowledge = research_knowledge
        app.state.context_service = context_service
        app.state.knowledge_qa = knowledge_qa
        app.state.rag_debug = rag_debug
        app.state.auth_rate_limiter = auth_rate_limiter
        app.state.task_runner = task_runner
        app.state.task_executor = task_executor
        app.state.task_queue = task_queue
        app.state.learning_loop = learning_loop
        app.state.context_budget = context_budget
        app.state.context_cache = context_cache
        app.state.scenario_catalog = scenario_catalog
        app.state.scenario_evidence_review = scenario_evidence_review
        app.state.knowledge_ocr_review_cache = knowledge_ocr_review_cache
        app.state.context_assembly = context_assembly
        app.state.session_compaction = session_compaction
        research_maintenance_task: asyncio.Task[None] | None = None
        deferred_startup_task: asyncio.Task[None] | None = None
        if app_settings.app_env == "test":
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            app.state.rag_warmup = {
                "status": "skipped",
                "reason": "test_environment_or_disabled",
            }
            try:
                recovered_tasks = await task_executor.recover()
            except Exception:
                logger.exception("task_recovery_startup_failed")
                recovered_tasks = 0
            if recovered_tasks:
                logger.info("task_recovery_requeued count=%s", recovered_tasks)
        else:
            # Do not hold the listening socket on optional maintenance, model
            # loading, or recovery.  The UI can render and health checks can
            # pass while these best-effort jobs continue in the background.
            app.state.rag_warmup = {
                "status": "deferred",
                "reason": "fast_startup",
            }

            async def deferred_startup() -> None:
                nonlocal research_maintenance_task
                await asyncio.sleep(0)
                if app_settings.research_knowledge_maintenance_enabled:
                    try:
                        await research_knowledge.maintain()
                    except Exception:
                        logger.exception("research_knowledge_initial_maintenance_failed")
                    research_maintenance_task = asyncio.create_task(
                        _research_maintenance_loop(
                            research_knowledge,
                            app_settings.research_knowledge_maintenance_interval_seconds,
                        ),
                        name="xzd-research-knowledge-maintenance",
                    )
                if app_settings.rag_enabled and app_settings.rag_warmup_on_startup:
                    logger.info("rag_model_warmup_started_deferred")
                    try:
                        warmup = await asyncio.to_thread(rag_retrieval.warmup)
                        app.state.rag_warmup = warmup
                        logger.info(
                            "rag_model_warmup_completed status=%s elapsed_ms=%s "
                            "failed=%s",
                            warmup["status"],
                            warmup["elapsed_ms"],
                            warmup["failed_components"],
                        )
                    except Exception:
                        logger.exception("rag_model_warmup_failed_deferred")
                        app.state.rag_warmup = {
                            "status": "failed",
                            "reason": "deferred_warmup_error",
                        }
                try:
                    recovered_tasks = await task_executor.recover()
                except Exception:
                    logger.exception("task_recovery_startup_failed")
                    recovered_tasks = 0
                if recovered_tasks:
                    logger.info("task_recovery_requeued count=%s", recovered_tasks)

            deferred_startup_task = asyncio.create_task(
                deferred_startup(), name="xzd-deferred-startup"
            )
        yield
        if deferred_startup_task is not None:
            deferred_startup_task.cancel()
            await asyncio.gather(deferred_startup_task, return_exceptions=True)
        if research_maintenance_task is not None:
            research_maintenance_task.cancel()
            await asyncio.gather(research_maintenance_task, return_exceptions=True)
        await task_executor.shutdown()
        await context_cache.close()
        await external_search.close()
        await external_fetcher.close()
        close_provider = getattr(provider, "aclose", None)
        if close_provider is not None:
            await close_provider()
        await model_service.aclose()
        await engine.dispose()

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description=(
            "芯智导学阶段 2.2 API。统一 Agent 注册、快速路由、受控降级与"
            "多星辰工作流共用同一 Provider 调用链。"
        ),
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix="/api/v1")
    app.add_api_route("/health", health_endpoint, methods=["GET"], tags=["health"])
    app.mount("/debug-assets", StaticFiles(directory=DEBUG_ROOT), name="debug-assets")

    @app.get("/", include_in_schema=False)
    async def root_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "home.html")

    @app.get("/debug", include_in_schema=True, tags=["development"])
    async def debug_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "demo.html")

    @app.get("/login", include_in_schema=True, tags=["authentication"])
    async def login_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "login.html")

    @app.get("/admin", include_in_schema=True, tags=["management"])
    async def admin_page() -> FileResponse:
        return FileResponse(
            DEBUG_ROOT / "admin.html",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get("/teacher", include_in_schema=True, tags=["teaching"])
    async def teacher_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "teacher.html")

    @app.get("/debug/rag", include_in_schema=True, tags=["development"])
    async def rag_debug_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "execution.html")

    @app.get("/debug/agents", include_in_schema=True, tags=["development"])
    async def agent_debug_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "agents.html")

    @app.get("/student", include_in_schema=True, tags=["student"])
    async def student_page() -> FileResponse:
        return FileResponse(
            DEBUG_ROOT / "workspace.html",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get("/workspace", include_in_schema=True, tags=["student"])
    async def workspace_page() -> FileResponse:
        return FileResponse(
            DEBUG_ROOT / "workspace.html",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get("/debug/execution", include_in_schema=True, tags=["development"])
    async def execution_debug_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "execution.html")

    @app.get("/system", include_in_schema=True, tags=["system"])
    async def system_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "system.html")

    @app.get("/demo", include_in_schema=True, tags=["development"])
    async def demo_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "demo.html")

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
        request.state.request_id = request_id
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(token)

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(error_payload(exc.code, exc.message, exc.details)),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                error_payload(
                    "validation_error",
                    "请求参数校验失败",
                    {"errors": exc.errors()},
                )
            ),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "unhandled_error request_id=%s error=%s",
            getattr(request.state, "request_id", "-"),
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content=error_payload("internal_error", "服务器内部错误"),
        )

    return app


app = None if os.getenv("XZD_SKIP_DEFAULT_APP") == "1" else create_app()
