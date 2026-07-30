from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from app.contracts import (
    ImageInput,
    ModelResponse,
    ModelStreamEvent,
    ModelUsage,
    ProviderHealth,
)
from app.core.config import Settings
from app.core.errors import (
    AuthenticationError,
    ModelTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
    StructuredOutputError,
)
from app.observability import ModelTracer
from app.providers.llm import BaseModelProvider
from app.services.model_registry import ModelRegistry
from app.services.model_service import ModelService
from pydantic import BaseModel


class FakeProvider(BaseModelProvider):
    def __init__(self, name: str, model: str, outcomes: list[Any]) -> None:
        self.provider_name = name
        self._model = model
        self.outcomes = outcomes
        self.calls = 0

    @property
    def configured(self) -> bool:
        return True

    @property
    def default_model(self) -> str:
        return self._model

    async def generate_text(self, **kwargs: Any) -> ModelResponse:
        del kwargs
        self.calls += 1
        value = self.outcomes.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def generate_json(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        schema: type[BaseModel] | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ModelResponse:
        del messages, model, schema, extra_options
        return await self.generate_text()

    async def generate_multimodal(
        self,
        *,
        prompt: str,
        images: list[ImageInput],
        model: str,
        high_resolution: bool = False,
        json_mode: bool = False,
        extra_options: dict[str, Any] | None = None,
    ) -> ModelResponse:
        del prompt, images, model, high_resolution, json_mode, extra_options
        return await self.generate_text()

    async def stream_text(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        extra_options: dict[str, Any] | None = None,
    ) -> AsyncIterator[ModelStreamEvent]:
        del messages, model, extra_options
        yield ModelStreamEvent(event_type="completed")

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.provider_name,
            configured=True,
            available=True,
            model=self.default_model,
        )

    async def aclose(self) -> None:
        return None


def response(
    provider: str, model: str, *, usage: ModelUsage | None = None
) -> ModelResponse:
    return ModelResponse(
        provider=provider,
        model=model,
        content="ok",
        usage=usage,
        elapsed_ms=1,
    )


def service(
    settings: Settings,
    spark: FakeProvider,
    qwen: FakeProvider,
) -> tuple[ModelService, ModelTracer]:
    tracer = ModelTracer()
    return (
        ModelService(
            settings,
            ModelRegistry(settings),
            {"iflytek_spark": spark, "dashscope": qwen},
            tracer,
        ),
        tracer,
    )


def test_registry_loads_models_and_routes() -> None:
    registry = ModelRegistry(Settings(_env_file=None))

    assert set(registry.models) == {
        "spark_reasoner",
        "qwen_vision_primary",
        "qwen_vision_fast",
        "qwen_text_fast",
    }
    assert registry.get_route("knowledge_answer").primary == "spark_reasoner"
    for task_type in (
        "course_classification",
        "intent_classification",
        "query_rewrite",
        "retrieval_keyword_generation",
        "knowledge_answer",
        "general_question_answer",
        "multi_image_summary",
        "academic_problem_solving",
        "lesson_prep",
        "assignment_review",
        "academic_writing",
        "data_analysis_explanation",
    ):
        assert registry.get_route(task_type).primary == "spark_reasoner"
    assert (
        registry.get_route("structured_output_normalization").primary
        == "qwen_text_fast"
    )
    assert registry.get_route("simple_image_understanding").primary.startswith(
        "qwen_vision"
    )
    academic_vision = registry.get_route("academic_image_extraction")
    assert academic_vision.primary == "qwen_vision_primary"
    assert academic_vision.fallback == "qwen_vision_fast"
    assert academic_vision.options["high_resolution"] is True
    assert registry.errors == []


@pytest.mark.asyncio
async def test_rate_limit_retries_once() -> None:
    settings = Settings(model_max_retries=1, _env_file=None)
    spark = FakeProvider(
        "iflytek_spark",
        "spark-x",
        [
            RateLimitError("limited", provider="iflytek_spark", model="spark-x"),
            response("iflytek_spark", "spark-x"),
        ],
    )
    qwen = FakeProvider("dashscope", "qwen3.7-plus", [])
    gateway, tracer = service(settings, spark, qwen)

    result = await gateway.generate_for_task(
        "knowledge_answer", messages=[{"role": "user", "content": "q"}]
    )

    assert result.content == "ok"
    assert spark.calls == 2
    assert [item.retry_count for item in tracer.list()] == [0, 1]


@pytest.mark.asyncio
async def test_authentication_does_not_retry_but_uses_fallback() -> None:
    settings = Settings(model_max_retries=1, _env_file=None)
    spark = FakeProvider(
        "iflytek_spark",
        "spark-x",
        [AuthenticationError("bad key", provider="iflytek_spark", model="spark-x")],
    )
    qwen = FakeProvider(
        "dashscope",
        "qwen3.7-plus",
        [response("dashscope", "qwen3.7-plus")],
    )
    gateway, tracer = service(settings, spark, qwen)

    result = await gateway.generate_for_task("knowledge_answer", messages=[])

    assert result.provider == "dashscope"
    assert spark.calls == 1
    assert qwen.calls == 1
    assert tracer.list()[-1].fallback_used


@pytest.mark.asyncio
async def test_timeout_retries_then_falls_back() -> None:
    timeout = ModelTimeoutError("timeout", provider="iflytek_spark", model="spark-x")
    spark = FakeProvider("iflytek_spark", "spark-x", [timeout, timeout])
    qwen = FakeProvider(
        "dashscope",
        "qwen3.7-plus",
        [response("dashscope", "qwen3.7-plus")],
    )
    gateway, _ = service(Settings(model_max_retries=1, _env_file=None), spark, qwen)

    result = await gateway.generate_for_task("knowledge_answer", messages=[])

    assert result.provider == "dashscope"
    assert spark.calls == 2
    assert qwen.calls == 1


@pytest.mark.asyncio
async def test_structured_output_error_does_not_call_fallback() -> None:
    spark = FakeProvider(
        "iflytek_spark",
        "spark-x",
        [
            StructuredOutputError(
                "invalid schema",
                provider="iflytek_spark",
                model="spark-x",
                details={"usage": {"total_tokens": 20}},
            )
        ],
    )
    qwen = FakeProvider(
        "dashscope",
        "qwen3.7-plus",
        [response("dashscope", "qwen3.7-plus")],
    )
    gateway, _ = service(Settings(model_max_retries=0, _env_file=None), spark, qwen)

    with pytest.raises(StructuredOutputError):
        await gateway.generate_json_for_task("lesson_prep", messages=[])

    assert spark.calls == 1
    assert qwen.calls == 0


@pytest.mark.asyncio
async def test_fallback_response_includes_failed_attempt_usage() -> None:
    spark = FakeProvider(
        "iflytek_spark",
        "spark-x",
        [
            ProviderUnavailableError(
                "temporary",
                provider="iflytek_spark",
                model="spark-x",
                details={
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                    }
                },
            )
        ],
    )
    qwen = FakeProvider(
        "dashscope",
        "qwen3.7-plus",
        [
            response(
                "dashscope",
                "qwen3.7-plus",
                usage=ModelUsage(
                    prompt_tokens=3,
                    completion_tokens=2,
                    total_tokens=5,
                ),
            )
        ],
    )
    gateway, _ = service(Settings(model_max_retries=0, _env_file=None), spark, qwen)

    result = await gateway.generate_for_task("knowledge_answer", messages=[])

    assert result.usage is not None
    assert result.usage.total_tokens == 20
    assert result.raw_metadata["failed_attempt_usage_included"] is True


@pytest.mark.asyncio
async def test_provider_unavailable_opens_short_lived_model_circuit() -> None:
    unavailable = ProviderUnavailableError(
        "temporary",
        provider="iflytek_spark",
        model="spark-x",
    )
    spark = FakeProvider("iflytek_spark", "spark-x", [unavailable])
    qwen = FakeProvider(
        "dashscope",
        "qwen3.7-plus",
        [
            response("dashscope", "qwen3.7-plus"),
            response("dashscope", "qwen3.7-plus"),
        ],
    )
    gateway, _ = service(
        Settings(
            model_max_retries=0,
            model_circuit_failure_threshold=1,
            model_circuit_reset_seconds=300,
            _env_file=None,
        ),
        spark,
        qwen,
    )

    first = await gateway.generate_for_task("knowledge_answer", messages=[])
    second = await gateway.generate_for_task("knowledge_answer", messages=[])

    assert first.provider == second.provider == "dashscope"
    assert spark.calls == 1
    assert qwen.calls == 2
    assert second.raw_metadata["route_fallback_used"] is True
    assert gateway._circuits["spark_reasoner"].state == "open_circuit"


@pytest.mark.asyncio
async def test_preferred_route_alias_reuses_successful_fallback_model() -> None:
    spark = FakeProvider(
        "iflytek_spark",
        "spark-x",
        [AssertionError("preferred fallback must bypass Spark")],
    )
    qwen = FakeProvider(
        "dashscope",
        "qwen3.7-plus",
        [response("dashscope", "qwen3.7-plus")],
    )
    gateway, _ = service(Settings(_env_file=None), spark, qwen)

    result = await gateway.generate_for_task(
        "knowledge_answer",
        messages=[],
        extra_options={
            "_preferred_route_alias": "qwen_text_fast",
            "_allow_route_fallback": False,
        },
    )

    assert result.provider == "dashscope"
    assert spark.calls == 0
    assert qwen.calls == 1


def test_only_provider_availability_failures_trip_model_circuit() -> None:
    assert ModelService._trips_circuit(
        ProviderUnavailableError(
            "temporary",
            provider="iflytek_spark",
            model="spark-x",
        )
    )
    assert ModelService._trips_circuit(
        AuthenticationError(
            "bad key",
            provider="iflytek_spark",
            model="spark-x",
        )
    )
    assert ModelService._trips_circuit(
        ModelTimeoutError(
            "stream budget exhausted",
            provider="iflytek_spark",
            model="spark-x",
            details={"response_transport": "stream"},
        )
    )
    assert not ModelService._trips_circuit(
        ModelTimeoutError(
            "ordinary request timeout",
            provider="iflytek_spark",
            model="spark-x",
        )
    )
    assert not ModelService._trips_circuit(
        RateLimitError(
            "limited",
            provider="iflytek_spark",
            model="spark-x",
        )
    )
