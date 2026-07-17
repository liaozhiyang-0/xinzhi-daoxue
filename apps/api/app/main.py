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
from app.api.v1.health import health as health_endpoint
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, reset_request_id, set_request_id
from app.database.base import Base
from app.database.session import create_engine_and_session
from app.providers.factory import get_agent_provider
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_qa_service import KnowledgeQAService
from app.services.retrieval_context import RetrievalContextService
from app.services.task_runner import TaskRunner

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
    provider = get_agent_provider(app_settings)
    agent_registry = AgentRegistry()
    task_router = TaskRouter(agent_registry)
    knowledge_base = KnowledgeBaseService(app_settings)
    context_service = RetrievalContextService(app_settings.knowledge_max_context_chars)
    knowledge_qa = KnowledgeQAService(knowledge_base, context_service)
    task_runner = TaskRunner(
        session_factory,
        provider,
        knowledge_base,
        agent_registry,
        knowledge_qa,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = app_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.provider = provider
        app.state.agent_registry = agent_registry
        app.state.task_router = task_router
        app.state.knowledge_base = knowledge_base
        app.state.task_runner = task_runner
        if app_settings.app_env == "test":
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        yield
        await task_runner.shutdown()
        await engine.dispose()

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description=(
            "芯智导学本地阶段 0—1.5 API。当前仅运行 Mock Provider；"
            "SOLVER_CT 外部 API 尚未发布。"
        ),
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix="/api/v1")
    app.add_api_route("/health", health_endpoint, methods=["GET"], tags=["health"])
    app.mount("/debug-assets", StaticFiles(directory=DEBUG_ROOT), name="debug-assets")

    @app.get("/debug", include_in_schema=True, tags=["development"])
    async def debug_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "index.html")

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
