from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from app.core.config import Settings
from app.core.errors import StructuredOutputError
from app.providers.llm import IflytekSparkProvider, LLMMessage
from openai import AsyncOpenAI


class FakeCompletions:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response: Any) -> None:
        self.completions = FakeCompletions(response)
        self.chat = SimpleNamespace(completions=self.completions)


def completion(
    content: str = "回答",
    reasoning: str | None = None,
    finish_reason: str = "stop",
) -> Any:
    message = SimpleNamespace(
        content=content,
        reasoning_content=reasoning,
        model_extra={},
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=SimpleNamespace(
            prompt_tokens=2,
            completion_tokens=1,
            total_tokens=3,
        ),
        model="spark-x",
        id="safe-id",
        model_extra={"sid": "spark-sid"},
    )


@pytest.mark.asyncio
async def test_spark_client_uses_openai_compatible_sdk() -> None:
    provider = IflytekSparkProvider(
        Settings(iflytek_spark_api_key="key", _env_file=None)
    )
    client = provider._get_client()

    assert isinstance(client, AsyncOpenAI)
    assert str(client.base_url).rstrip("/") == "https://spark-api-open.xf-yun.com/x2"
    await provider.aclose()


@pytest.mark.asyncio
async def test_spark_provider_uses_unified_response_and_thinking() -> None:
    client = FakeClient(completion(reasoning="internal reasoning"))
    settings = Settings(
        app_env="test",
        iflytek_spark_api_key="test-password",
        _env_file=None,
    )
    provider = IflytekSparkProvider(settings, client=client)

    result = await provider.generate([LLMMessage(role="user", content="问题")])

    assert result.text == "回答"
    assert result.usage["prompt_tokens"] == 2
    assert client.completions.calls[0]["extra_body"] == {"thinking": {"type": "auto"}}
    assert "reasoning_content" not in result.model_dump()


@pytest.mark.asyncio
async def test_spark_json_uses_local_validation() -> None:
    client = FakeClient(completion('{"answer": 42}'))
    provider = IflytekSparkProvider(
        Settings(iflytek_spark_api_key="key", _env_file=None),
        client=client,
    )

    result = await provider.generate_json(
        messages=[{"role": "user", "content": "json"}],
        model="spark-x",
        extra_options={"temperature": 0.2, "max_tokens": 128},
    )

    assert result.content == '{"answer": 42}'
    assert client.completions.calls[0]["messages"][0]["role"] == "system"
    assert client.completions.calls[0]["max_tokens"] == 128


@pytest.mark.asyncio
async def test_spark_structured_error_reports_truncation_metadata() -> None:
    client = FakeClient(completion("{\"answer\":", finish_reason="length"))
    provider = IflytekSparkProvider(
        Settings(iflytek_spark_api_key="key", _env_file=None),
        client=client,
    )

    with pytest.raises(StructuredOutputError) as captured:
        await provider.generate_json(
            messages=[{"role": "user", "content": "json"}],
            model="spark-x",
        )

    assert captured.value.details["finish_reason"] == "length"
    assert captured.value.details["truncated"] is True
    assert captured.value.details["output_chars"] == len('{"answer":')


@pytest.mark.asyncio
async def test_structured_error_keeps_safe_usage_metadata() -> None:
    client = FakeClient(completion("not-json"))
    provider = IflytekSparkProvider(
        Settings(iflytek_spark_api_key="key", _env_file=None),
        client=client,
    )

    with pytest.raises(StructuredOutputError) as captured:
        await provider.generate_json(
            messages=[{"role": "user", "content": "json"}],
            model="spark-x",
        )

    assert captured.value.details["usage"]["total_tokens"] == 3
    assert captured.value.details["provider_request_id"] == "spark-sid"
    assert "not-json" not in str(captured.value.details)
