from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeCourseId(StrEnum):
    CIRCUIT_THEORY = "CT"
    ANALOG_ELECTRONICS = "AE"
    DIGITAL_ELECTRONICS = "DE"
    SIGNALS_AND_SYSTEMS = "SS"
    DIGITAL_SIGNAL_PROCESSING = "DSP"
    COMMUNICATION_PRINCIPLES = "COMM"


class DocumentManifest(BaseModel):
    """Portable document identity and lifecycle metadata."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    document_version: str = "v1"
    course_id: str
    source_file: str
    source_relative_path: str
    content_hash: str
    title: str = "UNKNOWN"
    chapter: str = "UNKNOWN"
    page_count: int | None = Field(default=None, ge=0)
    content_type: str = "unknown"
    language: str = "unknown"
    source_updated_at: datetime | None = None
    indexed_at: datetime | None = None
    is_active: bool = True

    @field_validator("source_relative_path")
    @classmethod
    def require_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ":/" in normalized:
            raise ValueError("source_relative_path 必须是相对路径")
        return normalized


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    document_id: str
    document_version: str = "v1"
    course_id: str
    chapter: str = "UNKNOWN"
    section_path: list[str] = Field(default_factory=list)
    page_number: int | None = Field(default=None, ge=1)
    content_type: str = "unknown"
    text: str
    metadata: dict[str, object] = Field(default_factory=dict)
    is_active: bool = True


class CitationSupport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: str
    status: Literal[
        "valid",
        "partially_supported",
        "unsupported",
        "stale",
        "invalid_locator",
        "missing_source",
    ]
    document_id: str | None = None
    document_version: str | None = None
    chunk_id: str | None = None
    supported_conclusions: list[str] = Field(default_factory=list)
    unsupported_conclusions: list[str] = Field(default_factory=list)


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


class EvidenceSourceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    document_id: str
    chunk_id: str
    course_id: str | None = None
    chapter: str | None = None
    section: str | None = None
    page: int | None = Field(default=None, ge=1)
    title: str | None = None
    content_excerpt: str
    source_ref: str | None = None
    applicable_skill_ids: list[str] = Field(default_factory=list)
    retrieval_score: float | None = Field(default=None, ge=0)
    rerank_score: float | None = None
    score_components: dict[str, float] = Field(default_factory=dict)
    document_checksum: str | None = None
    source_version: str | None = None
    support_level: Literal[
        "retrieved",
        "potentially_relevant",
        "supports_claim",
        "conflicts",
        "unknown",
    ]
    image_refs: list[str] = Field(default_factory=list)


class EvidencePacketV1(BaseModel):
    """Bounded retrieval evidence; relevance is not proof of a conclusion."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    query: str
    course_id: str | None = None
    retrieval_status: str
    evidence_sufficiency: str
    sources: list[EvidenceSourceV1] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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


class KnowledgeMaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: str
    filename: str
    owner_user_id: str | None
    course_id: str
    material_key: str
    material_version: str
    checksum_sha256: str
    ingestion_status: str
    knowledge_status: str
    knowledge_index_status: str
    page_count: int
    chunk_count: int
    extraction_version: str
    quality_status: str = "unknown"
    ocr_required: bool = False
    manual_review_required: bool = False
    ocr_candidate_pages: list[int] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)
    material_review_status: str = "not_required"
    material_reviewed_by: str | None = None
    material_reviewed_at: datetime | None = None
    material_review_note: str | None = None
    knowledge_published_by: str | None
    knowledge_published_at: datetime | None
    created_at: datetime


class KnowledgeMaterialReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=1000)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return value.strip()


class KnowledgeMaterialManifestRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_filename: str
    chunk_filename: str
    generated_at: datetime
    material_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    course_ids: list[str] = Field(default_factory=list)


class KnowledgeOCRReviewQueueRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    generated_at: str
    mode: str
    runtime_loaded: bool
    ocr_execution_performed: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    decision_reports: dict[str, dict[str, Any]] = Field(default_factory=dict)
    cache_status: str = "miss"
    cache_backend: str = "none"
    source_fingerprint: str = ""
    snapshot_age_seconds: float = Field(default=0.0, ge=0)


class KnowledgeOCRDecisionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_id: str = Field(min_length=1, max_length=200)
    checksum: str = Field(min_length=1, max_length=128)
    decision: Literal[
        "pending",
        "approve_existing_text",
        "request_ocr",
        "split_pdf",
        "reject_source",
        "needs_manual_inspection",
    ]
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    note: str = Field(default="", max_length=2_000)

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for reference in value:
            item = reference.strip()
            if not item:
                continue
            if len(item) > 500:
                raise ValueError("evidence_refs entries must be at most 500 characters")
            if item not in normalized:
                normalized.append(item)
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return value.strip()


class KnowledgeOCRDecisionSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_fingerprint: str = Field(default="", max_length=64)
    reviewer: str = Field(min_length=1, max_length=120)
    decisions: list[KnowledgeOCRDecisionWrite] = Field(max_length=5_000)

    @field_validator("reviewer")
    @classmethod
    def normalize_reviewer(cls, value: str) -> str:
        return value.strip()


class KnowledgeOCRQualityDocumentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_id: str
    course_id: str
    document_id: str
    relative_path: str
    file_name: str
    page_count: int | None = Field(default=None, ge=0)
    parse_status: str
    quality_status: str
    index_status: str
    ocr_required: bool
    ocr_status: str
    ocr_candidate_pages: list[int] = Field(default_factory=list)
    candidate_page_count: int = Field(ge=0)
    low_text_page_count: int = Field(ge=0)
    page_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    manual_review_required: bool
    warnings: list[str] = Field(default_factory=list)
    priority: str
    review_action: str
    review_decision: str


class KnowledgeOCRDecisionEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "decision_file_missing",
        "pending",
        "complete_with_evidence",
        "complete_without_evidence",
        "invalid_or_stale",
    ]
    decision_file_present: bool
    report_valid: bool | None
    review_complete: bool
    candidate_count: int = Field(ge=0)
    decided_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    rows_missing_evidence_refs: int = Field(ge=0)
    stale_checksum_error_count: int = Field(ge=0)
    validation_error_count: int = Field(ge=0)
    next_action: str


class KnowledgeOCRQualitySummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ocr_quality_summary.v1"]
    course_id: str
    mode: Literal["read_only_text_layer_audit"]
    runtime_loaded: bool
    ocr_execution_performed: bool
    audit_status: Literal["available", "partial", "unavailable"]
    decision_evidence: KnowledgeOCRDecisionEvidenceRead
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[KnowledgeOCRQualityDocumentRead] = Field(default_factory=list)
    cache_status: str = "unknown"
    cache_backend: str = "none"
    source_fingerprint: str = ""
    snapshot_age_seconds: float = Field(default=0.0, ge=0)


class TeacherReviewQueueItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    error_signature: str
    priority: Literal["P1", "P2"]
    priority_reason: str
    skill_ids: list[str] = Field(default_factory=list)
    problem_types: list[str] = Field(default_factory=list)
    covered_by_runtime: bool
    review_decision: str
    review_evidence_refs: list[str] = Field(default_factory=list)
    review_notes: str = ""
    reviewer: str | None = None
    reviewed_at: str | None = None
    review_evidence_quality: Literal["missing", "traceable", "untraceable"] = "missing"
    review_evidence_reference_kinds: list[str] = Field(default_factory=list)
    evidence_required: bool
    runtime_eligible: bool
    deterministic_evidence_status: Literal[
        "evidence_ready", "review", "not_declared"
    ] = "not_declared"
    deterministic_conflict_types: list[str] = Field(default_factory=list)
    deterministic_evidence_scope: Literal[
        "structured_fields_only", "finite_deterministic", "not_declared"
    ] = "not_declared"
    deterministic_validator_id: str | None = None
    deterministic_validator_path: str | None = None
    deterministic_evidence_note: str = ""
    next_action: str


class TeacherReviewQueueRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["teacher_review_queue.v1"]
    course_id: str
    status: str
    source_fingerprint: str = ""
    runtime_loaded: bool
    item_count: int = Field(ge=0)
    items: list[TeacherReviewQueueItemRead] = Field(default_factory=list)
    unresolved_signatures_without_proposal: list[str] = Field(default_factory=list)
    all_items_require_teacher_evidence: bool
    proposal_schema_errors: list[str] = Field(default_factory=list)


class ErrorPoolReviewDecisionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(min_length=1, max_length=200)
    decision: Literal["pending", "approved", "rejected"]
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=2_000)

    @field_validator("proposal_id")
    @classmethod
    def normalize_proposal_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for reference in value:
            item = reference.strip()
            if not item:
                continue
            if len(item) > 500:
                raise ValueError("evidence_refs entries must be at most 500 characters")
            if item not in normalized:
                normalized.append(item)
        return normalized

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str) -> str:
        return value.strip()


class ErrorPoolReviewDecisionSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_fingerprint: str = Field(min_length=64, max_length=64)
    reviewer: str = Field(min_length=1, max_length=120)
    decisions: list[ErrorPoolReviewDecisionWrite] = Field(max_length=5_000)

    @field_validator("reviewer")
    @classmethod
    def normalize_reviewer(cls, value: str) -> str:
        return value.strip()


class CourseAssetReadinessItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    status: str
    source_ref: str


class CourseAssetEvidenceCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    declared_status: str
    observed_status: str
    evidence_status: str
    evidence_paths: list[str] = Field(default_factory=list)
    evidence_present: bool


class CourseKnowledgeInventoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available", "partial", "unavailable"]
    manifest_present: bool
    manifest_path: str
    document_count: int = Field(ge=0)
    malformed_manifest_rows: int = Field(ge=0)
    quality_issues_file_present: bool
    quality_issues_file_parseable: bool
    quality_issue_count: int = Field(ge=0)
    quality_issue_type_counts: dict[str, int] = Field(default_factory=dict)
    quality_status_counts: dict[str, int] = Field(default_factory=dict)
    parse_status_counts: dict[str, int] = Field(default_factory=dict)
    rows_with_ocr_metadata: int = Field(ge=0)
    rows_with_ocr_confidence: int = Field(ge=0)
    rows_with_manual_review_flag: int = Field(ge=0)
    ocr_metadata_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    ocr_status: Literal["available", "partial", "unavailable"]


class CourseEvaluationConsistencyRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["consistent", "partial", "inconsistent", "not_checkable"]
    schema_version_supported: bool
    summary_result_count_match: bool
    summary_status_counts_match: bool
    course_statistics_match: bool
    metadata_case_count_match: bool | None
    metadata_case_ids_match: bool | None
    metadata_filters_match: bool | None
    case_catalog_present: bool | None
    case_catalog_content_present: bool | None
    case_source_files_present: bool | None
    case_attachment_manifest_present: bool | None
    report_completed_at_parseable: bool
    report_completed_at_not_future: bool | None
    issues: list[str] = Field(default_factory=list)


class CourseEvaluationProvenanceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["course_evaluation_provenance.v1"]
    status: Literal[
        "available", "report_missing", "report_invalid", "course_not_covered"
    ]
    course_id: str
    report_path: str
    report_present: bool
    report_valid: bool | None
    report_schema_version: str | None
    report_mode: str | None
    started_at: str | None
    completed_at: str | None
    report_filters: dict[str, Any] = Field(default_factory=dict)
    snapshot_at: str
    report_age_seconds: float | None = Field(default=None, ge=0)
    temporal_consistency: Literal["valid", "invalid", "future", "not_checkable"]
    report_case_count: int | None = Field(default=None, ge=0)
    course_case_count: int = Field(ge=0)
    course_passed_count: int = Field(ge=0)
    course_pass_rate: float | None = Field(default=None, ge=0, le=1)
    run_metadata_present: bool
    run_id: str | None
    case_ids_sha256: str | None
    case_catalog_sha256: str | None
    case_catalog_content_sha256: str | None
    case_catalog_content_version: str | None
    case_source_files_sha256: str | None
    case_source_files_version: str | None
    case_attachment_manifest_sha256: str | None
    case_attachment_manifest_version: str | None
    case_attachment_count: int | None = Field(default=None, ge=0)
    filters_sha256: str | None
    implementation_fingerprint: str | None
    execution_channel: str | None
    model_trace_retention: str | None
    raw_prompts_stored: bool | None
    raw_results_included: Literal[False] = False
    data_boundary: list[str] = Field(default_factory=list)
    consistency: CourseEvaluationConsistencyRead


class CourseAssetReadinessRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["course_asset_readiness.v1"]
    course_id: str
    status: Literal["ready", "evidence_pending", "unavailable"]
    runtime_course_pack_status: str
    runtime_loaded: bool
    runtime_source: str | None
    frozen_fallback_reference: str | None
    boundaries: dict[str, Any] = Field(default_factory=dict)
    readiness_items: list[CourseAssetReadinessItemRead] = Field(default_factory=list)
    evidence_checks: list[CourseAssetEvidenceCheckRead] = Field(default_factory=list)
    knowledge_inventory: CourseKnowledgeInventoryRead
    ocr_decision_evidence: KnowledgeOCRDecisionEvidenceRead | None = None
    evaluation_provenance: CourseEvaluationProvenanceRead | None = None
    source_statuses: dict[str, str] = Field(default_factory=dict)
    blockers: list[dict[str, str]] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    teacher_review_queue: dict[str, Any] = Field(default_factory=dict)
    teacher_review_evidence: dict[str, Any] = Field(default_factory=dict)
    contest_boundary: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    hits: list[KnowledgeHit] = Field(default_factory=list)
    sources: list[KnowledgeSourceStatus] = Field(default_factory=list)


class KnowledgeDocumentPage(BaseModel):
    """A bounded page from a local source document with anchor metadata."""

    model_config = ConfigDict(extra="forbid")

    source_ref: str
    course_id: str
    relative_path: str
    requested_chunk: str = ""
    content: str
    total_chars: int = Field(ge=0)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    previous_offset: int | None = Field(default=None, ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    anchor_status: Literal["matched", "not_found", "not_requested"]


def utc_now() -> datetime:
    return datetime.now(UTC)
