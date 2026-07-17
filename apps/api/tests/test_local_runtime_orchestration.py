from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents import AgentRegistry, TaskRouter
from app.contracts import (
    AgentRequest,
    AgentResult,
    Artifact,
    AttachmentRef,
    InputMode,
)
from app.contracts.api import SessionCreate
from app.core.config import Settings
from app.database.base import Base
from app.providers.base import AgentProvider
from app.services.session_service import SessionService
from app.services.task_service import CACHE_WARNING, KB_WARNING, TaskService
from app.services.workflow_cache import WorkflowCache


class EmptyKnowledgeBase:
    def search(self, query: str, course_id: str, top_k: int) -> list[Any]:
        del query, course_id, top_k
        return []


class BrokenKnowledgeBase:
    def search(self, query: str, course_id: str, top_k: int) -> list[Any]:
        del query, course_id, top_k
        raise OSError("expected knowledge failure")


class BrokenCache:
    def key(self, *args: Any, **kwargs: Any) -> str:
        del args, kwargs
        return "broken"

    async def get(self, key: str) -> AgentResult | None:
        del key
        raise ConnectionError("expected redis failure")

    async def set(self, key: str, result: AgentResult, ttl_seconds: int) -> None:
        del key, result, ttl_seconds
        raise ConnectionError("expected redis failure")


class MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, AgentResult] = {}

    def key(
        self,
        agent_id: str,
        request: AgentRequest,
        *,
        course_id: str,
        intent: str,
        source_refs: list[str],
    ) -> str:
        return json.dumps(
            [
                agent_id,
                request.canonical_input,
                course_id,
                intent,
                source_refs,
            ],
            ensure_ascii=False,
            sort_keys=True,
        )

    async def get(self, key: str) -> AgentResult | None:
        result = self.values.get(key)
        return result.model_copy(deep=True) if result else None

    async def set(self, key: str, result: AgentResult, ttl_seconds: int) -> None:
        del ttl_seconds
        self.values[key] = result.model_copy(deep=True)


class RecordingProvider(AgentProvider):
    provider_name = "recording"

    def __init__(self, fallback_target: str = "SOLVER_CT_V1") -> None:
        self.fallback_target = fallback_target
        self.calls: list[tuple[str, AgentRequest]] = []

    async def run(
        self, agent_id: str, request: AgentRequest, stream: bool = False
    ) -> AgentResult:
        del stream
        self.calls.append((agent_id, request))
        if agent_id == "ROUTER_01_FALLBACK_V1":
            answer = json.dumps(
                {
                    "route_status": "selected",
                    "course_id": "CT",
                    "intent": "solve_problem",
                    "target_agent_id": self.fallback_target,
                    "route_confidence": 0.81,
                    "reason": "test fallback",
                },
                ensure_ascii=False,
            )
            return AgentResult(agent_id=agent_id, provider="recording", answer=answer)
        answer = f"answer from {agent_id}"
        return AgentResult(
            agent_id=agent_id,
            provider="recording",
            answer=answer,
            artifacts=[
                Artifact(
                    owner_id=request.user_id,
                    task_id=request.task_id,
                    course_id=request.course_id,
                    content={"answer": answer},
                )
            ],
        )

    async def cancel(self, run_id: str) -> None:
        del run_id

    async def get_status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "completed"}


@pytest.fixture
async def db(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'runtime.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield session
    await engine.dispose()


def settings(*, cache_enabled: bool = False) -> Settings:
    return Settings(app_env="test", xingchen_cache_enabled=cache_enabled)


def request(
    session_id: str,
    *,
    course_id: str = "CT",
    intent: str = "solve_problem",
    text: str = "求电阻两端电压",
    attachments: list[AttachmentRef] | None = None,
) -> AgentRequest:
    return AgentRequest.model_validate(
        {
            "session_id": session_id,
            "user_id": "runtime-user",
            "course_id": course_id,
            "intent": intent,
            "canonical_input": {"text": text} if text else {},
            "attachments": [
                item.model_dump(mode="json") for item in (attachments or [])
            ],
        }
    )


def test_local_routes_cover_text_image_and_knowledge() -> None:
    router = TaskRouter(AgentRegistry())
    text_request = request("session", course_id="CT", intent="solve_problem")
    assert (
        router.route(text_request, InputMode.TEXT).target_agent_id
        == "SOLVER_CT_V1"
    )

    image = AttachmentRef(
        file_id="image-1",
        filename="circuit.png",
        content_type="image/png",
        size_bytes=8,
        storage_key="local:image/circuit.png",
    )
    image_request = request("session", text="", attachments=[image])
    assert (
        router.route(image_request, InputMode.SINGLE_IMAGE).target_agent_id
        == "SOLVER_CT_V1"
    )

    knowledge_request = request(
        "session", course_id="AE", intent="explain_concept", text="什么是负反馈"
    )
    knowledge_route = router.route(knowledge_request, InputMode.TEXT)
    assert knowledge_route.target_agent_id == "LEARN_01_KNOWLEDGE_QA_V1"
    assert knowledge_route.needs_knowledge is True


@pytest.mark.asyncio
async def test_fuzzy_request_calls_cloud_router_then_one_target(db) -> None:
    session = await SessionService(db).create(
        SessionCreate(user_id="runtime-user", course_id="UNKNOWN")
    )
    provider = RecordingProvider()
    service = TaskService(
        db,
        provider,
        settings=settings(),
        knowledge_base=EmptyKnowledgeBase(),
    )

    task = await service.create_and_run(
        request(
            session.id,
            course_id="UNKNOWN",
            intent="unknown",
            text="这个怎么弄",
        )
    )

    assert task.status.value == "completed"
    assert [agent_id for agent_id, _ in provider.calls] == [
        "ROUTER_01_FALLBACK_V1",
        "SOLVER_CT_V1",
    ]
    assert task.result_content["structured_result"]["route_source"] == (
        "cloud_fallback"
    )


@pytest.mark.asyncio
async def test_cloud_router_cannot_route_to_itself(db) -> None:
    session = await SessionService(db).create(
        SessionCreate(user_id="runtime-user", course_id="UNKNOWN")
    )
    provider = RecordingProvider(fallback_target="ROUTER_01_FALLBACK_V1")
    service = TaskService(
        db,
        provider,
        settings=settings(),
        knowledge_base=EmptyKnowledgeBase(),
    )

    task = await service.create_and_run(
        request(session.id, course_id="UNKNOWN", intent="unknown", text="这个呢")
    )

    assert task.status.value == "failed"
    assert task.result_content["error_code"] == "route_unresolved"
    assert [agent_id for agent_id, _ in provider.calls] == [
        "ROUTER_01_FALLBACK_V1"
    ]


@pytest.mark.asyncio
async def test_knowledge_failure_does_not_block_solver(db) -> None:
    session = await SessionService(db).create(
        SessionCreate(user_id="runtime-user", course_id="CT")
    )
    provider = RecordingProvider()
    service = TaskService(
        db,
        provider,
        settings=settings(),
        knowledge_base=BrokenKnowledgeBase(),
    )

    task = await service.create_and_run(request(session.id))

    assert task.status.value == "completed"
    assert KB_WARNING in task.result_content["warnings"]
    assert [agent_id for agent_id, _ in provider.calls] == ["SOLVER_CT_V1"]


@pytest.mark.asyncio
async def test_redis_failure_does_not_block_provider(db) -> None:
    session = await SessionService(db).create(
        SessionCreate(user_id="runtime-user", course_id="CT")
    )
    provider = RecordingProvider()
    service = TaskService(
        db,
        provider,
        settings=settings(cache_enabled=True),
        knowledge_base=EmptyKnowledgeBase(),
        cache=BrokenCache(),
    )

    task = await service.create_and_run(request(session.id))

    assert task.status.value == "completed"
    assert CACHE_WARNING in task.result_content["warnings"]
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_cache_hit_skips_second_provider_call(db) -> None:
    session = await SessionService(db).create(
        SessionCreate(user_id="runtime-user", course_id="CT")
    )
    provider = RecordingProvider()
    cache = MemoryCache()
    service = TaskService(
        db,
        provider,
        settings=settings(cache_enabled=True),
        knowledge_base=EmptyKnowledgeBase(),
        cache=cache,
    )

    first = await service.create_and_run(request(session.id))
    second = await service.create_and_run(request(session.id))

    assert first.status.value == second.status.value == "completed"
    assert len(provider.calls) == 1
    assert second.result_content["metrics"]["cache_hit"] is True
    assert second.result_content["metrics"]["provider_call"] == "skipped"
    assert first.artifacts[0].id != second.artifacts[0].id


@pytest.mark.asyncio
async def test_follow_up_uses_only_latest_completed_context(db) -> None:
    session = await SessionService(db).create(
        SessionCreate(user_id="runtime-user", course_id="CT")
    )
    provider = RecordingProvider()
    service = TaskService(
        db,
        provider,
        settings=settings(),
        knowledge_base=EmptyKnowledgeBase(),
    )
    await service.create_and_run(request(session.id, text="原始电路题"))

    follow_up = await service.create_and_run(
        request(
            session.id,
            intent="follow_up_question",
            text="为什么这里是负号",
        )
    )

    assert follow_up.status.value == "completed"
    assert follow_up.agent_id == "SOLVER_CT_V1"
    _, captured = provider.calls[-1]
    text = captured.canonical_input["text"]
    assert "【上一次问题】\n原始电路题" in text
    assert "【上一次回答摘要】" in text
    assert "【本次追问】\n为什么这里是负号" in text


@pytest.mark.parametrize(
    ("structured", "answer"),
    [
        ({"answer_text": "专业解题"}, "专业解题"),
        ({"knowledge_summary": "知识讲解"}, "知识讲解"),
        ({}, "自然语言结果"),
    ],
)
def test_agent_result_accepts_three_workflow_result_shapes(
    structured: dict[str, Any], answer: str
) -> None:
    result = AgentResult(
        agent_id="SOLVER_CT_V1",
        provider="xingchen",
        answer=answer,
        structured_result=structured,
    )
    restored = AgentResult.model_validate(result.model_dump(mode="json"))
    assert restored.answer == answer


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_REDIS_INTEGRATION") != "1",
    reason="requires an explicitly enabled local Redis integration run",
)
async def test_workflow_cache_real_redis_round_trip(db) -> None:
    redis_url = os.environ.get("REDIS_INTEGRATION_URL", "redis://localhost:6379/0")
    runtime_settings = Settings(
        app_env="test",
        redis_url=redis_url,
        xingchen_solver_ct_flow_id="cache-test-flow",
    )
    cache = WorkflowCache(runtime_settings, AgentRegistry())
    session = await SessionService(db).create(
        SessionCreate(user_id="runtime-user", course_id="CT")
    )
    cache_request = request(session.id, text="缓存往返测试")
    key = cache.key(
        "SOLVER_CT_V1",
        cache_request,
        course_id="CT",
        intent="solve_problem",
        source_refs=[],
    )
    provider = RecordingProvider()
    service = TaskService(
        db,
        provider,
        settings=runtime_settings,
        knowledge_base=EmptyKnowledgeBase(),
        cache=cache,
    )
    client = Redis.from_url(redis_url)
    try:
        await client.delete(key)
        first = await service.create_and_run(cache_request)
        second = await service.create_and_run(
            request(session.id, text="缓存往返测试")
        )
        assert first.status.value == second.status.value == "completed"
        assert len(provider.calls) == 1
        assert second.result_content["metrics"]["cache_hit"] is True
        assert await client.ttl(key) > 0
    finally:
        await client.delete(key)
        await client.aclose()
