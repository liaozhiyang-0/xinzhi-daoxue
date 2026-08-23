from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import (
    CourseAssetReadinessRead,
    ErrorPoolReviewDecisionSaveRequest,
    KnowledgeDocumentPage,
    KnowledgeMaterialManifestRead,
    KnowledgeMaterialRead,
    KnowledgeMaterialReviewRequest,
    KnowledgeOCRDecisionSaveRequest,
    KnowledgeOCRQualitySummaryRead,
    KnowledgeOCRReviewQueueRead,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSourceStatus,
    RAGSearchRequest,
    RetrievalResult,
    TeacherReviewQueueRead,
)
from app.contracts.api import FileChunkRead
from app.dependencies import (
    get_current_principal,
    get_db,
    get_knowledge_base,
    get_rag_retrieval,
)
from app.knowledge_catalog import KNOWLEDGE_COURSE_IDS
from app.models import (
    CourseMaterialReviewStatus,
    DocumentChunkModel,
    FileIngestionStatus,
    FileModel,
    KnowledgeMaterialStatus,
)
from app.services.audit_service import record_audit
from app.services.auth_service import Principal
from app.services.course_asset_review import (
    attach_evaluation_provenance_readiness,
    attach_ocr_decision_readiness,
    build_course_asset_readiness,
    build_error_pool_review_document,
    build_teacher_review_queue,
    validate_error_pool_review_document,
    write_error_pool_review_document,
)
from app.services.course_material_manifest import (
    build_course_material_manifest,
    update_material_revocation_state,
)
from app.services.evaluation_provenance import (
    EVALUATION_REPORT_PATH,
    build_evaluation_provenance,
)
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_index import KnowledgeIndexBuilder
from app.services.knowledge_ocr_quality import build_ocr_quality_summary
from app.services.knowledge_ocr_review import (
    build_ocr_decision_document,
    build_ocr_review_queue,
    validate_ocr_decisions,
    write_ocr_decision_document,
)
from app.services.knowledge_resources import (
    resolve_course_resource,
    resolve_kb_image_uri,
)
from app.services.math_formatting_service import MathFormattingService
from app.services.rag_retrieval import RAGRetrievalService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
DOCUMENT_PAGE_CHARS = 24_000
DOCUMENT_PAGE_MAX_CHARS = 60_000
DOCUMENT_CHUNK_PAGE_CHARS = 8_000


async def _published_material(
    db: AsyncSession,
    *,
    course_id: str,
    material_id: str,
) -> FileModel:
    """Resolve only currently published uploaded material by its source id."""

    item = await db.scalar(
        select(FileModel).where(
            FileModel.id == material_id,
            FileModel.course_id == course_id,
            FileModel.purpose == "course_material",
            FileModel.knowledge_status == KnowledgeMaterialStatus.PUBLISHED,
            FileModel.ingestion_status == FileIngestionStatus.READY,
            FileModel.material_review_status != CourseMaterialReviewStatus.REJECTED,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="课程资料不存在或已撤回")
    return item


async def _published_material_content(
    db: AsyncSession,
    *,
    course_id: str,
    material_id: str,
    chunk: str,
) -> tuple[FileModel, str, str]:
    item = await _published_material(
        db, course_id=course_id, material_id=material_id
    )
    if not chunk:
        return item, item.extracted_text or "", ""
    if not chunk.startswith("chunk-") or not chunk.removeprefix("chunk-").isdigit():
        raise HTTPException(status_code=400, detail="知识库片段编号无效")
    ordinal = int(chunk.removeprefix("chunk-"))
    row = await db.scalar(
        select(DocumentChunkModel).where(
            DocumentChunkModel.file_id == item.id,
            DocumentChunkModel.ordinal == ordinal,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="知识库片段不存在")
    return item, row.content, row.content


def _material_quality_report(item: FileModel) -> dict[str, Any]:
    metadata = item.extraction_metadata
    quality = metadata.get("quality_report") if isinstance(metadata, dict) else None
    return quality if isinstance(quality, dict) else {}


def _material_requires_review(item: FileModel) -> bool:
    quality_report = _material_quality_report(item)
    return bool(
        quality_report.get("manual_review_required")
        or item.material_review_status != CourseMaterialReviewStatus.NOT_REQUIRED
    )


def _require_material_manager(request: Request, principal: Principal) -> None:
    if not request.app.state.settings.auth_required:
        return
    if not principal.authenticated or principal.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="需要教师或管理员权限")


def _effective_material_index_status(request: Request, item: FileModel) -> str:
    persisted = item.knowledge_index_status
    state_path = (
        request.app.state.settings.knowledge_index_path / "rag_index_state.json"
    )
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    material_checksums = payload.get("material_checksums", {})
    indexed_checksum = (
        material_checksums.get(item.id)
        if isinstance(material_checksums, dict)
        else None
    )
    if indexed_checksum == item.checksum_sha256:
        return (
            "indexed"
            if item.knowledge_status == KnowledgeMaterialStatus.PUBLISHED
            else "stale"
        )
    if (
        item.knowledge_status != KnowledgeMaterialStatus.PUBLISHED
        and persisted == "indexed"
    ):
        return "stale"
    return (
        persisted if persisted in {"not_indexed", "stale", "failed"} else "not_indexed"
    )


async def _material_read(
    request: Request, db: AsyncSession, item: FileModel
) -> KnowledgeMaterialRead:
    chunk_count = int(
        await db.scalar(
            select(func.count(DocumentChunkModel.id)).where(
                DocumentChunkModel.file_id == item.id
            )
        )
        or 0
    )
    quality_report = _material_quality_report(item)
    return KnowledgeMaterialRead(
        file_id=item.id,
        filename=item.filename,
        owner_user_id=item.owner_user_id,
        course_id=item.course_id or "",
        material_key=item.material_key or "",
        material_version=item.material_version or "",
        checksum_sha256=item.checksum_sha256,
        ingestion_status=item.ingestion_status.value,
        knowledge_status=item.knowledge_status.value,
        knowledge_index_status=_effective_material_index_status(request, item),
        page_count=item.page_count,
        chunk_count=chunk_count,
        extraction_version=item.extraction_version,
        quality_status=str(quality_report.get("quality_status", "unknown")),
        ocr_required=bool(quality_report.get("ocr_required", False)),
        manual_review_required=bool(
            quality_report.get("manual_review_required", False)
        ),
        ocr_candidate_pages=[
            int(page)
            for page in quality_report.get("ocr_candidate_pages", [])
            if isinstance(page, int) and page >= 1
        ],
        quality_warnings=[
            str(warning)
            for warning in quality_report.get("warnings", [])
            if str(warning).strip()
        ],
        material_review_status=item.material_review_status,
        material_reviewed_by=item.material_reviewed_by,
        material_reviewed_at=item.material_reviewed_at,
        material_review_note=item.material_review_note,
        knowledge_published_by=item.knowledge_published_by,
        knowledge_published_at=item.knowledge_published_at,
        created_at=item.created_at,
    )


def _searchable_text(value: str) -> tuple[str, list[int]]:
    normalized: list[str] = []
    offsets: list[int] = []
    for index, character in enumerate(value):
        if character.isalnum():
            normalized.append(character.casefold())
            offsets.append(index)
    return "".join(normalized), offsets


def _find_anchor(document: str, anchor: str) -> int | None:
    if not anchor.strip():
        return None
    direct = document.find(anchor)
    if direct >= 0:
        return direct
    searchable_document, offsets = _searchable_text(document)
    searchable_anchor, _ = _searchable_text(anchor)
    if not searchable_anchor or not offsets:
        return None
    lengths = tuple(
        dict.fromkeys(
            min(len(searchable_anchor), value)
            for value in (360, 240, 160, 100, 60)
            if len(searchable_anchor) >= min(len(searchable_anchor), value)
        )
    )
    for length in lengths:
        if length < 30:
            continue
        matched = searchable_document.find(searchable_anchor[:length])
        if matched >= 0:
            return offsets[matched]
    return None


def _document_window(
    document: str,
    *,
    offset: int | None,
    limit: int,
    anchor: str,
) -> tuple[
    int,
    int,
    Literal["matched", "not_found", "not_requested"],
]:
    anchor_status: Literal["matched", "not_found", "not_requested"]
    anchor_offset = _find_anchor(document, anchor) if offset is None else None
    if anchor_offset is not None:
        start = max(0, anchor_offset - limit // 4)
        anchor_status = "matched"
    else:
        start = max(0, min(offset or 0, max(0, len(document) - 1)))
        anchor_status = (
            "not_found" if anchor.strip() and offset is None else "not_requested"
        )
    if start and offset is None:
        line_start = document.rfind("\n", max(0, start - 1000), start)
        if line_start >= 0:
            start = line_start + 1
    elif start:
        line_start = document.find("\n", start, min(len(document), start + 1000))
        if line_start >= 0:
            start = line_start + 1
    end = min(len(document), start + limit)
    if end < len(document):
        line_end = document.find("\n", end, min(len(document), end + 1000))
        if line_end >= 0:
            end = line_end
    return start, end, anchor_status


@router.get("/sources", response_model=list[KnowledgeSourceStatus])
async def list_sources(
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> list[KnowledgeSourceStatus]:
    return await asyncio.to_thread(knowledge_base.source_statuses)


def _ocr_review_queue_payload(
    request: Request, course_id: str | None
) -> dict[str, Any]:
    settings = request.app.state.settings
    selected = [course_id] if course_id else list(KNOWLEDGE_COURSE_IDS)
    builder = KnowledgeIndexBuilder(
        roots=settings.knowledge_paths,
        output_root=settings.knowledge_index_path,
        max_parse_bytes=settings.knowledge_max_file_size_mb * 1024 * 1024,
        chunk_size=settings.knowledge_chunk_size_chars,
        overlap_chars=settings.knowledge_chunk_overlap_chars,
    )
    queue = build_ocr_review_queue(builder.audit(selected))
    decision_reports: dict[str, dict[str, Any]] = {}
    rows_by_id = {str(item["queue_id"]): item for item in queue["rows"]}
    for selected_course in selected:
        decision_path = (
            settings.knowledge_ocr_decisions_path / f"{selected_course}.yaml"
        )
        if not decision_path.is_file():
            continue
        try:
            raw = yaml.safe_load(decision_path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                raise ValueError("decision document must be an object")
            report = validate_ocr_decisions(queue, raw)
        except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
            report = {
                "schema_version": "ocr_review_decisions.v1",
                "valid": False,
                "course_id": selected_course,
                "errors": [f"decision_file_unreadable:{type(exc).__name__}"],
                "runtime_loaded": False,
                "rows": [],
            }
        decision_reports[selected_course] = report
        for row in report.get("rows", []):
            if isinstance(row, dict) and row.get("queue_id") in rows_by_id:
                rows_by_id[str(row["queue_id"])] = row
    queue["rows"] = list(rows_by_id.values())
    queue["decision_reports"] = decision_reports
    queue["summary"] = {
        **queue["summary"],
        "decision_report_count": len(decision_reports),
        "review_complete_course_count": sum(
            bool(report.get("review_complete")) for report in decision_reports.values()
        ),
    }
    return queue


def _course_asset_readiness_payload(request: Request, course_id: str) -> dict[str, Any]:
    root = Path(request.app.state.settings.knowledge_config_path).parent
    readiness = build_course_asset_readiness(root, course_id)
    queue = request.app.state.knowledge_ocr_review_cache.get_or_build(
        course_id,
        lambda: _ocr_review_queue_payload(request, course_id),
    )
    quality = build_ocr_quality_summary(queue, course_id)
    with_ocr = attach_ocr_decision_readiness(
        readiness, quality.get("decision_evidence", {})
    )
    return attach_evaluation_provenance_readiness(
        with_ocr,
        build_evaluation_provenance(EVALUATION_REPORT_PATH, course_id),
    )


@router.get("/ocr-review-queue", response_model=KnowledgeOCRReviewQueueRead)
async def get_ocr_review_queue(
    request: Request,
    course_id: str | None = Query(default=None, max_length=16),
    principal: Principal = Depends(get_current_principal),
) -> KnowledgeOCRReviewQueueRead:
    """Expose the read-only PDF/OCR review snapshot to teacher managers."""

    _require_material_manager(request, principal)
    normalized_course = course_id.strip().upper() if course_id else None
    if normalized_course and normalized_course not in KNOWLEDGE_COURSE_IDS:
        raise HTTPException(status_code=400, detail="unsupported course_id")
    payload = await asyncio.to_thread(
        request.app.state.knowledge_ocr_review_cache.get_or_build,
        normalized_course,
        lambda: _ocr_review_queue_payload(request, normalized_course),
    )
    return KnowledgeOCRReviewQueueRead.model_validate(payload)


@router.put(
    "/ocr-review-decisions/{course_id}",
    response_model=KnowledgeOCRReviewQueueRead,
)
async def save_ocr_review_decisions(
    course_id: str,
    payload: KnowledgeOCRDecisionSaveRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeOCRReviewQueueRead:
    """Atomically save a validated teacher OCR decision document."""

    _require_material_manager(request, principal)
    normalized_course = course_id.strip().upper()
    if normalized_course not in KNOWLEDGE_COURSE_IDS:
        raise HTTPException(status_code=400, detail="unsupported course_id")

    cache = request.app.state.knowledge_ocr_review_cache
    current_queue = await asyncio.to_thread(
        cache.get_or_build,
        normalized_course,
        lambda: _ocr_review_queue_payload(request, normalized_course),
    )
    if (
        request.app.state.settings.knowledge_ocr_review_cache_enabled
        and payload.source_fingerprint != current_queue.get("source_fingerprint")
    ):
        raise HTTPException(
            status_code=409,
            detail="ocr review queue changed; reload before saving decisions",
        )

    reviewer = payload.reviewer
    if request.app.state.settings.auth_required:
        reviewer = principal.account_id or principal.user_id
        if not reviewer:
            raise HTTPException(status_code=403, detail="reviewer identity required")
    try:
        document = build_ocr_decision_document(
            current_queue,
            normalized_course,
            [item.model_dump(mode="json") for item in payload.decisions],
            reviewer=reviewer,
            reviewed_at=datetime.now(UTC).isoformat(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    report = validate_ocr_decisions(current_queue, document)
    if not report.get("valid"):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "invalid OCR decision document",
                "errors": report["errors"],
            },
        )
    decision_path = (
        request.app.state.settings.knowledge_ocr_decisions_path
        / f"{normalized_course}.yaml"
    )
    try:
        await asyncio.to_thread(write_ocr_decision_document, decision_path, document)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"unable to persist OCR decision document: {type(exc).__name__}",
        ) from exc

    record_audit(
        db,
        request,
        action="knowledge_ocr.review_decisions.save",
        actor_account_id=principal.account_id or None,
        target_type="ocr_decision_document",
        target_id=normalized_course,
        details={
            "course_id": normalized_course,
            "source_fingerprint": payload.source_fingerprint,
            "decision_count": report.get("decision_count", 0),
            "decided_count": report.get("decided_count", 0),
            "review_complete": bool(report.get("review_complete")),
            "evidence_ref_count": sum(
                len(item.get("evidence_refs", []))
                for item in document.get("decisions", [])
                if isinstance(item, dict)
            ),
        },
    )
    await db.commit()
    cache.invalidate(normalized_course)
    refreshed = await asyncio.to_thread(
        cache.get_or_build,
        normalized_course,
        lambda: _ocr_review_queue_payload(request, normalized_course),
    )
    return KnowledgeOCRReviewQueueRead.model_validate(refreshed)


@router.get("/ocr-quality-summary", response_model=KnowledgeOCRQualitySummaryRead)
async def get_ocr_quality_summary(
    request: Request,
    course_id: str | None = Query(default=None, max_length=16),
    principal: Principal = Depends(get_current_principal),
) -> KnowledgeOCRQualitySummaryRead:
    """Expose read-only page-level OCR evidence from the cached audit queue."""

    _require_material_manager(request, principal)
    normalized_course = course_id.strip().upper() if course_id else None
    if normalized_course and normalized_course not in KNOWLEDGE_COURSE_IDS:
        raise HTTPException(status_code=400, detail="unsupported course_id")
    queue = await asyncio.to_thread(
        request.app.state.knowledge_ocr_review_cache.get_or_build,
        normalized_course,
        lambda: _ocr_review_queue_payload(request, normalized_course),
    )
    payload = build_ocr_quality_summary(queue, normalized_course)
    return KnowledgeOCRQualitySummaryRead.model_validate(payload)


@router.get("/course-asset-review-queue", response_model=TeacherReviewQueueRead)
async def get_course_asset_review_queue(
    request: Request,
    course_id: str = Query(..., min_length=2, max_length=16),
    principal: Principal = Depends(get_current_principal),
) -> TeacherReviewQueueRead:
    """Expose the evidence-gated CT/AE error-template queue read-only."""

    _require_material_manager(request, principal)
    normalized_course = course_id.strip().upper()
    if normalized_course not in {"CT", "AE"}:
        raise HTTPException(status_code=400, detail="unsupported course_id")
    root = Path(request.app.state.settings.knowledge_config_path).parent
    payload = await asyncio.to_thread(
        build_teacher_review_queue, root, normalized_course
    )
    return TeacherReviewQueueRead.model_validate(payload)


@router.put(
    "/course-asset-review-decisions/{course_id}",
    response_model=TeacherReviewQueueRead,
)
async def save_course_asset_review_decisions(
    course_id: str,
    payload: ErrorPoolReviewDecisionSaveRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TeacherReviewQueueRead:
    """Atomically save evidence-backed CT/AE error-template decisions."""

    _require_material_manager(request, principal)
    normalized_course = course_id.strip().upper()
    if normalized_course not in {"CT", "AE"}:
        raise HTTPException(status_code=400, detail="unsupported course_id")
    root = Path(request.app.state.settings.knowledge_config_path).parent
    current_queue = await asyncio.to_thread(
        build_teacher_review_queue, root, normalized_course
    )
    if payload.source_fingerprint != current_queue.get("source_fingerprint"):
        raise HTTPException(
            status_code=409,
            detail="course asset review queue changed; reload before saving decisions",
        )

    reviewer = payload.reviewer
    if request.app.state.settings.auth_required:
        reviewer = principal.account_id or principal.user_id
        if not reviewer:
            raise HTTPException(status_code=403, detail="reviewer identity required")
    try:
        document = build_error_pool_review_document(
            current_queue,
            normalized_course,
            [item.model_dump(mode="json") for item in payload.decisions],
            source_fingerprint=payload.source_fingerprint,
            reviewer=reviewer,
            reviewed_at=datetime.now(UTC).isoformat(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    report = validate_error_pool_review_document(current_queue, document)
    if not report.get("valid"):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "invalid course asset review document",
                "errors": report["errors"],
            },
        )
    decision_path = (
        root / "config" / "error_pool" / "reviews" / f"{normalized_course}.yaml"
    )
    try:
        await asyncio.to_thread(
            write_error_pool_review_document, decision_path, document
        )
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "unable to persist course asset review document: "
                f"{type(exc).__name__}"
            ),
        ) from exc

    record_audit(
        db,
        request,
        action="knowledge_course_asset.review_decisions.save",
        actor_account_id=principal.account_id or None,
        target_type="course_asset_review_document",
        target_id=normalized_course,
        details={
            "course_id": normalized_course,
            "source_fingerprint": payload.source_fingerprint,
            "decision_count": report.get("decision_count", 0),
            "decided_count": report.get("decided_count", 0),
            "review_complete": bool(report.get("review_complete")),
            "evidence_ref_count": sum(
                len(item.get("evidence_refs", []))
                for item in document.get("decisions", [])
                if isinstance(item, dict)
            ),
            "runtime_loaded": False,
        },
    )
    await db.commit()
    refreshed = await asyncio.to_thread(
        build_teacher_review_queue, root, normalized_course
    )
    return TeacherReviewQueueRead.model_validate(refreshed)


@router.get("/course-asset-readiness", response_model=CourseAssetReadinessRead)
async def get_course_asset_readiness(
    request: Request,
    course_id: str = Query(..., min_length=2, max_length=16),
    principal: Principal = Depends(get_current_principal),
) -> CourseAssetReadinessRead:
    """Expose evidence readiness and blockers for one CT/AE asset manifest."""

    _require_material_manager(request, principal)
    normalized_course = course_id.strip().upper()
    if normalized_course not in {"CT", "AE"}:
        raise HTTPException(status_code=400, detail="unsupported course_id")
    payload = await asyncio.to_thread(
        _course_asset_readiness_payload, request, normalized_course
    )
    return CourseAssetReadinessRead.model_validate(payload)


@router.get("/materials", response_model=list[KnowledgeMaterialRead])
async def list_course_materials(
    request: Request,
    course_id: str | None = Query(default=None, max_length=32),
    material_status: KnowledgeMaterialStatus | None = Query(default=None),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeMaterialRead]:
    _require_material_manager(request, principal)
    statement = select(FileModel).where(FileModel.purpose == "course_material")
    if course_id:
        statement = statement.where(FileModel.course_id == course_id.strip())
    if material_status is not None:
        statement = statement.where(FileModel.knowledge_status == material_status)
    statement = statement.order_by(FileModel.created_at.desc())
    items = list((await db.scalars(statement)).all())
    return [await _material_read(request, db, item) for item in items]


@router.get(
    "/materials/{file_id}/chunks",
    response_model=list[FileChunkRead],
)
async def list_course_material_chunks(
    file_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[FileChunkRead]:
    """Expose bounded parsed material chunks to authorized reviewers only."""

    _require_material_manager(request, principal)
    item = await db.get(FileModel, file_id)
    if item is None or item.purpose != "course_material":
        raise HTTPException(status_code=404, detail="课程材料不存在")
    chunks = list(
        (
            await db.scalars(
                select(DocumentChunkModel)
                .where(DocumentChunkModel.file_id == file_id)
                .order_by(DocumentChunkModel.ordinal)
            )
        ).all()
    )
    return [FileChunkRead.model_validate(chunk) for chunk in chunks]


@router.post("/materials/manifest", response_model=KnowledgeMaterialManifestRead)
async def sync_course_material_manifest(
    request: Request,
    course_id: str | None = Query(default=None, max_length=32),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeMaterialManifestRead:
    _require_material_manager(request, principal)
    result = await build_course_material_manifest(
        db,
        request.app.state.settings.knowledge_index_path,
        course_id=course_id.strip() if course_id else None,
    )
    record_audit(
        db,
        request,
        action="knowledge_material.manifest_sync",
        actor_account_id=principal.account_id or None,
        target_type="knowledge_index",
        target_id=result.manifest_filename,
        details=result.to_dict(),
    )
    await db.commit()
    return KnowledgeMaterialManifestRead.model_validate(result.to_dict())


@router.post("/materials/{file_id}/publish", response_model=KnowledgeMaterialRead)
async def publish_course_material(
    file_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeMaterialRead:
    _require_material_manager(request, principal)
    item = await db.get(FileModel, file_id)
    if item is None or item.purpose != "course_material":
        raise HTTPException(status_code=404, detail="课程资料不存在")
    if item.ingestion_status != FileIngestionStatus.READY:
        raise HTTPException(
            status_code=409,
            detail="资料解析未达到ready，不能发布；请先完成人工复核",
        )
    if (
        _material_requires_review(item)
        and item.material_review_status != CourseMaterialReviewStatus.APPROVED
    ):
        raise HTTPException(
            status_code=409,
            detail="material review approval is required before publishing",
        )
    previous = await db.scalars(
        select(FileModel).where(
            FileModel.course_id == item.course_id,
            FileModel.material_key == item.material_key,
            FileModel.knowledge_status == KnowledgeMaterialStatus.PUBLISHED,
            FileModel.id != item.id,
        )
    )
    for version in previous:
        version.knowledge_status = KnowledgeMaterialStatus.SUPERSEDED
        version.knowledge_index_status = "stale"
    item.knowledge_status = KnowledgeMaterialStatus.PUBLISHED
    item.knowledge_index_status = "not_indexed"
    item.knowledge_published_by = principal.user_id or None
    item.knowledge_published_at = datetime.now(UTC)
    update_material_revocation_state(
        request.app.state.settings.knowledge_index_path,
        item.id,
        revoked=False,
    )
    record_audit(
        db,
        request,
        action="knowledge_material.publish",
        actor_account_id=principal.account_id or None,
        target_type="file",
        target_id=item.id,
        details={
            "course_id": item.course_id,
            "material_key": item.material_key,
            "material_version": item.material_version,
            "checksum_sha256": item.checksum_sha256,
            "knowledge_index_status": item.knowledge_index_status,
        },
    )
    await db.commit()
    await db.refresh(item)
    return await _material_read(request, db, item)


@router.post("/materials/{file_id}/review", response_model=KnowledgeMaterialRead)
async def review_course_material(
    file_id: str,
    payload: KnowledgeMaterialReviewRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeMaterialRead:
    _require_material_manager(request, principal)
    item = await db.get(FileModel, file_id)
    if item is None or item.purpose != "course_material":
        raise HTTPException(status_code=404, detail="course material not found")
    if (
        payload.status == "approved"
        and item.ingestion_status != FileIngestionStatus.READY
    ):
        raise HTTPException(
            status_code=409,
            detail="only ready material can be approved",
        )
    was_published = item.knowledge_status == KnowledgeMaterialStatus.PUBLISHED
    review_status = (
        CourseMaterialReviewStatus.APPROVED
        if payload.status == "approved"
        else CourseMaterialReviewStatus.REJECTED
    )
    item.material_review_status = review_status
    item.material_reviewed_by = principal.account_id or principal.user_id or None
    item.material_reviewed_at = datetime.now(UTC)
    item.material_review_note = payload.note or None
    if payload.status == "rejected" and was_published:
        # A review decision is also a publication authorization decision. A
        # later rejection must revoke the already-public material immediately;
        # otherwise the manifest/RAG index can continue exposing it until a
        # separate withdrawal call happens.
        item.knowledge_status = KnowledgeMaterialStatus.WITHDRAWN
        item.knowledge_index_status = "stale"
        item.knowledge_published_by = principal.user_id or None
        item.knowledge_published_at = item.material_reviewed_at
        update_material_revocation_state(
            request.app.state.settings.knowledge_index_path,
            item.id,
            revoked=True,
        )
    record_audit(
        db,
        request,
        action="knowledge_material.review",
        actor_account_id=principal.account_id or None,
        target_type="file",
        target_id=item.id,
        details={
            "course_id": item.course_id,
            "material_key": item.material_key,
            "material_version": item.material_version,
            "review_status": review_status.value,
            "note_present": bool(payload.note),
            "publication_revoked": bool(payload.status == "rejected" and was_published),
        },
    )
    await db.commit()
    await db.refresh(item)
    return await _material_read(request, db, item)


@router.post("/materials/{file_id}/withdraw", response_model=KnowledgeMaterialRead)
async def withdraw_course_material(
    file_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeMaterialRead:
    _require_material_manager(request, principal)
    item = await db.get(FileModel, file_id)
    if item is None or item.purpose != "course_material":
        raise HTTPException(status_code=404, detail="课程资料不存在")
    was_published = item.knowledge_status == KnowledgeMaterialStatus.PUBLISHED
    item.knowledge_status = KnowledgeMaterialStatus.WITHDRAWN
    if was_published:
        item.knowledge_index_status = "stale"
    item.knowledge_published_by = principal.user_id or None
    item.knowledge_published_at = datetime.now(UTC)
    update_material_revocation_state(
        request.app.state.settings.knowledge_index_path,
        item.id,
        revoked=True,
    )
    record_audit(
        db,
        request,
        action="knowledge_material.withdraw",
        actor_account_id=principal.account_id or None,
        target_type="file",
        target_id=item.id,
        details={
            "course_id": item.course_id,
            "material_key": item.material_key,
            "material_version": item.material_version,
            "publication_revoked": was_published,
        },
    )
    await db.commit()
    await db.refresh(item)
    return await _material_read(request, db, item)


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    payload: KnowledgeSearchRequest,
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> KnowledgeSearchResponse:
    hits = await asyncio.to_thread(
        knowledge_base.search,
        payload.query,
        list(payload.course_ids),
        payload.top_k,
    )
    sources = await asyncio.to_thread(knowledge_base.source_statuses)
    return KnowledgeSearchResponse(query=payload.query, hits=hits, sources=sources)


@router.post("/evaluate-query", response_model=RetrievalResult)
async def evaluate_query(
    payload: KnowledgeSearchRequest,
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> RetrievalResult:
    return await asyncio.to_thread(
        knowledge_base.search_result,
        payload.query,
        list(payload.course_ids),
        payload.top_k,
    )


@router.post("/rag-search", response_model=RetrievalResult)
async def rag_search(
    payload: RAGSearchRequest,
    request: Request,
    rag: RAGRetrievalService = Depends(get_rag_retrieval),
) -> RetrievalResult:
    if not payload.query_text and not payload.image_resource_uri:
        raise HTTPException(status_code=422, detail="query_text 与图片至少提供一项")
    image = None
    if payload.image_resource_uri:
        try:
            image = resolve_kb_image_uri(
                request.app.state.settings, payload.image_resource_uri
            )
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await asyncio.to_thread(
        rag.search,
        query_text=payload.query_text,
        query_image=image,
        course_id=payload.course_id.value,
        intent=payload.intent,
        target_agent_id=payload.target_agent_id,
        top_k=payload.top_k,
        content_types=tuple(payload.content_types),
        include_images=payload.include_images,
        use_reranker=payload.use_reranker,
    )


@router.get("/health", response_model=dict[str, Any])
async def rag_health(
    rag: RAGRetrievalService = Depends(get_rag_retrieval),
) -> dict[str, Any]:
    return await asyncio.to_thread(rag.health)


@router.get("/materials/{course_id}/{material_id}")
async def knowledge_material_document(
    course_id: str,
    material_id: str,
    chunk: str = "",
    normalize_math: bool = False,
    _principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    _, content, _ = await _published_material_content(
        db,
        course_id=course_id,
        material_id=material_id,
        chunk=chunk,
    )
    if normalize_math:
        content = await asyncio.to_thread(
            lambda: MathFormattingService().process_markdown(content).markdown
        )
    return PlainTextResponse(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get(
    "/material-pages/{course_id}/{material_id}",
    response_model=KnowledgeDocumentPage,
)
async def knowledge_material_page(
    course_id: str,
    material_id: str,
    response: Response,
    offset: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=4000, le=DOCUMENT_PAGE_MAX_CHARS),
    anchor: str = Query(default="", max_length=2000),
    chunk: str = Query(default="", max_length=64),
    normalize_math: bool = True,
    _principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentPage:
    item, document, _ = await _published_material_content(
        db,
        course_id=course_id,
        material_id=material_id,
        chunk="",
    )
    chunk_anchor = ""
    if chunk:
        _, _, chunk_anchor = await _published_material_content(
            db,
            course_id=course_id,
            material_id=material_id,
            chunk=chunk,
        )
    page_limit = limit or (DOCUMENT_CHUNK_PAGE_CHARS if chunk else DOCUMENT_PAGE_CHARS)
    requested_anchor = anchor or chunk_anchor
    start, end, anchor_status = await asyncio.to_thread(
        _document_window,
        document,
        offset=offset,
        limit=page_limit,
        anchor=requested_anchor,
    )
    content = document[start:end]
    if normalize_math:
        content = await asyncio.to_thread(
            lambda: MathFormattingService().process_markdown(content).markdown
        )
    source_ref = f"kb-material://{course_id}/{material_id}"
    if chunk:
        source_ref += f"#{chunk}"
    response.headers["Cache-Control"] = "private, no-store"
    return KnowledgeDocumentPage(
        source_ref=source_ref,
        course_id=course_id,
        relative_path=f"materials/{material_id}/{item.filename}",
        requested_chunk=chunk,
        content=content,
        total_chars=len(document),
        start_offset=start,
        end_offset=end,
        previous_offset=max(0, start - page_limit - 1000) if start > 0 else None,
        next_offset=end if end < len(document) else None,
        anchor_status=anchor_status,
    )


@router.get("/images/{course_id}/{relative_path:path}")
async def knowledge_image(
    course_id: str,
    relative_path: str,
    request: Request,
    _principal: Principal = Depends(get_current_principal),
) -> FileResponse:
    try:
        target = resolve_course_resource(
            request.app.state.settings,
            course_id=course_id,
            relative_path=relative_path,
            image_only=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        target,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/documents/{course_id}/{relative_path:path}")
async def knowledge_document(
    course_id: str,
    relative_path: str,
    request: Request,
    normalize_math: bool = False,
    chunk: str = "",
    _principal: Principal = Depends(get_current_principal),
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> PlainTextResponse:
    try:
        if chunk:
            if (
                not chunk.startswith("chunk-")
                or not chunk.removeprefix("chunk-").isdigit()
            ):
                raise ValueError("知识库片段编号无效")
            source_ref = f"kb://{course_id}/{relative_path}#{chunk}"
            content = await asyncio.to_thread(knowledge_base.source_content, source_ref)
            if content is None:
                raise FileNotFoundError("知识库片段不存在")
        else:
            target = resolve_course_resource(
                request.app.state.settings,
                course_id=course_id,
                relative_path=relative_path,
                text_only=True,
            )
            content = await asyncio.to_thread(target.read_text, encoding="utf-8")
        if normalize_math:
            content = await asyncio.to_thread(
                lambda: MathFormattingService().process_markdown(content).markdown
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, UnicodeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlainTextResponse(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get(
    "/document-pages/{course_id}/{relative_path:path}",
    response_model=KnowledgeDocumentPage,
)
async def knowledge_document_page(
    course_id: str,
    relative_path: str,
    request: Request,
    response: Response,
    offset: int | None = Query(default=None, ge=0),
    limit: int | None = Query(
        default=None,
        ge=4000,
        le=DOCUMENT_PAGE_MAX_CHARS,
    ),
    anchor: str = Query(default="", max_length=2000),
    chunk: str = Query(default="", max_length=64),
    normalize_math: bool = True,
    _principal: Principal = Depends(get_current_principal),
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> KnowledgeDocumentPage:
    try:
        if chunk and (
            not chunk.startswith("chunk-") or not chunk.removeprefix("chunk-").isdigit()
        ):
            raise ValueError("知识库片段编号无效")
        target = resolve_course_resource(
            request.app.state.settings,
            course_id=course_id,
            relative_path=relative_path,
            text_only=True,
        )
        document = await asyncio.to_thread(target.read_text, encoding="utf-8")
        chunk_anchor = ""
        if offset is None and chunk:
            source_ref = f"kb://{course_id}/{relative_path}#{chunk}"
            chunk_anchor = await asyncio.to_thread(
                lambda: knowledge_base.source_content(source_ref) or ""
            )
        page_limit = limit or (
            DOCUMENT_CHUNK_PAGE_CHARS if chunk else DOCUMENT_PAGE_CHARS
        )
        # The evidence-card summary is the freshest locator for a persisted
        # result.  A chunk id can point at an older index projection after a
        # course document is reindexed, so using it first can open an unrelated
        # part of the same document.  Keep the chunk as a bounded fallback.
        requested_anchor = anchor or chunk_anchor
        start, end, anchor_status = await asyncio.to_thread(
            _document_window,
            document,
            offset=offset,
            limit=page_limit,
            anchor=requested_anchor,
        )
        if offset is None and anchor and chunk_anchor and anchor_status == "not_found":
            start, end, anchor_status = await asyncio.to_thread(
                _document_window,
                document,
                offset=None,
                limit=page_limit,
                anchor=chunk_anchor,
            )
        content = document[start:end]
        if normalize_math:
            content = await asyncio.to_thread(
                lambda: MathFormattingService().process_markdown(content).markdown
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, UnicodeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    source_ref = f"kb://{course_id}/{relative_path}"
    if chunk:
        source_ref += f"#{chunk}"
    response.headers["Cache-Control"] = "private, no-store"
    return KnowledgeDocumentPage(
        source_ref=source_ref,
        course_id=course_id,
        relative_path=relative_path,
        requested_chunk=chunk,
        content=content,
        total_chars=len(document),
        start_offset=start,
        end_offset=end,
        previous_offset=max(0, start - page_limit - 1000) if start > 0 else None,
        next_offset=end if end < len(document) else None,
        anchor_status=anchor_status,
    )


@router.get("/benchmark-summary", response_model=dict[str, Any])
async def benchmark_summary(request: Request) -> dict[str, Any]:
    root = Path(request.app.state.settings.knowledge_config_path).parent
    results = root / "evaluation" / "knowledge_retrieval" / "results"
    runs: dict[str, Any] = {}
    for run_id in ("baseline_lexical_v1", "local_lexical_v2"):
        path = results / f"{run_id}.json"
        if not path.is_file():
            runs[run_id] = {"available": False}
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            runs[run_id] = {"available": False, "warning": "结果文件不可读"}
            continue
        runs[run_id] = {
            "available": True,
            "generated_at": payload.get("generated_at"),
            "case_count": payload.get("case_count"),
            "case_status": payload.get("case_status"),
            "metrics": payload.get("metrics", {}),
        }
    return {"benchmark_status": "draft", "human_review_required": True, "runs": runs}


@router.post("/reload", response_model=list[KnowledgeSourceStatus])
async def reload_knowledge(
    request: Request,
    knowledge_base: KnowledgeBaseService = Depends(get_knowledge_base),
) -> list[KnowledgeSourceStatus]:
    if request.app.state.settings.app_env == "production":
        return await asyncio.to_thread(knowledge_base.source_statuses)
    return await asyncio.to_thread(knowledge_base.refresh)
