from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.health import health as health_endpoint
from app.api.v1.observability import observability_metrics
from app.api.v1.router import api_router
from app.core.config import PROJECT_ROOT
from app.core.errors import AppError
from app.core.logging import reset_request_id, set_request_id
from app.dependencies import require_admin

logger = logging.getLogger(__name__)

DEBUG_ROOT = Path(__file__).resolve().parents[1] / "static" / "debug"
REACT_ROOT = DEBUG_ROOT / "react"
QUESTION_BANK_IMAGE_ROOT = PROJECT_ROOT / "evaluation" / "cache" / "storage"
ANALOG_OPAMP_IMAGE_NAME = "模电测试集_图2.1.1_运算放大器电路.jpg"
CASE6_DEMO_IMAGE = (
    PROJECT_ROOT
    / "组员反馈"
    / "组员一反馈"
    / "images"
    / "Q07_analog_instrumentation_amp.png"
)


def error_payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def configure_http_app(app: FastAPI) -> None:
    """Register API routes, static pages, middleware, and error handlers."""

    app.include_router(api_router, prefix="/api/v1")
    app.add_api_route("/health", health_endpoint, methods=["GET"], tags=["health"])
    app.add_api_route(
        "/metrics",
        observability_metrics,
        methods=["GET"],
        tags=["observability"],
        include_in_schema=False,
    )

    @app.get(
        "/debug-assets/question-bank/analog-opamp.jpg",
        include_in_schema=False,
        dependencies=[Depends(require_admin)],
    )
    async def analog_opamp_question_image() -> FileResponse:
        matches = tuple(QUESTION_BANK_IMAGE_ROOT.rglob(ANALOG_OPAMP_IMAGE_NAME))
        if not matches:
            raise HTTPException(status_code=404, detail="本地模电题库图片不存在")
        return FileResponse(
            matches[0],
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.get(
        "/demo-assets/case6-opamp.png",
        include_in_schema=False,
    )
    async def case6_demo_image() -> FileResponse:
        """Serve the reproducible, non-private image used by the AC-01 demo."""

        if not CASE6_DEMO_IMAGE.is_file():
            raise HTTPException(status_code=404, detail="AC-01演示图片不存在")
        return FileResponse(
            CASE6_DEMO_IMAGE,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    app.mount(
        "/debug-assets",
        StaticFiles(directory=DEBUG_ROOT),
        name="debug-assets",
    )
    app.mount(
        "/react-assets",
        StaticFiles(directory=REACT_ROOT, check_dir=False),
        name="react-assets",
    )
    _register_page_routes(app)
    _register_request_middleware(app)
    _register_error_handlers(app)


def _register_page_routes(app: FastAPI) -> None:
    @app.get("/", include_in_schema=False)
    async def root_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "home.html")

    @app.get(
        "/debug",
        include_in_schema=True,
        tags=["development"],
        dependencies=[Depends(require_admin)],
    )
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

    @app.get(
        "/debug/rag",
        include_in_schema=True,
        tags=["development"],
        dependencies=[Depends(require_admin)],
    )
    async def rag_debug_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "rag.html")

    @app.get(
        "/debug/agents",
        include_in_schema=True,
        tags=["development"],
        dependencies=[Depends(require_admin)],
    )
    async def agent_debug_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "agents.html")

    @app.get("/student", include_in_schema=True, tags=["student"])
    async def student_page() -> FileResponse:
        return FileResponse(
            DEBUG_ROOT / "workspace.html",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get("/workspace-legacy", include_in_schema=False, tags=["student"])
    async def legacy_workspace_page() -> FileResponse:
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

    @app.get("/workspace-react", include_in_schema=False, tags=["student"])
    async def react_workspace_page(request: Request) -> RedirectResponse:
        if not (REACT_ROOT / "index.html").exists():
            raise HTTPException(
                status_code=503,
                detail="React Workspace build is not available",
            )
        return _workspace_redirect(request)

    @app.get(
        "/debug/execution",
        include_in_schema=True,
        tags=["development"],
        dependencies=[Depends(require_admin)],
    )
    async def execution_debug_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "execution.html")

    @app.get(
        "/system",
        include_in_schema=True,
        tags=["system"],
        dependencies=[Depends(require_admin)],
    )
    async def system_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "system.html")

    @app.get(
        "/demo",
        include_in_schema=True,
        tags=["development"],
        dependencies=[Depends(require_admin)],
    )
    async def demo_page() -> FileResponse:
        return FileResponse(DEBUG_ROOT / "demo.html")


def _workspace_redirect(request: Request) -> RedirectResponse:
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(url=f"/workspace{query}", status_code=307)


def _register_request_middleware(app: FastAPI) -> None:
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


def _register_error_handlers(app: FastAPI) -> None:
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
        _request: Request,
        exc: RequestValidationError,
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
        request: Request,
        exc: Exception,
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
