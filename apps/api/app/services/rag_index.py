from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.config import Settings
from app.services.rag_providers import ImageEmbeddingProvider, TextEmbeddingProvider
from app.services.vector_store import VectorStoreAdapter


@dataclass(frozen=True, slots=True)
class IndexVersionInfo:
    schema_version: str
    chunker_version: str
    cleaning_version: str
    text_embedding_model: str
    text_embedding_revision: str
    image_embedding_model: str
    image_embedding_revision: str
    text_dimension: int
    image_dimension: int
    text_normalize: bool
    image_normalize: bool

    @property
    def version_id(self) -> str:
        payload = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)
        return "RAG_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "version_id": self.version_id}


@dataclass(frozen=True, slots=True)
class RAGBuildResult:
    index_version: str
    text_points: int
    image_points: int
    reused_text_points: int
    reused_image_points: int
    failed_images: int
    duration_ms: int
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class MultimodalRAGIndexer:
    def __init__(
        self,
        settings: Settings,
        text_provider: TextEmbeddingProvider,
        image_provider: ImageEmbeddingProvider,
        vector_store: VectorStoreAdapter,
    ) -> None:
        self.settings = settings
        self.text_provider = text_provider
        self.image_provider = image_provider
        self.vector_store = vector_store
        self.chunk_path = (
            settings.knowledge_index_path / "cache" / "knowledge_base_chunks.jsonl"
        )
        self.image_path = (
            settings.knowledge_index_path / "knowledge_base_image_evidence.jsonl"
        )
        self.state_path = settings.knowledge_index_path / "rag_index_state.json"

    def version_info(self) -> IndexVersionInfo:
        self.text_provider.load()
        self.image_provider.load()
        return IndexVersionInfo(
            schema_version=self.settings.rag_schema_version,
            chunker_version=self.settings.rag_chunker_version,
            cleaning_version=self.settings.rag_cleaning_version,
            text_embedding_model=self.text_provider.model_name,
            text_embedding_revision=self.text_provider.model_revision,
            image_embedding_model=self.image_provider.model_name,
            image_embedding_revision=self.image_provider.model_revision,
            text_dimension=self.text_provider.dimension,
            image_dimension=self.image_provider.dimension,
            text_normalize=self.settings.text_embedding_normalize,
            image_normalize=self.settings.image_embedding_normalize,
        )

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            return {}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def build(
        self,
        *,
        course_id: str | None = None,
        include_text: bool = True,
        include_images: bool = True,
        incremental: bool = True,
        force_vectors: bool = False,
        relative_file: str | None = None,
        relative_image: str | None = None,
        batch_size: int | None = None,
        dry_run: bool = False,
    ) -> RAGBuildResult:
        started = perf_counter()
        version = self.version_info()
        prior = self._load_state()
        same_version = prior.get("index_version") == version.version_id
        recreate = force_vectors or not same_version
        if not dry_run:
            # Never delete the last usable collections before a replacement build
            # has succeeded. Same-dimension rebuilds overwrite points in place;
            # dimension changes fail safely and retain the prior collection/state.
            self.vector_store.ensure_collections(
                version.text_dimension,
                version.image_dimension,
                recreate=False,
            )
        prior_text = prior.get("text_checksums", {}) if same_version else {}
        prior_images = prior.get("image_checksums", {}) if same_version else {}
        chunks = [
            item
            for item in load_jsonl(self.chunk_path)
            if item.get("is_active", True)
            and (course_id is None or item.get("course_id") == course_id)
            and (relative_file is None or item.get("relative_path") == relative_file)
        ]
        images = [
            item
            for item in load_jsonl(self.image_path)
            if (course_id is None or item.get("course_id") == course_id)
            and (relative_image is None or item.get("source_path") == relative_image)
        ]
        text_todo = [
            item
            for item in chunks
            if not incremental
            or recreate
            or prior_text.get(str(item["chunk_id"])) != item["document_checksum"]
        ]
        image_todo = [
            item
            for item in images
            if not incremental
            or recreate
            or prior_images.get(str(item["image_id"])) != item["checksum"]
        ]
        if dry_run:
            return RAGBuildResult(
                index_version=version.version_id,
                text_points=len(text_todo) if include_text else 0,
                image_points=len(image_todo) if include_images else 0,
                reused_text_points=len(chunks) - len(text_todo),
                reused_image_points=len(images) - len(image_todo),
                failed_images=0,
                duration_ms=int((perf_counter() - started) * 1000),
                dry_run=True,
            )

        actual_batch = batch_size or self.settings.text_embedding_batch_size
        if include_text:
            self._index_text(text_todo, version, actual_batch)
        failed_images: list[dict[str, str]] = []
        indexed_images = 0
        if include_images and self.settings.image_embedding_enabled:
            indexed_images, failed_images = self._index_images(
                image_todo, version, actual_batch
            )

        text_checksums = dict(prior_text) if same_version else {}
        image_checksums = dict(prior_images) if same_version else {}
        if include_text:
            text_checksums.update(
                {str(item["chunk_id"]): item["document_checksum"] for item in chunks}
            )
        if include_images:
            failed_ids = {item["image_id"] for item in failed_images}
            image_checksums.update(
                {
                    str(item["image_id"]): item["checksum"]
                    for item in images
                    if item["image_id"] not in failed_ids
                }
            )
        self.state_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "index_version": version.version_id,
                    "version": version.to_dict(),
                    "text_checksums": text_checksums,
                    "image_checksums": image_checksums,
                    "failed_images": failed_images,
                    "failed_documents": sorted(
                        {
                            str(item.get("parent_document_id", ""))
                            for item in failed_images
                            if item.get("parent_document_id")
                        }
                    ),
                    "last_successful_build_at": datetime.now(UTC).isoformat(),
                    "text_point_count": len(text_checksums),
                    "image_point_count": len(image_checksums),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return RAGBuildResult(
            index_version=version.version_id,
            text_points=len(text_todo) if include_text else 0,
            image_points=indexed_images,
            reused_text_points=len(chunks) - len(text_todo),
            reused_image_points=len(images) - len(image_todo),
            failed_images=len(failed_images),
            duration_ms=int((perf_counter() - started) * 1000),
            dry_run=False,
        )

    def _index_text(
        self,
        chunks: Sequence[dict[str, Any]],
        version: IndexVersionInfo,
        batch_size: int,
    ) -> None:
        for start in range(0, len(chunks), batch_size):
            batch = list(chunks[start : start + batch_size])
            vectors = self.text_provider.embed_documents(
                [str(item["text"]) for item in batch]
            )
            records = [self._text_payload(item, version) for item in batch]
            self.vector_store.upsert_text(records, vectors)

    def _index_images(
        self,
        images: Sequence[dict[str, Any]],
        version: IndexVersionInfo,
        batch_size: int,
    ) -> tuple[int, list[dict[str, str]]]:
        indexed = 0
        failures: list[dict[str, str]] = []
        for start in range(0, len(images), batch_size):
            batch = list(images[start : start + batch_size])
            valid: list[tuple[dict[str, Any], Path]] = []
            for item in batch:
                path = self._image_source(item)
                if path is None or not path.is_file():
                    failures.append(
                        {"image_id": str(item["image_id"]), "reason": "source_missing"}
                    )
                else:
                    valid.append((item, path))
            if not valid:
                continue
            try:
                visual = self.image_provider.embed_images([path for _, path in valid])
                captions = [self._caption_embedding_text(item) for item, _ in valid]
                caption_vectors = self.text_provider.embed_documents(captions)
                records = [self._image_payload(item, version) for item, _ in valid]
                self.vector_store.upsert_images(records, visual, caption_vectors)
                indexed += len(valid)
            except Exception:
                for item, path in valid:
                    try:
                        visual_one = [self.image_provider.embed_image(path)]
                        caption_one = self.text_provider.embed_documents(
                            [self._caption_embedding_text(item)]
                        )
                        self.vector_store.upsert_images(
                            [self._image_payload(item, version)],
                            visual_one,
                            caption_one,
                        )
                        indexed += 1
                    except Exception as exc:
                        failures.append(
                            {
                                "image_id": str(item["image_id"]),
                                "reason": type(exc).__name__,
                            }
                        )
        return indexed, failures

    def _caption_embedding_text(self, item: dict[str, Any]) -> str:
        # Caption metadata remains complete in Qdrant. The text fed to BGE is
        # bounded during index construction so the model never silently truncates.
        return self._caption(item)[: self.settings.knowledge_chunk_size_chars]

    def _image_source(self, item: dict[str, Any]) -> Path | None:
        course_id = str(item.get("course_id", ""))
        root = self.settings.knowledge_paths.get(course_id)
        if root is None:
            return None
        source = (root / str(item["source_path"])).resolve()
        try:
            source.relative_to(root.resolve())
        except ValueError:
            return None
        return source

    @staticmethod
    def _caption(item: dict[str, Any]) -> str:
        fields = (
            item.get("image_caption"),
            item.get("nearby_text"),
            item.get("page_or_section"),
            Path(str(item.get("source_path", "image"))).stem,
        )
        caption = "。".join(
            str(value).strip() for value in fields if str(value or "").strip()
        )
        return caption or "教材图片，内容未标注"

    @staticmethod
    def _text_payload(
        item: dict[str, Any], version: IndexVersionInfo
    ) -> dict[str, Any]:
        return {
            "point_id": str(item["chunk_id"]),
            "document_id": item["document_id"],
            "chunk_id": item["chunk_id"],
            "course_id": item["course_id"],
            "chapter": item.get("chapter", "UNKNOWN"),
            "title": item.get("title", "UNKNOWN"),
            "content_type": item.get("content_type", "unknown"),
            "text": item["text"],
            "source_uri": item["source_uri"],
            "relative_path": item["relative_path"],
            "checksum": item["document_checksum"],
            "chunk_index": item["chunk_index"],
            "parent_section": item.get("title", "UNKNOWN"),
            "related_image_ids": item.get("related_images", []),
            "quality_status": "indexed",
            "index_version": version.version_id,
            "embedding_model": version.text_embedding_model,
            "embedding_revision": version.text_embedding_revision,
        }

    @classmethod
    def _image_payload(
        cls, item: dict[str, Any], version: IndexVersionInfo
    ) -> dict[str, Any]:
        return {
            "image_id": item["image_id"],
            "course_id": item["course_id"],
            "parent_document_id": item.get("parent_document_id"),
            "parent_chunk_id": item.get("parent_chunk_id"),
            "chapter": item.get("page_or_section", "UNKNOWN"),
            "image_type": item.get("image_type", "unknown"),
            "caption": cls._caption(item),
            "nearby_text": item.get("nearby_text", ""),
            "resource_uri": item["resource_uri"],
            "relative_path": item["source_path"],
            "checksum": item["checksum"],
            "width": item.get("width"),
            "height": item.get("height"),
            "description_source": item.get("description_source", "source_text"),
            "quality_status": item.get("quality_status", "unknown"),
            "index_version": version.version_id,
            "visual_model": version.image_embedding_model,
            "visual_revision": version.image_embedding_revision,
            "caption_embedding_model": version.text_embedding_model,
            "caption_embedding_revision": version.text_embedding_revision,
        }
