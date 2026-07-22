from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts import (
    ImageInput,
    ModelResponse,
    ModelStreamEvent,
    ProviderHealth,
)


class LLMMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str


class LLMResult(BaseModel):
    """Compatibility envelope retained for the existing KnowledgeQA boundary."""

    model_config = ConfigDict(extra="forbid")

    text: str
    model: str
    provider: str
    usage: dict[str, int] = Field(default_factory=dict)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class BaseModelProvider(ABC):
    provider_name: str

    @property
    @abstractmethod
    def configured(self) -> bool: ...

    @property
    @abstractmethod
    def default_model(self) -> str: ...

    @property
    def available(self) -> bool:
        return self.configured

    @abstractmethod
    async def generate_text(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ModelResponse: ...

    @abstractmethod
    async def generate_json(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        schema: type[BaseModel] | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ModelResponse: ...

    @abstractmethod
    async def generate_multimodal(
        self,
        *,
        prompt: str,
        images: list[ImageInput],
        model: str,
        high_resolution: bool = False,
        json_mode: bool = False,
        extra_options: dict[str, Any] | None = None,
    ) -> ModelResponse: ...

    @abstractmethod
    def stream_text(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        extra_options: dict[str, Any] | None = None,
    ) -> AsyncIterator[ModelStreamEvent]: ...

    @abstractmethod
    async def health_check(self) -> ProviderHealth: ...

    @abstractmethod
    async def aclose(self) -> None: ...

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout_seconds: float | None = None,
    ) -> LLMResult:
        options: dict[str, Any] = {}
        if timeout_seconds is not None:
            options["timeout"] = timeout_seconds
        response = await self.generate_text(
            messages=[item.model_dump() for item in messages],
            model=self.default_model,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_options=options,
        )
        usage = (
            {
                key: value
                for key, value in response.usage.model_dump().items()
                if value is not None
            }
            if response.usage is not None
            else {}
        )
        return LLMResult(
            text=response.content,
            model=response.model,
            provider=response.provider,
            usage=usage,
            raw_metadata=response.raw_metadata,
        )

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[str]:
        options: dict[str, Any] = {
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if timeout_seconds is not None:
            options["timeout"] = timeout_seconds
        async for event in self.stream_text(
            messages=[item.model_dump() for item in messages],
            model=self.default_model,
            extra_options=options,
        ):
            if event.event_type == "content_delta" and event.content:
                yield event.content


LLMProvider = BaseModelProvider
