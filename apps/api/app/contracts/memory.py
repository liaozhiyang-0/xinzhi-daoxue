from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemoryType(StrEnum):
    PREFERENCE = "preference"
    LEARNING_PREFERENCE = "learning_preference"
    STABLE_PROFILE = "stable_profile"
    PROJECT_CONTEXT = "project_context"
    EPISODIC = "episodic"
    SEMANTIC_LEARNING = "semantic_learning"


class MemoryStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    DELETED = "deleted"
    EXPIRED = "expired"


class MemoryScope(StrEnum):
    GLOBAL = "global"
    COURSE = "course"


class MemoryCreate(BaseModel):
    user_id: str
    memory_type: MemoryType = MemoryType.PREFERENCE
    scope: MemoryScope = MemoryScope.GLOBAL
    course_id: str | None = None
    content: str = Field(min_length=1, max_length=1000)
    content_data: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=20)
    source_session_id: str | None = None
    source_message_id: str | None = None


class MemoryUpdate(BaseModel):
    user_id: str
    content: str | None = Field(default=None, min_length=1, max_length=1000)
    memory_type: MemoryType | None = None
    scope: MemoryScope | None = None
    course_id: str | None = None
    tags: list[str] | None = Field(default=None, max_length=20)


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    memory_id: str = Field(validation_alias="id")
    user_id: str
    memory_type: MemoryType
    scope: MemoryScope
    course_id: str | None
    content: str
    content_data: dict[str, Any]
    tags: list[str]
    source_session_id: str | None
    source_message_id: str | None
    status: MemoryStatus
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revision: int


class ForgetRequest(BaseModel):
    user_id: str
    query: str = Field(default="", max_length=1000)
    all_memories: bool = False


class MemoryMutationResult(BaseModel):
    affected: int = Field(ge=0)
    message: str
