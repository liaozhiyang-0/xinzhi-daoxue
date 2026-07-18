from fastapi import APIRouter

from app.api.v1 import (
    agents,
    artifacts,
    debug_agents,
    debug_rag,
    files,
    health,
    knowledge,
    sessions,
    tasks,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(agents.router)
api_router.include_router(sessions.router)
api_router.include_router(tasks.router)
api_router.include_router(files.router)
api_router.include_router(artifacts.router)
api_router.include_router(knowledge.router)
api_router.include_router(debug_rag.router)
api_router.include_router(debug_agents.router)
