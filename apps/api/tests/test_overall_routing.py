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
    settings = Settings(
        app_env="development", overall_routing_enabled=True, _env_file=None
    )
    router = TaskRouter(AgentRegistry(), settings)
    request = _request("help me decide how to organize a study project")
    current = router.route(request)
    hub = FakeOverallHub(
        {
            "target_agent_id": "RESEARCH_01_ACADEMIC_SEARCH_V1",
            "intent": "general_qa",
            "course_id": "UNKNOWN",
            "confidence": 0.96,
            "reason": "the user needs a bounded study workflow",
            "reason_codes": ["paper_search"],
            "task_subtype": "academic_search",
        }
    )

    outcome = await OverallRoutingService(hub, router, settings).route(request, current)

    assert outcome.used is True
    assert outcome.decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert outcome.decision.route_revision == 1
    assert outcome.decision.route_trace[-1]["stage"] == "overall_refinement"
    prompt = hub.calls[0]["input_text"]
    assert "help me decide how to organize a study project" in prompt
    assert "RESEARCH_02_ACADEMIC_WRITING_V1" in prompt
    assert hub.calls[0]["max_tokens"] == 160
    assert hub.calls[0]["extra_options"] == {"_allow_route_fallback": False}


@pytest.mark.asyncio
async def test_overall_router_timeout_keeps_deterministic_route() -> None:
    settings = Settings(
        app_env="development",
        overall_routing_enabled=True,
        overall_routing_timeout_seconds=0.01,
        _env_file=None,
    )
    router = TaskRouter(AgentRegistry(), settings)
    request = _request("help me decide how to organize a study project")
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


@pytest.mark.asyncio
async def test_overall_router_skips_decisive_local_route() -> None:
    settings = Settings(
        app_env="development", overall_routing_enabled=True, _env_file=None
    )
    router = TaskRouter(AgentRegistry(), settings)
    request = _request("请解释电容两端电压为什么不能突变")
    current = router.route(request).model_copy(
        update={
            "route_confidence": 0.99,
            "local_confidence": 0.99,
            "route_source": "local_fast",
        }
    )
    hub = FakeOverallHub({})

    outcome = await OverallRoutingService(hub, router, settings).route(
        request, current
    )

    assert outcome.used is False
    assert outcome.decision == current
    assert outcome.metadata["fallback_reason"] == "high_confidence_local_route"
    assert hub.calls == []


@pytest.mark.asyncio
async def test_overall_router_does_not_override_research_continuity() -> None:
    settings = Settings(
        app_env="development", overall_routing_enabled=True, _env_file=None
    )
    router = TaskRouter(AgentRegistry(), settings)
    request = _request("接着提供一些额外的论文信息").model_copy(
        update={
            "options": {
                "previous_agent": "RESEARCH_01_ACADEMIC_SEARCH_V1",
                "previous_answer_summary": "上一轮已经完成科研前沿检索并返回论文证据。",
            }
        }
    )
    current = router.route(request)
    hub = FakeOverallHub(
        {
            "target_agent_id": "RESEARCH_02_ACADEMIC_WRITING_V1",
            "intent": "academic_writing",
            "course_id": "UNKNOWN",
            "confidence": 0.99,
            "reason": "the word paper appears in the follow-up",
        }
    )

    outcome = await OverallRoutingService(hub, router, settings).route(request, current)

    assert outcome.used is False
    assert outcome.decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert outcome.metadata["fallback_reason"] == "high_confidence_local_route"
    assert hub.calls == []


@pytest.mark.asyncio
async def test_overall_router_does_not_override_high_confidence_research() -> None:
    settings = Settings(
        app_env="development", overall_routing_enabled=True, _env_file=None
    )
    router = TaskRouter(AgentRegistry(), settings)
    request = _request("find the latest research papers on flexible electronics")
    current = router.route(request)
    hub = FakeOverallHub(
        {
            "target_agent_id": "RESEARCH_02_ACADEMIC_WRITING_V1",
            "intent": "academic_writing",
            "course_id": "UNKNOWN",
            "confidence": 0.99,
            "reason": "paper appears in the request",
        }
    )

    outcome = await OverallRoutingService(hub, router, settings).route(
        request, current
    )

    assert outcome.used is False
    assert outcome.decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert outcome.decision.intent == "academic_search"
    assert outcome.metadata["fallback_reason"] == "high_confidence_local_route"
    assert hub.calls == []


@pytest.mark.asyncio
async def test_overall_route_alignment_updates_structured_intent() -> None:
    settings = Settings(
        app_env="development", overall_routing_enabled=True, _env_file=None
    )
    router = TaskRouter(AgentRegistry(), settings)
    request = _request("help me decide how to organize a study project")
    current = router.route(request)
    hub = FakeOverallHub(
        {
            "target_agent_id": "RESEARCH_01_ACADEMIC_SEARCH_V1",
            "intent": "general_qa",
            "course_id": "UNKNOWN",
            "confidence": 0.96,
            "reason": "the request needs research evidence",
            "task_subtype": "academic_search",
        }
    )

    outcome = await OverallRoutingService(hub, router, settings).route(
        request, current
    )

    assert outcome.used is True
    assert outcome.decision.intent == "academic_search"
    assert outcome.decision.intent_recognition["intent"] == "academic_search"
    assert outcome.decision.intent_recognition["task_family"] == "research"
    assert outcome.decision.route_mode == "workflow"
