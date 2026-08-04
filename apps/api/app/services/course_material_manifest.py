from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DocumentChunkModel,
    FileIngestionStatus,
    FileModel,
    KnowledgeMaterialStatus,
)


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
