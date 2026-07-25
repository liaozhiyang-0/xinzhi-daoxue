from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeCourseId(StrEnum):
    CIRCUIT_THEORY = "CT"
    ANALOG_ELECTRONICS = "AE"
    DIGITAL_ELECTRONICS = "DE"
    SIGNALS_AND_SYSTEMS = "SS"
    DIGITAL_SIGNAL_PROCESSING = "DSP"
    COMMUNICATION_PRINCIPLES = "COMM"


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


class RAGSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str = Field(default="", max_length=1000)
    course_id: KnowledgeCourseId
    image_resource_uri: str | None = None
    intent: str = "general_qa"
    target_agent_id: str = "LEARN_01_KNOWLEDGE_QA_V1"
    top_k: int = Field(default=5, ge=1, le=20)
    content_types: list[str] = Field(default_factory=list)
    include_images: bool = True
    use_reranker: bool | None = None

    @field_validator("query_text")
    @classmethod
    def normalize_rag_query(cls, value: str) -> str:
        return " ".join(value.split())


class RelatedImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: str
    resource_uri: str
    caption: str = ""
    description_source: str = "source_text"
    course_id: str = ""
    parent_document_id: str | None = None
    parent_chunk_id: str | None = None
    image_type: str = "unknown"
    score: float = Field(default=0, ge=0)
    retrieval_channels: list[str] = Field(default_factory=list)


class KnowledgeHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = ""
    evidence_id: str = ""
    document_id: str = ""
    course_id: KnowledgeCourseId
    course_name: str
    chapter: str = ""
    section: str = ""
    document_path: str
    title: str
    content_type: str = "unknown"
    content: str
    score: float = Field(ge=0)
    score_components: dict[str, float] = Field(default_factory=dict)
    source_ref: str
    document_checksum: str = ""
    related_images: list[RelatedImage] = Field(default_factory=list)


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
    image_hits: list[RelatedImage] = Field(default_factory=list)
    rag_status: str = "disabled"
    embedding_status: str = "disabled"
    vector_store_status: str = "disabled"
    reranker_status: str = "disabled"
    query_modalities: list[str] = Field(default_factory=lambda: ["text"])
    retrieval_trace_id: str = ""
    index_version: str = ""
    trace: dict[str, object] = Field(default_factory=dict)


class RetrievalContextPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    course_id: str
    intent: str
    evidence: list[KnowledgeHit] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    evidence_status: str
    retrieval_mode: str = "local_lexical_v2"
    warnings: list[str] = Field(default_factory=list)
    max_context_chars: int = Field(gt=0)
    rag_status: str = "disabled"
    embedding_status: str = "disabled"
    vector_store_status: str = "disabled"
    reranker_status: str = "disabled"
    query_modalities: list[str] = Field(default_factory=lambda: ["text"])
    retrieval_trace_id: str = ""
    latency_ms: int = Field(default=0, ge=0)
    index_version: str = ""

    def to_retrieved_context(self) -> str:
        blocks = [
            f"evidence_status: {self.evidence_status}",
            f"retrieval_mode: {self.retrieval_mode}",
            f"rag_status: {self.rag_status}",
            f"index_version: {self.index_version or 'unavailable'}",
        ]
        if self.warnings:
            blocks.append("warnings: " + "；".join(self.warnings))
        for index, hit in enumerate(self.evidence, start=1):
            evidence_id = hit.evidence_id or f"S{index}"
            lines = [
                f"[{evidence_id}]",
                f"课程：{hit.course_name}",
                f"章节：{hit.chapter or 'UNKNOWN'}",
                f"标题：{hit.title}",
                f"内容类型：{hit.content_type}",
                f"来源：{hit.source_ref}",
                f"内容：{hit.content}",
            ]
            if hit.related_images:
                lines.append("相关图片：")
                for image in hit.related_images:
                    lines.append(f"- {image.resource_uri}")
                    if image.caption:
                        lines.append(f"- 图片说明：{image.caption}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)


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
