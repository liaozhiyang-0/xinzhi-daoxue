from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator
from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest
from app.contracts import ImageInput
from app.core.config import Settings
from app.core.errors import (
    InvalidModelRequestError,
    ModelTimeoutError,
    ProviderNotConfiguredError,
)
from app.multimodal import ImageEncoder
from app.providers.llm import DashScopeQwenProvider, IflytekSparkProvider
from app.providers.llm.dashscope_qwen import resolve_dashscope_base_url
from openai import AsyncOpenAI
from PIL import Image


def completion(content: str = "QWEN_OK", model: str = "qwen3.5-flash") -> Any:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, model_extra={}),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=3,
            completion_tokens=2,
            total_tokens=5,
        ),
        model=model,
        id="request-id",
        model_extra={},
    )


class FakeCompletions:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class FakeClient:
    def __init__(self, *responses: Any) -> None:
        self.completions = FakeCompletions(list(responses))
        self.chat = SimpleNamespace(completions=self.completions)


def png_data_url() -> str:
    output = BytesIO()
    Image.new("RGB", (8, 6), "white").save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def test_image_encoder_supports_local_paths_and_resizes(tmp_path: Any) -> None:
    path = tmp_path / "large.bmp"
    Image.new("RGB", (512, 128), "white").save(path, format="BMP")
    encoder = ImageEncoder(
        Settings(image_max_long_edge=256, upload_max_image_size_mb=1, _env_file=None)
    )

    result = encoder.encode(ImageInput(source_type="path", value=str(path)))

    assert result.startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_missing_api_keys_fail_only_when_called() -> None:
    spark = IflytekSparkProvider(Settings(_env_file=None), client=FakeClient())
    qwen = DashScopeQwenProvider(Settings(_env_file=None), client=FakeClient())

    assert not spark.configured
    assert not qwen.configured
    with pytest.raises(ProviderNotConfiguredError, match="IFLYTEK_SPARK_API_KEY"):
        await spark.generate_text(messages=[], model="spark-x")
    with pytest.raises(ProviderNotConfiguredError, match="DASHSCOPE_API_KEY"):
        await qwen.generate_text(messages=[], model="qwen3.5-flash")


def test_dashscope_workspace_base_url_resolution() -> None:
    settings = Settings(
        dashscope_base_url="",
        dashscope_workspace_id="workspace-1",
        dashscope_region="cn-beijing",
        _env_file=None,
    )
    assert resolve_dashscope_base_url(settings) == (
        "https://workspace-1.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    )


@pytest.mark.asyncio
async def test_qwen_client_uses_openai_compatible_sdk() -> None:
    provider = DashScopeQwenProvider(Settings(dashscope_api_key="key", _env_file=None))
    client = provider._get_client()

    assert isinstance(client, AsyncOpenAI)
    assert str(client.base_url).rstrip("/") == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    await provider.aclose()


@pytest.mark.asyncio
async def test_qwen_retries_once_without_optional_thinking_parameter() -> None:
    optional_error = InvalidModelRequestError(
        "unsupported enable_thinking",
        provider="dashscope",
        model="qwen3.5-flash",
        details={"optional_parameter_error": True},
    )
    client = FakeClient(optional_error, completion())
    provider = DashScopeQwenProvider(
        Settings(dashscope_api_key="key", _env_file=None),
        client=client,
    )

    result = await provider.generate_text(
        messages=[{"role": "user", "content": "test"}],
        model="qwen3.5-flash",
    )

    assert result.content == "QWEN_OK"
    assert len(client.completions.calls) == 2
    assert "enable_thinking" not in client.completions.calls[1]["extra_body"]


@pytest.mark.asyncio
async def test_qwen_text_and_json_calls() -> None:
    client = FakeClient(completion(), completion('{"intent":"solve"}'))
    provider = DashScopeQwenProvider(
        Settings(dashscope_api_key="key", _env_file=None),
        client=client,
    )

    text = await provider.generate_text(
        messages=[{"role": "user", "content": "test"}],
        model="qwen3.5-flash",
    )
    structured = await provider.generate_json(
        messages=[{"role": "user", "content": "json"}],
        model="qwen3.5-flash",
        extra_options={"temperature": 0.2, "max_tokens": 128},
    )

    assert text.content == "QWEN_OK"
    assert structured.content == '{"intent": "solve"}'
    assert client.completions.calls[0]["extra_body"] == {"enable_thinking": False}
    assert client.completions.calls[1]["response_format"] == {"type": "json_object"}
    assert client.completions.calls[1]["max_tokens"] == 128


@pytest.mark.asyncio
async def test_qwen_single_and_multi_image_preserve_order_and_resolution() -> None:
    client = FakeClient(completion(model="qwen3.6-flash"), completion())
    provider = DashScopeQwenProvider(
        Settings(dashscope_api_key="key", _env_file=None),
        client=client,
    )
    image = ImageInput(source_type="base64", value=png_data_url())

    single = await provider.generate_multimodal(
        prompt="describe",
        images=[image],
        model="qwen3.6-flash",
    )
    multi = await provider.generate_multimodal(
        prompt="compare",
        images=[image, image],
        model="qwen3.8-max",
        high_resolution=True,
    )

    first_content = client.completions.calls[0]["messages"][0]["content"]
    second_content = client.completions.calls[1]["messages"][0]["content"]
    assert [item["type"] for item in first_content] == ["image_url", "text"]
    assert [item["type"] for item in second_content] == [
        "image_url",
        "image_url",
        "text",
    ]
    assert (
        client.completions.calls[1]["extra_body"]["vl_high_resolution_images"] is True
    )
    assert single.raw_metadata["image_count"] == 1
    assert multi.raw_metadata["image_count"] == 2


class FakeStream:
    def __init__(self, chunks: list[Any]) -> None:
        self.chunks = chunks

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[Any]:
        for chunk in self.chunks:
            yield chunk


class SlowStream:
    def __aiter__(self) -> AsyncIterator[Any]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[Any]:
        await asyncio.sleep(1)
        if False:
            yield None


@pytest.mark.asyncio
async def test_spark_stream_hides_reasoning_content() -> None:
    reasoning_delta = SimpleNamespace(
        reasoning_content="hidden",
        content=None,
        model_extra={},
    )
    content_delta = SimpleNamespace(
        reasoning_content=None,
        content="final",
        model_extra={},
    )
    stream = FakeStream(
        [
            SimpleNamespace(
                choices=[SimpleNamespace(delta=reasoning_delta)], usage=None
            ),
            SimpleNamespace(choices=[SimpleNamespace(delta=content_delta)], usage=None),
        ]
    )
    provider = IflytekSparkProvider(
        Settings(iflytek_spark_api_key="key", _env_file=None),
        client=FakeClient(stream),
    )

    events = [
        event
        async for event in provider.stream_text(
            messages=[{"role": "user", "content": "test"}],
            model="spark-x",
        )
    ]

    assert [event.event_type for event in events] == [
        "reasoning_delta",
        "content_delta",
        "completed",
    ]
    assert events[0].content is None
    assert events[1].content == "final"


@pytest.mark.asyncio
async def test_spark_generate_text_can_collect_streaming_response() -> None:
    reasoning_delta = SimpleNamespace(
        reasoning_content="hidden",
        content=None,
        model_extra={},
    )
    content_delta = SimpleNamespace(
        reasoning_content=None,
        content="final",
        model_extra={},
    )
    stream = FakeStream(
        [
            SimpleNamespace(
                id="stream-request-id",
                model="spark-x",
                model_extra={"sid": "stream-sid"},
                choices=[
                    SimpleNamespace(delta=reasoning_delta, finish_reason=None)
                ],
                usage=None,
            ),
            SimpleNamespace(
                id="stream-request-id",
                model="spark-x",
                model_extra={"sid": "stream-sid"},
                choices=[
                    SimpleNamespace(delta=content_delta, finish_reason="stop")
                ],
                usage=None,
            ),
            SimpleNamespace(
                id="stream-request-id",
                model="spark-x",
                model_extra={"sid": "stream-sid"},
                choices=[],
                usage=SimpleNamespace(
                    prompt_tokens=3,
                    completion_tokens=2,
                    total_tokens=5,
                ),
            ),
        ]
    )
    client = FakeClient(stream)
    provider = IflytekSparkProvider(
        Settings(iflytek_spark_api_key="key", _env_file=None),
        client=client,
    )

    response = await provider.generate_text(
        messages=[{"role": "user", "content": "test"}],
        model="spark-x",
        extra_options={
            "spark_response_transport": "stream",
            "spark_stream_total_timeout_seconds": 30,
        },
    )

    assert response.content == "final"
    assert response.reasoning_content is None
    assert response.finish_reason == "stop"
    assert response.provider_request_id == "stream-sid"
    assert response.usage is not None
    assert response.usage.total_tokens == 5
    assert response.raw_metadata["reasoning_present"] is True
    assert response.raw_metadata["response_transport"] == "stream"
    assert response.raw_metadata["stream_chunk_count"] == 3
    assert client.completions.calls[0]["stream"] is True
    assert client.completions.calls[0]["stream_options"] == {
        "include_usage": True
    }


@pytest.mark.asyncio
async def test_spark_collected_stream_enforces_total_timeout() -> None:
    provider = IflytekSparkProvider(
        Settings(iflytek_spark_api_key="key", _env_file=None),
        client=FakeClient(SlowStream()),
    )

    with pytest.raises(ModelTimeoutError) as captured:
        await provider.generate_text(
            messages=[{"role": "user", "content": "test"}],
            model="spark-x",
            extra_options={
                "spark_response_transport": "stream",
                "spark_stream_total_timeout_seconds": 0.01,
            },
        )

    assert captured.value.details["response_transport"] == "stream"
    assert captured.value.details["stream_total_timeout_seconds"] == 0.01
