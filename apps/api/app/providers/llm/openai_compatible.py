from __future__ import annotations

import json
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    BadRequestError,
)
from openai import (
    AuthenticationError as OpenAIAuthenticationError,
)
from openai import (
    RateLimitError as OpenAIRateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.contracts import ModelResponse, ModelStreamEvent, ModelUsage
from app.core.config import Settings
from app.core.errors import (
    AuthenticationError,
    ContextLengthExceededError,
    InvalidModelRequestError,
    ModelProviderError,
    ModelTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
    StructuredOutputError,
)
from app.core.redaction import redact_sensitive_text


class OpenAICompatibleProvider:
    provider_name: str

    def __init__(
        self,
        settings: Settings,
        *,
        client: Any | None = None,
    ) -> None:
        self.settings = settings
        self._client = client
        self._owns_client = client is None

    @property
    def api_key(self) -> str:
        raise NotImplementedError

    @property
    def base_url(self) -> str:
        raise NotImplementedError

    @property
    def request_timeout_seconds(self) -> float:
        return self.settings.model_read_timeout_seconds

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key or "not-configured",
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    connect=self.settings.model_connect_timeout_seconds,
                    read=self.request_timeout_seconds,
                    write=self.request_timeout_seconds,
                    pool=self.settings.model_connect_timeout_seconds,
                ),
                max_retries=0,
            )
        return self._client

    async def _create_completion(self, **kwargs: Any) -> Any:
        try:
            return await self._get_client().chat.completions.create(**kwargs)
        except Exception as exc:
            raise self._translate_error(
                exc, model=str(kwargs.get("model", ""))
            ) from exc

    def _response_from_completion(
        self,
        completion: Any,
        *,
        model: str,
        started: float,
        metadata: dict[str, Any] | None = None,
    ) -> ModelResponse:
        try:
            choice = completion.choices[0]
            message = choice.message
            content = message.content or ""
        except (AttributeError, IndexError, TypeError) as exc:
            raise ProviderUnavailableError(
                "模型返回格式无效",
                provider=self.provider_name,
                model=model,
            ) from exc
        reasoning = getattr(message, "reasoning_content", None)
        model_extra = getattr(message, "model_extra", None)
        if reasoning is None and isinstance(model_extra, dict):
            reasoning = model_extra.get("reasoning_content")
        usage = self._usage(getattr(completion, "usage", None))
        extra = getattr(completion, "model_extra", None)
        sid = extra.get("sid") if isinstance(extra, dict) else None
        return ModelResponse(
            provider=self.provider_name,
            model=str(getattr(completion, "model", None) or model),
            content=str(content),
            reasoning_content=str(reasoning) if reasoning else None,
            usage=usage,
            provider_request_id=str(sid or getattr(completion, "id", None) or "")
            or None,
            elapsed_ms=max(0, int((perf_counter() - started) * 1000)),
            finish_reason=str(getattr(choice, "finish_reason", None) or "") or None,
            raw_metadata={
                "reasoning_present": bool(reasoning),
                **(metadata or {}),
            },
        )

    async def _stream_completion(
        self, *, model: str, kwargs: dict[str, Any]
    ) -> AsyncIterator[ModelStreamEvent]:
        try:
            stream = await self._get_client().chat.completions.create(
                **kwargs, stream=True, stream_options={"include_usage": True}
            )
            async for chunk in stream:
                usage = self._usage(getattr(chunk, "usage", None))
                if usage is not None:
                    yield ModelStreamEvent(
                        event_type="usage",
                        metadata=usage.model_dump(exclude_none=True),
                    )
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None)
                model_extra = getattr(delta, "model_extra", None)
                if reasoning is None and isinstance(model_extra, dict):
                    reasoning = model_extra.get("reasoning_content")
                if reasoning:
                    yield ModelStreamEvent(
                        event_type="reasoning_delta",
                        content=None,
                        metadata={"reasoning_present": True},
                    )
                content = getattr(delta, "content", None)
                if content:
                    yield ModelStreamEvent(
                        event_type="content_delta", content=str(content)
                    )
            yield ModelStreamEvent(event_type="completed", metadata={"model": model})
        except Exception as exc:
            translated = self._translate_error(exc, model=model)
            yield ModelStreamEvent(
                event_type="failed",
                metadata={
                    "error_type": translated.code,
                    "error_message": translated.message,
                },
            )

    def _translate_error(self, exc: Exception, *, model: str) -> ModelProviderError:
        common: dict[str, Any] = {"provider": self.provider_name, "model": model}
        if isinstance(exc, OpenAIAuthenticationError):
            auth_message = (
                "讯飞模型 API 鉴权失败，请检查HTTP APIPassword或AK:SK格式"
                if self.provider_name == "iflytek_spark"
                else "百炼模型 API 鉴权失败，请检查API Key和地域"
            )
            return AuthenticationError(
                auth_message,
                **common,
            )
        if isinstance(exc, OpenAIRateLimitError):
            return RateLimitError("模型 API 触发限流", **common)
        if isinstance(exc, APITimeoutError):
            return ModelTimeoutError("模型请求超时", **common)
        if isinstance(exc, APIConnectionError):
            return ProviderUnavailableError("无法连接模型 API", **common)
        status = getattr(exc, "status_code", None)
        message = redact_sensitive_text(exc)
        if isinstance(exc, BadRequestError) or status in {400, 404, 413, 422}:
            if "context" in message.casefold() and "length" in message.casefold():
                return ContextLengthExceededError("模型上下文长度超限", **common)
            invalid_message = (
                "百炼模型请求无效，请检查模型名、Base URL和业务空间"
                if self.provider_name == "dashscope" and status == 404
                else "模型请求参数或模型名称无效"
            )
            return InvalidModelRequestError(
                invalid_message,
                details={
                    "http_status": status,
                    "optional_parameter_error": "enable_thinking" in message.casefold(),
                },
                **common,
            )
        if isinstance(exc, APIStatusError) and status in {502, 503, 504}:
            return ProviderUnavailableError(
                "模型服务暂时不可用",
                details={"http_status": status},
                **common,
            )
        if isinstance(exc, ModelProviderError):
            return exc
        return ProviderUnavailableError(
            "模型调用失败",
            details={"error_type": type(exc).__name__},
            **common,
        )

    @staticmethod
    def _usage(value: Any) -> ModelUsage | None:
        if value is None:
            return None
        return ModelUsage(
            prompt_tokens=getattr(value, "prompt_tokens", None),
            completion_tokens=getattr(value, "completion_tokens", None),
            total_tokens=getattr(value, "total_tokens", None),
        )

    @staticmethod
    def validate_json(
        response: ModelResponse, schema: type[BaseModel] | None
    ) -> ModelResponse:
        text = response.content.strip()
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```")
            text = text.removesuffix("```").strip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                raise StructuredOutputError(
                    "模型未返回合法 JSON 对象",
                    provider=response.provider,
                    model=response.model,
                    details=OpenAICompatibleProvider._structured_details(response),
                ) from None
            try:
                value = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise StructuredOutputError(
                    "模型未返回合法 JSON 对象",
                    provider=response.provider,
                    model=response.model,
                    details=OpenAICompatibleProvider._structured_details(response),
                ) from exc
        if not isinstance(value, dict):
            raise StructuredOutputError(
                "模型 JSON 顶层必须是对象",
                provider=response.provider,
                model=response.model,
                details=OpenAICompatibleProvider._structured_details(response),
            )
        if schema is not None:
            try:
                value = schema.model_validate(value).model_dump(mode="json")
            except ValidationError as exc:
                raise StructuredOutputError(
                    "模型 JSON 不符合业务结构",
                    provider=response.provider,
                    model=response.model,
                    details={
                        **OpenAICompatibleProvider._structured_details(response),
                        "validation_error_count": exc.error_count(),
                        "validation_fields": [
                            {
                                "path": ".".join(str(item) for item in error["loc"]),
                                "type": error["type"],
                            }
                            for error in exc.errors(include_input=False)[:10]
                        ],
                    },
                ) from exc
        return response.model_copy(
            update={"content": json.dumps(value, ensure_ascii=False)}
        )

    @staticmethod
    def _structured_details(response: ModelResponse) -> dict[str, Any]:
        usage = (
            response.usage.model_dump(exclude_none=True)
            if response.usage is not None
            else {}
        )
        return {
            "usage": usage,
            "elapsed_ms": response.elapsed_ms,
            "provider_request_id": response.provider_request_id,
        }

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.close()
            self._client = None
