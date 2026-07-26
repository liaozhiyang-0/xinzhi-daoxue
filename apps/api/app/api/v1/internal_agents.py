from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/internal-agents", tags=["internal-agents"])


@router.get("")
async def list_internal_agents(request: Request) -> dict[str, Any]:
    return {
        "agents": request.app.state.internal_agent_hub.list_agents(),
        "execution_policy": (
            "subordinate_only; existing workflow routing remains unchanged"
        ),
    }
