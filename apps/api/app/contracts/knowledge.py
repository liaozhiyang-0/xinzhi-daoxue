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

    chunk_id: str = ""
    course_id: KnowledgeCourseId
    course_name: str
    chapter: str = ""
    section: str = ""
    document_path: str
    title: str
    content: str
    score: float = Field(ge=0)
    score_components: dict[str, float] = Field(default_factory=dict)
    source_ref: str
    document_checksum: str = ""


class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    normalized_query: str
    course_ids: list[str]
    hits: list[KnowledgeHit] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    retrieval_mode: str = "local_lexical_v2"
    warnings: list[str] = Field(default_factory=list)
    latency_ms: int = Field(ge=0)


class RetrievalContextPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    course_id: str
    intent: str
    evidence: list[KnowledgeHit] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    evidence_status: str
    warnings: list[str] = Field(default_factory=list)
    max_context_chars: int = Field(gt=0)


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
