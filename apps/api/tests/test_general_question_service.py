from __future__ import annotations

from typing import Any, cast

import pytest
from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, Intent, ModelResponse, ModelUsage
from app.core.config import Settings
from app.services.general_question_service import GeneralQuestionService
from app.services.model_registry import ModelRegistry
from app.services.model_service import ModelService


class FakeGeneralModelService:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def generate_for_task(self, task_type: str, **kwargs: Any) -> ModelResponse:
        self.calls.append({"task_type": task_type, **kwargs})
        return self.responses.pop(0)


class FailingGeneralModelService:
    async def generate_for_task(
        self, task_type: str, **kwargs: Any
    ) -> ModelResponse:
        del task_type, kwargs
        raise RuntimeError("unexpected provider adapter failure")


def response(
    content: str, *, finish_reason: str = "stop", elapsed_ms: int = 25
) -> ModelResponse:
    return ModelResponse(
        provider="iflytek_spark",
        model="spark-x",
        content=content,
        usage=ModelUsage(prompt_tokens=20, completion_tokens=30, total_tokens=50),
        elapsed_ms=elapsed_ms,
        finish_reason=finish_reason,
    )


def request(text: str = "给我梳理一下电路理论课程的框架") -> AgentRequest:
    return AgentRequest(
        task_id="task-general",
        session_id="session-general",
        user_id="student-general",
        scene="dispatch",
        course_id="CT",
        intent="general_qa",
        canonical_input={"text": text},
        options={"request_id": "request-general", "response_depth": "standard"},
    )


def test_low_confidence_text_routes_to_general_question_without_cloud() -> None:
    decision = TaskRouter(AgentRegistry()).route(
        request().model_copy(update={"intent": Intent.UNKNOWN})
    )

    assert decision.agent_id == "GENERAL_QUESTION_V1"
    assert decision.route_status.value == "selected"
    assert decision.intent == "general_qa"
    assert decision.route_source == "local_general_fallback"
    assert decision.provider_required is False
    assert "cloud_router_not_authorized" in decision.reason_codes
    assert "general_question_fallback" in decision.reason_codes


def test_general_question_model_route_prefers_spark() -> None:
    route = ModelRegistry(Settings(_env_file=None)).get_route(
        "general_question_answer"
    )

    assert route.primary == "spark_reasoner"
    assert route.fallback == "qwen_text_fast"


def test_daily_science_question_routes_to_general_question() -> None:
    daily = request(
        "请用不超过150字解释：为什么天空通常看起来是蓝色的？"
        "要求面向高中生，不使用复杂公式。"
    ).model_copy(
        update={
            "course_id": "UNKNOWN",
            "intent": Intent.UNKNOWN,
        }
    )

    decision = TaskRouter(AgentRegistry()).route(daily)

    assert decision.agent_id == "GENERAL_QUESTION_V1"
    assert decision.provider_required is False
    assert decision.retrieval_required is False
    assert decision.cloud_router_invoked is False


@pytest.mark.asyncio
async def test_general_question_returns_model_answer_without_course_citation() -> None:
    fake = FakeGeneralModelService([response("电路理论通常可分为五个学习层次。")])
    service = GeneralQuestionService(cast(ModelService, fake))

    result = await service.run(request())

    assert result.answer == "电路理论通常可分为五个学习层次。"
    assert result.provider == "local_agent"
    assert result.citations == []
    assert result.evidence_status == "not_requested"
    assert result.structured_result["source_policy"] == "no_course_evidence_claimed"
    assert result.metrics.model_calls == 1
    assert fake.calls[0]["task_type"] == "general_question_answer"
    assert fake.calls[0]["extra_options"] == {"max_tokens": 4096}
    system_prompt = fake.calls[0]["messages"][0]["content"]
    assert "日常常识、生活、语言和一般科普问题直接给出简洁答案" in system_prompt
    assert "严格遵守用户提出的字数、受众、语气、格式" in system_prompt


@pytest.mark.asyncio
async def test_general_question_continues_once_after_token_limit() -> None:
    fake = FakeGeneralModelService(
        [
            response("第一部分", finish_reason="length", elapsed_ms=30),
            response("第二部分", finish_reason="stop", elapsed_ms=20),
        ]
    )
    service = GeneralQuestionService(cast(ModelService, fake))

    result = await service.run(request("请完整介绍电路理论"))

    assert result.answer == "第一部分\n\n第二部分"
    assert result.metrics.model_calls == 2
    assert result.metrics.provider_latency_ms == 50
    assert result.metrics.input_tokens == 40
    assert result.metrics.output_tokens == 60
    assert result.structured_result["model_execution"]["output_status"] == "completed"
    assert fake.calls[1]["extra_options"] == {"max_tokens": 2048}


@pytest.mark.asyncio
async def test_general_question_unexpected_error_returns_non_empty_fallback() -> None:
    service = GeneralQuestionService(cast(ModelService, FailingGeneralModelService()))

    result = await service.run(request("请解释一个普通问题"))

    assert result.status.value == "completed"
    assert result.answer
    assert "暂时不可用" in result.answer
    assert result.structured_result["model_execution"]["error_type"] == (
        "general_model_unexpected_error"
    )


@pytest.mark.asyncio
async def test_general_question_empty_response_returns_non_empty_fallback() -> None:
    service = GeneralQuestionService(
        cast(ModelService, FakeGeneralModelService([response("   ")]))
    )

    result = await service.run(request("请解释一个普通问题"))

    assert result.status.value == "completed"
    assert result.answer
    assert result.structured_result["model_execution"]["error_type"] == (
        "general_model_empty_response"
    )


def test_workspace_unknown_task_completes_with_general_module(client, api) -> None:
    fake = FakeGeneralModelService([response("这是可直接展示的通用回答。")])
    client.app.state.general_question.model_service = cast(ModelService, fake)
    session = api.create_session(user_id="student-general-task")
    payload = {
        "session_id": session["id"],
        "user_id": "student-general-task",
        "user_role": "student",
        "scene": "dispatch",
        "course_id": "CT",
        "intent": "unknown",
        "canonical_input": {"text": "给我梳理一下电路理论课程的框架"},
        "options": {
            "request_id": "workspace-general-task",
            "allow_cloud": False,
            "response_depth": "standard",
        },
    }

    created = client.post("/api/v1/tasks", json=payload)
    assert created.status_code == 202
    task = api.wait_for_task(created.json()["id"])

    assert task["status"] == "completed"
    assert task["agent_id"] == "GENERAL_QUESTION_V1"
    assert task["intent"] == "general_qa"
    assert task["result_content"]["answer"] == "这是可直接展示的通用回答。"
    presentation = task["result_content"]["structured_result"]["presentation"]
    assert presentation["source_summary"] == "未使用外部材料"
    assert presentation["fallback_message"] == ""


def test_workspace_general_unexpected_error_still_returns_answer(client, api) -> None:
    client.app.state.general_question.model_service = cast(
        ModelService, FailingGeneralModelService()
    )
    session = api.create_session(user_id="student-general-fallback")
    payload = {
        "session_id": session["id"],
        "user_id": "student-general-fallback",
        "user_role": "student",
        "scene": "dispatch",
        "course_id": "UNKNOWN",
        "intent": "unknown",
        "canonical_input": {"text": "请用一句话说明今天适合先做什么"},
        "options": {
            "request_id": "workspace-general-fallback",
            "allow_cloud": False,
            "response_depth": "brief",
        },
    }

    created = client.post("/api/v1/tasks", json=payload)
    assert created.status_code == 202
    task = api.wait_for_task(created.json()["id"])

    assert task["status"] == "completed"
    assert task["agent_id"] == "GENERAL_QUESTION_V1"
    assert task["result_content"]["answer"]
    execution = task["result_content"]["structured_result"]["model_execution"]
    assert execution["status"] == "failed"
    assert execution["error_type"] == "general_model_unexpected_error"
