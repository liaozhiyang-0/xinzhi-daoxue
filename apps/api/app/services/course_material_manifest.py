from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CourseMaterialReviewStatus,
    DocumentChunkModel,
    FileIngestionStatus,
    FileModel,
    KnowledgeMaterialStatus,
)

REVOCATION_STATE_UNAVAILABLE = "__revocation_state_unavailable__"


@dataclass(frozen=True, slots=True)
class CourseMaterialManifestResult:
    manifest_filename: str
    chunk_filename: str
    generated_at: datetime
    material_count: int
    chunk_count: int
    course_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_filename": self.manifest_filename,
            "chunk_filename": self.chunk_filename,
            "generated_at": self.generated_at.isoformat(),
            "material_count": self.material_count,
            "chunk_count": self.chunk_count,
            "course_ids": list(self.course_ids),
        }


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def load_revoked_material_ids(output_root: Path) -> set[str]:
    """Read the durable material revocation set without failing open on bad state."""

    state_path = output_root / "rag_index_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {REVOCATION_STATE_UNAVAILABLE}
    if not isinstance(state, dict):
        return {REVOCATION_STATE_UNAVAILABLE}
    values = state.get("revoked_material_ids", [])
    if not isinstance(values, list):
        return {REVOCATION_STATE_UNAVAILABLE}
    return {str(value).strip() for value in values if str(value).strip()}


def load_material_revocation_version(output_root: Path) -> str:
    """Read the cross-process version of material publication state.

    The revoked-id set alone is not enough for cache invalidation: a material
    can be withdrawn and later republished, returning the set to its previous
    value while its content and permissions have changed.
    """

    state_path = output_root / "rag_index_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return REVOCATION_STATE_UNAVAILABLE
    if not isinstance(state, dict):
        return REVOCATION_STATE_UNAVAILABLE
    revoked_ids = state.get("revoked_material_ids", [])
    if not isinstance(revoked_ids, list):
        return REVOCATION_STATE_UNAVAILABLE
    version = str(state.get("material_revocation_version", "")).strip()
    if version:
        return version
    try:
        file_revision = state_path.stat().st_mtime_ns
    except OSError:
        return REVOCATION_STATE_UNAVAILABLE
    return hashlib.sha256(
        json.dumps(
            {
                "generated_at": str(state.get("generated_at", "")),
                "file_revision": file_revision,
                "revoked_material_ids": sorted(
                    str(value).strip()
                    for value in revoked_ids
                    if str(value).strip()
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:20]


def material_id_from_source_ref(source_ref: str) -> str | None:
    """Return the uploaded-material id from a bounded ``kb-material://`` URI."""

    value = str(source_ref or "")
    if not value.startswith("kb-material://"):
        return None
    path = value.removeprefix("kb-material://").split("#", 1)[0]
    course_id, separator, material_id = path.partition("/")
    if not separator or not course_id.strip() or not material_id.strip():
        return None
    return material_id.strip()


def collect_material_source_refs(value: Any) -> list[str]:
    """Collect bounded uploaded-material source URIs from persisted projections."""

    refs: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, str):
            if item.startswith("kb-material://") and item not in refs:
                refs.append(item)
            return
        if isinstance(item, dict):
            for child in item.values():
                if len(refs) >= 100:
                    return
                visit(child)
            return
        if isinstance(item, list):
            for child in item:
                if len(refs) >= 100:
                    return
                visit(child)

    visit(value)
    return refs


def filter_revoked_material_result(
    result_content: dict[str, Any] | None,
    revoked_material_ids: set[str],
) -> dict[str, Any] | None:
    """Hide withdrawn-material evidence from persisted public projections.

    The answer itself is retained for history, but it is explicitly marked for
    review.  Evidence cards, citations, and retrieval packets are removed so a
    stale task cannot present a withdrawn source as currently valid evidence.
    """

    if not result_content or not revoked_material_ids:
        return result_content
    output = cast(
        dict[str, Any],
        json.loads(json.dumps(result_content, ensure_ascii=False)),
    )
    removed = False

    def is_revoked(value: Any) -> bool:
        material_id = material_id_from_source_ref(str(value or ""))
        return bool(
            material_id
            and (
                REVOCATION_STATE_UNAVAILABLE in revoked_material_ids
                or material_id in revoked_material_ids
            )
        )

    def filter_items(value: Any) -> list[Any]:
        nonlocal removed
        if not isinstance(value, list):
            return value if isinstance(value, list) else []
        filtered: list[Any] = []
        for item in value:
            if isinstance(item, dict) and (
                is_revoked(item.get("source_ref"))
                or is_revoked(item.get("source_uri"))
            ):
                removed = True
                continue
            if isinstance(item, str) and is_revoked(item):
                removed = True
                continue
            filtered.append(item)
        return filtered

    top_level_keys = ("citations",)
    for key in top_level_keys:
        if key in output:
            output[key] = filter_items(output[key])
    structured = output.get("structured_result")
    if isinstance(structured, dict):
        for key in (
            "citations",
            "evidence_view",
            "core_retrieval_summary",
            "source_refs",
            "course_material_source_refs",
        ):
            if key in structured:
                structured[key] = filter_items(structured[key])
        knowledge = structured.get("knowledge")
        if isinstance(knowledge, dict) and "hits" in knowledge:
            knowledge["hits"] = filter_items(knowledge["hits"])
        packet = structured.get("evidence_packet")
        if isinstance(packet, dict) and "sources" in packet:
            packet["sources"] = filter_items(packet["sources"])
        if removed:
            output["evidence_status"] = "insufficient"
            structured["evidence_status"] = "insufficient"
            structured["knowledge_hit_count"] = 0
            structured["verified_evidence_ids"] = []
            workflow_context = structured.get("workflow_context")
            if isinstance(workflow_context, dict):
                workflow_context["evidence_items"] = filter_items(
                    workflow_context.get("evidence_items", [])
                )
                workflow_context["workflow_evidence_ids"] = []
                workflow_context["used_evidence_ids"] = []
                workflow_context["retrieved_context"] = ""
                workflow_context["evidence_status"] = "insufficient"
            if isinstance(packet, dict):
                packet["evidence_sufficiency"] = "insufficient"
                packet["warnings"] = list(
                    dict.fromkeys(
                        [
                            *(
                                packet.get("warnings", [])
                                if isinstance(packet.get("warnings"), list)
                                else []
                            ),
                            "revoked_course_material_removed_from_evidence",
                        ]
                    )
                )
            presentation = structured.get("presentation")
            if isinstance(presentation, dict):
                presentation["source_summary"] = "课程资料已撤回"
                presentation["evidence_message"] = (
                    "原回答引用的课程资料已撤回，当前结果需要重新核验。"
                )
                presentation["requires_review"] = True
                presentation["answer_quality_status"] = "needs_review"
            execution_summary = structured.get("execution_summary")
            if isinstance(execution_summary, dict):
                for key in (
                    "evidence_count",
                    "workflow_evidence_count",
                    "used_evidence_count",
                ):
                    execution_summary[key] = 0
            structured["revocation_notice"] = {
                "status": "needs_review",
                "message": (
                    "回答引用的课程资料已撤回，原答案保留用于历史记录，"
                    "不得作为当前有效依据。"
                ),
            }
            warnings = structured.get("warnings", [])
            if isinstance(warnings, list):
                warnings.append("revoked_course_material_removed_from_evidence")
                structured["warnings"] = list(
                    dict.fromkeys(str(item) for item in warnings)
                )
    if removed:
        warnings = output.get("warnings", [])
        if not isinstance(warnings, list):
            warnings = []
        warnings.append("revoked_course_material_removed_from_evidence")
        output["warnings"] = list(dict.fromkeys(str(item) for item in warnings))
    return output


def update_material_revocation_state(
    output_root: Path,
    material_id: str,
    *,
    revoked: bool,
) -> None:
    """Apply a fail-closed material revocation to files and RAG state.

    Database status is authoritative for publication, but an already-built
    vector collection can outlive that row. Marking the material inactive in
    the durable chunk cache and recording its chunk IDs lets retrieval reject
    stale vectors immediately; a later full index build can then physically
    prune them.
    """

    normalized_id = material_id.strip()
    if not normalized_id:
        raise ValueError("material_id_required")
    chunk_path = output_root / "cache" / "course_material_chunks.jsonl"
    manifest_path = output_root / "course_material_manifest.jsonl"
    state_path = output_root / "rag_index_state.json"
    chunk_rows = _load_jsonl(chunk_path)
    changed = False
    for row in chunk_rows:
        metadata = row.get("metadata")
        row_material_id = (
            str(metadata.get("material_file_id", ""))
            if isinstance(metadata, dict)
            else ""
        )
        if row_material_id == normalized_id and row.get("is_active", True) == revoked:
            row["is_active"] = not revoked
            changed = True
    if changed:
        _write_jsonl_atomic(chunk_path, chunk_rows)

    if revoked and manifest_path.is_file():
        manifest_rows = _load_jsonl(manifest_path)
        filtered_rows = [
            row
            for row in manifest_rows
            if str(row.get("document_id", "")) != normalized_id
        ]
        if len(filtered_rows) != len(manifest_rows):
            _write_jsonl_atomic(manifest_path, filtered_rows)

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    revoked_ids = {
        str(value).strip()
        for value in state.get("revoked_material_ids", [])
        if str(value).strip()
    }
    before = set(revoked_ids)
    if revoked:
        revoked_ids.add(normalized_id)
    else:
        revoked_ids.discard(normalized_id)
    if revoked_ids == before and not changed:
        return
    revoked_chunk_ids = sorted(
        str(row.get("chunk_id"))
        for row in chunk_rows
        if str(row.get("chunk_id", ""))
        and isinstance(row.get("metadata"), dict)
        and str(row["metadata"].get("material_file_id", "")) in revoked_ids
    )
    state["revoked_material_ids"] = sorted(revoked_ids)
    state["revoked_material_chunk_ids"] = revoked_chunk_ids
    generation = state.get("material_revocation_generation", 0)
    try:
        generation = max(0, int(generation)) + 1
    except (TypeError, ValueError):
        generation = 1
    state["material_revocation_generation"] = generation
    state["material_revocation_version"] = hashlib.sha256(
        json.dumps(
            {
                "generation": generation,
                "materials": sorted(revoked_ids),
                "chunks": revoked_chunk_ids,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:20]
    _write_json_atomic(state_path, state)


async def build_course_material_manifest(
    db: AsyncSession,
    output_root: Path,
    *,
    course_id: str | None = None,
) -> CourseMaterialManifestResult:
    statement = select(FileModel).where(
        FileModel.purpose == "course_material",
        FileModel.knowledge_status == KnowledgeMaterialStatus.PUBLISHED,
        FileModel.ingestion_status == FileIngestionStatus.READY,
        FileModel.material_review_status != CourseMaterialReviewStatus.REJECTED,
    )
    if course_id:
        statement = statement.where(FileModel.course_id == course_id)
    materials = list((await db.scalars(statement)).all())
    materials.sort(
        key=lambda item: (item.course_id or "", item.created_at, item.id)
    )

    chunks_by_file: dict[str, list[DocumentChunkModel]] = {
        item.id: [] for item in materials
    }
    if chunks_by_file:
        chunks = await db.scalars(
            select(DocumentChunkModel)
            .where(DocumentChunkModel.file_id.in_(tuple(chunks_by_file)))
            .order_by(DocumentChunkModel.file_id, DocumentChunkModel.ordinal)
        )
        for chunk in chunks:
            chunks_by_file[chunk.file_id].append(chunk)

    manifest_rows: list[dict[str, Any]] = []
    chunk_rows: list[dict[str, Any]] = []
    for material in materials:
        normalized_course = material.course_id or ""
        normalized_key = material.material_key or material.filename
        normalized_version = material.material_version or "unknown"
        relative_path = (
            f"materials/{material.id}/{material.filename}"
        )
        manifest_rows.append(
            {
                "document_id": material.id,
                "course_id": normalized_course,
                "relative_path": relative_path,
                "checksum": material.checksum_sha256,
                "parse_status": material.ingestion_status.value,
                "index_status": material.knowledge_index_status,
                "active": True,
                "source_type": "uploaded_course_material",
                "material_key": normalized_key,
                "material_version": normalized_version,
                "filename": material.filename,
            }
        )
        for chunk in chunks_by_file[material.id]:
            chunk_id = f"material-{material.id}-{chunk.ordinal}"
            source_uri = (
                f"kb-material://{normalized_course}/{material.id}"
                f"#chunk-{chunk.ordinal}"
            )
            chunk_rows.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": material.id,
                    "document_checksum": material.checksum_sha256,
                    "course_id": normalized_course,
                    "relative_path": relative_path,
                    "title": normalized_key,
                    "chapter": chunk.section or normalized_key,
                    "content_type": "course_material",
                    "chunk_index": chunk.ordinal,
                    "text": chunk.content,
                    "source_uri": source_uri,
                    "related_images": [],
                    "document_version": normalized_version,
                    "section_path": [chunk.section] if chunk.section else [],
                    "page_number": chunk.page_number,
                    "metadata": {
                        "material_file_id": material.id,
                        "material_key": normalized_key,
                        "material_version": normalized_version,
                        "source_filename": material.filename,
                    },
                    "is_active": True,
                }
            )

    manifest_path = output_root / "course_material_manifest.jsonl"
    chunk_path = output_root / "cache" / "course_material_chunks.jsonl"
    _write_jsonl_atomic(manifest_path, manifest_rows)
    _write_jsonl_atomic(chunk_path, chunk_rows)
    return CourseMaterialManifestResult(
        manifest_filename=manifest_path.name,
        chunk_filename=chunk_path.relative_to(output_root).as_posix(),
        generated_at=datetime.now(UTC),
        material_count=len(materials),
        chunk_count=len(chunk_rows),
        course_ids=tuple(sorted({item.course_id or "" for item in materials})),
    )
