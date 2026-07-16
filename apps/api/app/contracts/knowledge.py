from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeCourseId(StrEnum):
    CIRCUIT_THEORY = "CT"
    ANALOG_ELECTRONICS = "AE"
    DIGITAL_ELECTRONICS = "DE"


class KnowledgeSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    course_ids: list[KnowledgeCourseId] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("query 不能为空")
        return normalized


class KnowledgeHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: KnowledgeCourseId
    course_name: str
    document_path: str
    title: str
    content: str
    score: float = Field(ge=0)
    source_ref: str


class KnowledgeSourceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: KnowledgeCourseId
    course_name: str
    available: bool
    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    indexed_at: datetime | None = None
    message: str | None = None


class KnowledgeSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    hits: list[KnowledgeHit] = Field(default_factory=list)
    sources: list[KnowledgeSourceStatus] = Field(default_factory=list)


def utc_now() -> datetime:
    return datetime.now(UTC)
