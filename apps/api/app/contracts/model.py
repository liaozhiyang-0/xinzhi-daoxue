from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    content: str
    reasoning_content: str | None = Field(default=None, exclude=True)
    usage: ModelUsage | None = None
    request_id: str | None = None
    provider_request_id: str | None = None
    elapsed_ms: int = Field(ge=0)
    finish_reason: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    configured: bool
    available: bool
    model: str | None = None
    elapsed_ms: int | None = Field(default=None, ge=0)
    error_type: str | None = None
    error_message: str | None = None


class ImageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["path", "url", "base64"]
    value: str
    mime_type: str | None = None
    filename: str | None = None

    @field_validator("value")
    @classmethod
    def value_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("图片输入不能为空")
        return value


class ModelStreamEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: Literal[
        "reasoning_delta",
        "content_delta",
        "usage",
        "completed",
        "failed",
    ]
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
