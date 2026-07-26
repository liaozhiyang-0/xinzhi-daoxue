from __future__ import annotations

from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any

from pydantic import BaseModel

from app.contracts import (
    ImageInput,
    ModelResponse,
    ModelStreamEvent,
    ProviderHealth,
)
from app.core.config import Settings
from app.core.errors import ProviderNotConfiguredError, UnsupportedModalityError
from app.core.redaction import redact_sensitive_text
from app.providers.llm.base import BaseModelProvider
from app.providers.llm.openai_compatible import OpenAICompatibleProvider


class IflytekSparkProvider(OpenAICompatibleProvider, BaseModelProvider):
    provider_name = "iflytek_spark"

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        super().__init__(settings, client=client)

    @property
    def api_key(self) -> str:
        return (
            self.settings.iflytek_spark_api_key.get_secret_value()
            or self.settings.spark_api_password.get_secret_value()
        )

    @property
    def configured(self) -> bool:
        if self.settings.iflytek_spark_api_key.get_secret_value():
            enabled = self.settings.iflytek_spark_enabled
        else:
            enabled = self.settings.spark_enabled
        return bool(enabled and self.api_key and self.default_model and self.base_url)

    @property
    def default_model(self) -> str:
        if self.settings.iflytek_spark_api_key.get_secret_value():
            return self.settings.iflytek_spark_model
        if self.settings.spark_api_password.get_secret_value():
            return self.settings.spark_model
        return self.settings.iflytek_spark_model

    @property
    def base_url(self) -> str:
        value = (
            self.settings.iflytek_spark_base_url
            if self.settings.iflytek_spark_api_key.get_secret_value()
            else self.settings.spark_base_url
            if self.settings.spark_api_password.get_secret_value()
            else self.settings.iflytek_spark_base_url
        ).rstrip("/")
        return value.removesuffix("/chat/completions")

    @property
    def request_timeout_seconds(self) -> float:
        return self.settings.iflytek_spark_timeout_seconds

    def _ensure_configured(self, model: str) -> None:
        if not self.configured:
            raise ProviderNotConfiguredError(
                "IFLYTEK_SPARK_API_KEY未配置",
                provider=self.provider_name,
                model=model,
            )

    def _thinking(self, options: dict[str, Any]) -> str:
        raw = options.pop("thinking", self.settings.iflytek_spark_thinking_mode)
        if isinstance(raw, dict):
            raw = raw.get("type", self.settings.iflytek_spark_thinking_mode)
        value = str(raw)
        if value not in {"enabled", "disabled", "auto"}:
            value = self.settings.iflytek_spark_thinking_mode
        return value

    async def generate_text(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ModelResponse:
        self._ensure_configured(model)
        options = dict(extra_options or {})
        thinking = self._thinking(options)
        started = perf_counter()
        completion = await self._create_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens or self.settings.iflytek_spark_max_tokens,
            extra_body={"thinking": {"type": thinking}},
            **options,
        )
        return self._response_from_completion(
            completion,
            model=model,
            started=started,
            metadata={"thinking_mode": thinking},
        )

    async def generate_json(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        schema: type[BaseModel] | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ModelResponse:
        options = dict(extra_options or {})
        temperature = float(options.pop("temperature", 0.1))
        max_tokens = int(
            options.pop("max_tokens", self.settings.iflytek_spark_max_tokens)
        )
        guided = [
            {
                "role": "system",
                "content": "只输出一个合法JSON对象，不要使用Markdown代码块。",
            },
            *messages,
        ]
        response = await self.generate_text(
            messages=guided,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_options=options,
        )
        return self.validate_json(response, schema)

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
        del prompt, images, high_resolution, json_mode, extra_options
        raise UnsupportedModalityError(
            "Spark-X2 Provider不支持图片输入",
            provider=self.provider_name,
            model=model,
        )

    async def stream_text(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        extra_options: dict[str, Any] | None = None,
    ) -> AsyncIterator[ModelStreamEvent]:
        self._ensure_configured(model)
        options = dict(extra_options or {})
        thinking = self._thinking(options)
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": options.pop("temperature", 0.2),
            "max_tokens": options.pop(
                "max_tokens", self.settings.iflytek_spark_max_tokens
            ),
            "extra_body": {"thinking": {"type": thinking}},
            **options,
        }
        async for event in self._stream_completion(model=model, kwargs=kwargs):
            yield event

    async def health_check(self) -> ProviderHealth:
        if not self.configured:
            return ProviderHealth(
                provider=self.provider_name,
                configured=False,
                available=False,
                model=self.default_model,
                error_type="unconfigured",
                error_message="IFLYTEK_SPARK_API_KEY未配置",
            )
        started = perf_counter()
        try:
            await self.generate_text(
                messages=[{"role": "user", "content": "只回答：SPARK_OK"}],
                model=self.default_model,
                temperature=0,
                max_tokens=16,
                extra_options={"thinking": "disabled"},
            )
        except Exception as exc:
            return ProviderHealth(
                provider=self.provider_name,
                configured=True,
                available=False,
                model=self.default_model,
                elapsed_ms=max(0, int((perf_counter() - started) * 1000)),
                error_type=type(exc).__name__,
                error_message=redact_sensitive_text(exc),
            )
        return ProviderHealth(
            provider=self.provider_name,
            configured=True,
            available=True,
            model=self.default_model,
            elapsed_ms=max(0, int((perf_counter() - started) * 1000)),
        )
