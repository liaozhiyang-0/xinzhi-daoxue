from __future__ import annotations

from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel

from app.contracts import (
    ImageInput,
    ModelResponse,
    ModelStreamEvent,
    ProviderHealth,
)
from app.core.config import Settings
from app.core.errors import (
    InvalidModelRequestError,
    ProviderNotConfiguredError,
)
from app.core.redaction import redact_sensitive_text
from app.multimodal import ImageEncoder
from app.providers.llm.base import BaseModelProvider
from app.providers.llm.openai_compatible import OpenAICompatibleProvider

REGION_DOMAINS = {
    "cn-beijing": "cn-beijing.maas.aliyuncs.com",
    "ap-southeast-1": "ap-southeast-1.maas.aliyuncs.com",
    "ap-northeast-1": "ap-northeast-1.maas.aliyuncs.com",
    "eu-central-1": "eu-central-1.maas.aliyuncs.com",
}
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def resolve_dashscope_base_url(settings: Settings) -> str:
    explicit = settings.dashscope_base_url.strip().rstrip("/")
    if explicit:
        result = explicit
    elif settings.dashscope_workspace_id.strip():
        workspace = settings.dashscope_workspace_id.strip()
        domain = REGION_DOMAINS.get(settings.dashscope_region)
        if domain is None:
            raise ValueError("当前地域需要显式配置DASHSCOPE_BASE_URL")
        result = f"https://{workspace}.{domain}/compatible-mode/v1"
    elif settings.dashscope_region == "us-east-1":
        result = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    else:
        result = DEFAULT_DASHSCOPE_BASE_URL
    parsed = urlparse(result)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username:
        raise ValueError("DASHSCOPE_BASE_URL必须是无凭据的HTTPS地址")
    return result


class DashScopeQwenProvider(OpenAICompatibleProvider, BaseModelProvider):
    provider_name = "dashscope"

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        super().__init__(settings, client=client)
        self.image_encoder = ImageEncoder(settings)

    @property
    def api_key(self) -> str:
        return self.settings.dashscope_api_key.get_secret_value()

    @property
    def base_url(self) -> str:
        return resolve_dashscope_base_url(self.settings)

    @property
    def request_timeout_seconds(self) -> float:
        return self.settings.qwen_timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.settings.dashscope_enabled and self.api_key and self.base_url)

    @property
    def default_model(self) -> str:
        return self.settings.qwen_text_fast_model

    def _ensure_configured(self, model: str) -> None:
        if not self.configured:
            raise ProviderNotConfiguredError(
                "DASHSCOPE_API_KEY未配置",
                provider=self.provider_name,
                model=model,
            )

    async def _qwen_completion(self, **kwargs: Any) -> Any:
        try:
            return await self._create_completion(**kwargs)
        except InvalidModelRequestError as exc:
            extra_body = kwargs.get("extra_body")
            optional_error = bool(exc.details.get("optional_parameter_error"))
            if (
                optional_error
                and isinstance(extra_body, dict)
                and "enable_thinking" in extra_body
            ):
                retry_kwargs = dict(kwargs)
                retry_body = dict(extra_body)
                retry_body.pop("enable_thinking", None)
                retry_kwargs["extra_body"] = retry_body
                return await self._create_completion(**retry_kwargs)
            raise

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
        enable_thinking = bool(options.pop("enable_thinking", False))
        started = perf_counter()
        completion = await self._qwen_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens or 2048,
            extra_body={"enable_thinking": enable_thinking},
            **options,
        )
        return self._response_from_completion(
            completion,
            model=model,
            started=started,
            metadata={"thinking_enabled": enable_thinking},
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
        max_tokens = int(options.pop("max_tokens", 2048))
        options = {"response_format": {"type": "json_object"}, **options}
        response = await self.generate_text(
            messages=[
                {
                    "role": "system",
                    "content": "只输出一个合法JSON对象，不要使用Markdown代码块。",
                },
                *messages,
            ],
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
        self._ensure_configured(model)
        if not images:
            raise InvalidModelRequestError(
                "图片任务至少需要一张图片",
                provider=self.provider_name,
                model=model,
            )
        if len(images) > self.settings.upload_max_images:
            message = (
                f"图片数量 {len(images)} 超过项目限制 {self.settings.upload_max_images}"
            )
            raise InvalidModelRequestError(
                message,
                provider=self.provider_name,
                model=model,
            )
        content: list[dict[str, Any]] = [
            {
                "type": "image_url",
                "image_url": {"url": self.image_encoder.encode(image)},
            }
            for image in images
        ]
        content.append({"type": "text", "text": prompt})
        options = dict(extra_options or {})
        enable_thinking = bool(options.pop("enable_thinking", False))
        extra_body = {
            "enable_thinking": enable_thinking,
            "vl_high_resolution_images": high_resolution,
        }
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": options.pop("temperature", 0.1),
            "max_tokens": options.pop("max_tokens", 4096),
            "extra_body": extra_body,
            **options,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        started = perf_counter()
        completion = await self._qwen_completion(**kwargs)
        response = self._response_from_completion(
            completion,
            model=model,
            started=started,
            metadata={
                "image_count": len(images),
                "high_resolution": high_resolution,
                "thinking_enabled": enable_thinking,
            },
        )
        return self.validate_json(response, None) if json_mode else response

    async def stream_text(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        extra_options: dict[str, Any] | None = None,
    ) -> AsyncIterator[ModelStreamEvent]:
        self._ensure_configured(model)
        options = dict(extra_options or {})
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": options.pop("temperature", 0.2),
            "max_tokens": options.pop("max_tokens", 2048),
            "extra_body": {
                "enable_thinking": bool(options.pop("enable_thinking", False))
            },
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
                error_message="DASHSCOPE_API_KEY未配置",
            )
        started = perf_counter()
        try:
            await self.generate_text(
                messages=[{"role": "user", "content": "只回答：QWEN_OK"}],
                model=self.default_model,
                temperature=0,
                max_tokens=16,
                extra_options={"enable_thinking": False},
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
