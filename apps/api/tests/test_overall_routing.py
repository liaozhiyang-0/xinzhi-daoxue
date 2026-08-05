import asyncio
from typing import Any

import pytest
from app.agents import AgentRegistry, TaskRouter
from app.agents.internal.contracts import InternalAgentResult
from app.contracts import AgentRequest
from app.core.config import Settings
from app.services.overall_routing import OverallRoutingService


def _request(text: str) -> AgentRequest:
    return AgentRequest.model_validate(
        {
            "session_id": "session-overall-route",
            "user_id": "user-overall-route",
            "scene": "research",
            "course_id": "AUTO",
            "intent": "unknown",
            "canonical_input": {"text": text},
        }
    )


class FakeOverallHub:
    def __init__(self, payload: dict[str, Any], *, delay: float = 0) -> None:
        self.payload = payload
        self.delay = delay
        self.calls: list[dict[str, Any]] = []

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "agent_id": "OVERALL_ROUTER_LOCAL_V1",
                "enabled": True,
                "configured": True,
            }
        ]

    async def run_text(self, agent_id: str, **kwargs: Any) -> InternalAgentResult:
        self.calls.append({"agent_id": agent_id, **kwargs})
        if self.delay:
            await asyncio.sleep(self.delay)
        return InternalAgentResult(
            agent_id=agent_id,
            task_type="overall_routing",
            provider="dashscope",
            model="qwen3.5-flash",
            content="{}",
            structured_result=self.payload,
            prompt_tokens=20,
            completion_tokens=12,
            total_tokens=32,
            elapsed_ms=15,
        )


@pytest.mark.asyncio
async def test_overall_router_uses_original_input_and_candidate_paths() -> None:
    settings = Settings(app_env="development", _env_file=None)
    router = TaskRouter(AgentRegistry(), settings)
    request = _request("find the latest electronics information papers")
    current = router.route(request)
    hub = FakeOverallHub(
        {
            "target_agent_id": "RESEARCH_01_ACADEMIC_SEARCH_V1",
            "intent": "general_qa",
            "course_id": "UNKNOWN",
            "confidence": 0.96,
            "reason": "the user asks to find recent papers",
            "reason_codes": ["paper_search"],
            "task_subtype": "academic_search",
        }
    )

    outcome = await OverallRoutingService(hub, router, settings).route(request, current)

    assert outcome.used is True
    assert outcome.decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    prompt = hub.calls[0]["input_text"]
    assert "find the latest electronics information papers" in prompt
    assert "RESEARCH_02_ACADEMIC_WRITING_V1" in prompt
    assert hub.calls[0]["max_tokens"] == 160
    assert hub.calls[0]["extra_options"] == {"_allow_route_fallback": False}


@pytest.mark.asyncio
async def test_overall_router_timeout_keeps_deterministic_route() -> None:
    settings = Settings(
        app_env="development",
        overall_routing_timeout_seconds=0.01,
        _env_file=None,
    )
    router = TaskRouter(AgentRegistry(), settings)
    request = _request("find the latest electronics information papers")
    current = router.route(request)
    hub = FakeOverallHub(
        {
            "target_agent_id": "RESEARCH_01_ACADEMIC_SEARCH_V1",
            "intent": "general_qa",
            "course_id": "UNKNOWN",
            "confidence": 0.96,
            "reason": "paper search",
        },
        delay=0.1,
    )

    outcome = await OverallRoutingService(hub, router, settings).route(request, current)

    assert outcome.used is False
    assert outcome.decision.agent_id == current.agent_id
    assert outcome.metadata["fallback_reason"] == "timeout"
