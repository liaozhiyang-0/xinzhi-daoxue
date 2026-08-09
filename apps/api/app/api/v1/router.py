from fastapi import APIRouter

from app.api.v1 import (
    admin,
    agents,
    artifacts,
    auth,
    debug_agents,
    debug_execution,
    debug_rag,
    debug_traces,
    evaluation,
    feedback,
    files,
    health,
    internal_agents,
    knowledge,
    learning,
    memories,
    models,
    orchestration,
    research,
    scenarios,
    sessions,
    tasks,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(health.router)
api_router.include_router(internal_agents.router)
api_router.include_router(agents.router)
api_router.include_router(sessions.router)
api_router.include_router(scenarios.router)
api_router.include_router(tasks.router)
api_router.include_router(files.router)
api_router.include_router(artifacts.router)
api_router.include_router(knowledge.router)
api_router.include_router(learning.router)
api_router.include_router(memories.router)
api_router.include_router(models.router)
api_router.include_router(orchestration.router)
api_router.include_router(research.router)
api_router.include_router(debug_rag.router)
api_router.include_router(debug_agents.router)
api_router.include_router(debug_execution.router)
api_router.include_router(debug_traces.router)
api_router.include_router(evaluation.router)
api_router.include_router(feedback.router)
