from __future__ import annotations

import logging
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
from app.services.academic_solver_service import AcademicProblemSolverService
from app.services.answer_disclosure import AnswerDisclosureService
from app.services.context_assembly import ContextAssemblyService
from app.services.context_budget import ContextBudgetManager
from app.services.context_cache import ContextAssemblyCache
from app.services.error_pool import ErrorPoolRegistry
from app.services.evidence_packet_adapter import EvidencePacketAdapterService
from app.services.general_question_service import GeneralQuestionService
from app.services.hint_policy import HintPolicyService
from app.services.internal_agent_execution import InternalAgentExecutionService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_qa_service import KnowledgeQAService
from app.services.learning_loop import LearningLoopService
from app.services.learning_outcome import LearningOutcomeService
from app.services.model_registry import ModelRegistry
from app.services.model_service import ModelService
from app.services.next_check_question import NextCheckQuestionService
from app.services.rag_debug import RAGDebugService
from app.services.rag_retrieval import RAGRetrievalService
from app.services.rag_runtime import (
    create_image_embedding_provider,
    create_reranker_provider,
    create_text_embedding_provider,
    create_vector_store,
)
from app.services.retrieval_context import (
    EvidenceQualityEvaluator,
    RetrievalContextService,
)
from app.services.session_compaction import SessionCompactionService
from app.services.skill_registry import SkillRegistry
from app.services.solution_packet_adapter import SolutionPacketAdapterService
from app.services.storage import StorageService
from app.services.student_verification import StudentVerificationService
from app.services.task_executor import LocalTaskExecutor
from app.services.task_runner import TaskRunner
from app.services.teaching_execution_planner import TeachingExecutionPlanner
from app.services.teaching_foundation import TeachingFoundationService
from app.services.teaching_interaction import TeachingInteractionService
from app.tools import default_tool_registry

logger = logging.getLogger(__name__)
DEBUG_ROOT = Path(__file__).resolve().parent / "static" / "debug"


def error_payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


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
    tool_registry = default_tool_registry()
    graph_factory = GraphFactory(
        courses=course_registry,
        capabilities=capability_registry,
        tools=tool_registry,
        model_service=model_service,
    )
    storage = StorageService(app_settings)
    academic_solver = AcademicProblemSolverService(
        graph_factory.create("academic_problem_solver"), model_service, storage
    )
    internal_agent_hub = InternalAgentHub(model_service)
    general_question = GeneralQuestionService(model_service)
    internal_agent_execution = InternalAgentExecutionService(
        internal_agent_hub, academic_solver, general_question
    )
    knowledge_base = KnowledgeBaseService(app_settings)
    text_embedding = create_text_embedding_provider(app_settings)
    image_embedding = create_image_embedding_provider(app_settings)
    reranker = create_reranker_provider(app_settings)
    vector_store = create_vector_store(app_settings)
    rag_retrieval = RAGRetrievalService(
        app_settings,
        knowledge_base,
        text_embedding,
        image_embedding,
        reranker,
        vector_store,
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
    )
    learning_loop = LearningLoopService(
        teaching_interactions=teaching_interactions,
        learning_outcome=learning_outcome,
    )
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
        app.state.tool_registry = tool_registry
        app.state.graph_factory = graph_factory
        app.state.academic_solver = academic_solver
        app.state.storage = storage
        app.state.internal_agent_hub = internal_agent_hub
        app.state.general_question = general_question
        app.state.internal_agent_execution = internal_agent_execution
        app.state.supervisor = supervisor
        app.state.knowledge_base = knowledge_base
        app.state.rag_retrieval = rag_retrieval
        app.state.context_service = context_service
        app.state.knowledge_qa = knowledge_qa
        app.state.rag_debug = rag_debug
        app.state.task_runner = task_runner
        app.state.task_executor = task_executor
        app.state.learning_loop = learning_loop
        app.state.context_budget = context_budget
        app.state.context_cache = context_cache
        app.state.context_assembly = context_assembly
        app.state.session_compaction = session_compaction
        if app_settings.app_env == "test":
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        yield
        await task_executor.shutdown()
        await context_cache.close()
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

    @app.get("/debug/rag", include_in_schema=True, tags=["development"])
    async def rag_debug_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "execution.html")

    @app.get("/debug/agents", include_in_schema=True, tags=["development"])
    async def agent_debug_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "agents.html")

    @app.get("/student", include_in_schema=True, tags=["student"])
    async def student_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "workspace.html")

    @app.get("/workspace", include_in_schema=True, tags=["student"])
    async def workspace_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "workspace.html")

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
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(error_payload(exc.code, exc.message, exc.details)),
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


app = create_app()
