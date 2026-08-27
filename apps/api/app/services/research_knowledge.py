from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from pydantic import TypeAdapter
from pydantic.networks import AnyHttpUrl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts.external_retrieval import (
    ExternalEvidenceItem,
    ExternalRetrievalResult,
    ExternalSourceType,
)
from app.core.config import Settings
from app.models import ResearchEvidenceModel
from app.services.vector_store import VectorSearchHit, VectorStoreAdapter

logger = logging.getLogger(__name__)


class ResearchKnowledgeService:
    """Persist and maintain externally retrieved research evidence."""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        text_embedding: Any,
        vector_store: VectorStoreAdapter,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.text_embedding = text_embedding
        self.vector_store = vector_store

    async def ingest(
        self,
        result: ExternalRetrievalResult,
        *,
        query: str,
        task_id: str = "",
    ) -> dict[str, Any]:
        if not self.settings.research_knowledge_enabled or not result.items:
            return {"stored": 0, "vector_indexed": 0, "skipped": True}
        items = list(result.items)
        vector_indexed = False
        try:
            records = [self._vector_record(item, query) for item in items]
            texts = [self._index_text(item) for item in items]
            vectors = await asyncio.to_thread(self._embed_documents, texts)
            await asyncio.to_thread(
                self.vector_store.ensure_research_collection,
                self.text_embedding.dimension,
            )
            await asyncio.to_thread(self.vector_store.upsert_research, records, vectors)
            vector_indexed = True
        except Exception:
            logger.warning(
                "research_vector_ingest_failed task_id=%s", task_id, exc_info=True
            )

        now = datetime.now(UTC)
        async with self.session_factory() as db:
            for item in items:
                existing = await db.scalar(
                    select(ResearchEvidenceModel).where(
                        ResearchEvidenceModel.evidence_id == item.evidence_id
                    )
                )
                values = self._model_values(item, query, now, vector_indexed)
                if existing is None:
                    db.add(ResearchEvidenceModel(**values))
                else:
                    for key, value in values.items():
                        if key not in {"id", "evidence_id", "created_at"}:
                            setattr(existing, key, value)
            await db.commit()
        return {
            "stored": len(items),
            "vector_indexed": len(items) if vector_indexed else 0,
            "collection": self.settings.qdrant_research_collection,
        }

    async def maintain(self) -> dict[str, Any]:
        if not self.settings.research_knowledge_enabled:
            return {"stale": 0, "deleted_vectors": 0, "skipped": True}
        cutoff = datetime.now(UTC) - timedelta(
            days=self.settings.research_knowledge_retention_days
        )
        stale_ids: list[str] = []
        async with self.session_factory() as db:
            rows = (
                await db.scalars(
                    select(ResearchEvidenceModel).where(
                        ResearchEvidenceModel.status == "active",
                        ResearchEvidenceModel.last_seen_at < cutoff,
                    )
                )
            ).all()
            stale_ids = [row.evidence_id for row in rows]
            for row in rows:
                row.status = "stale"
                row.vector_indexed = False
            await db.commit()
        deleted = 0
        if stale_ids:
            try:
                deleted = await asyncio.to_thread(
                    self.vector_store.delete_research, stale_ids
                )
            except Exception:
                logger.warning("research_vector_maintenance_failed", exc_info=True)
        reindexed = await self.reindex_pending()
        return {
            "stale": len(stale_ids),
            "deleted_vectors": deleted,
            "reindexed": reindexed,
        }

    async def reindex_pending(self, *, limit: int = 256) -> int:
        """Repair missing research vectors without blocking task creation.

        SQL metadata is the durable source of truth.  A Qdrant restart or a
        first-time collection can therefore be repaired from active rows on
        the next deferred maintenance pass.
        """
        if not self.settings.research_knowledge_enabled or limit <= 0:
            return 0
        try:
            collection_exists = await asyncio.to_thread(
                self.vector_store.research_collection_exists
            )
        except Exception:
            logger.warning("research_vector_collection_check_failed", exc_info=True)
            collection_exists = False

        async with self.session_factory() as db:
            query = select(ResearchEvidenceModel).where(
                ResearchEvidenceModel.status == "active"
            )
            if collection_exists:
                query = query.where(ResearchEvidenceModel.vector_indexed.is_(False))
            rows = (
                await db.scalars(
                    query.order_by(ResearchEvidenceModel.updated_at.asc()).limit(limit)
                )
            ).all()
        if not rows:
            return 0

        items = [self._item_from_model(row) for row in rows]
        try:
            vectors = await asyncio.to_thread(
                self._embed_documents,
                [self._index_text(item) for item in items],
            )
            await asyncio.to_thread(
                self.vector_store.ensure_research_collection,
                self.text_embedding.dimension,
            )
            await asyncio.to_thread(
                self.vector_store.upsert_research,
                [
                    self._vector_record(item, row.topic)
                    for item, row in zip(items, rows, strict=True)
                ],
                vectors,
            )
        except Exception:
            logger.warning("research_vector_reindex_failed", exc_info=True)
            return 0

        async with self.session_factory() as db:
            row_ids = [row.id for row in rows]
            stored_rows = (
                await db.scalars(
                    select(ResearchEvidenceModel).where(
                        ResearchEvidenceModel.id.in_(row_ids)
                    )
                )
            ).all()
            for row in stored_rows:
                row.vector_indexed = True
            await db.commit()
        return len(rows)

    async def search(
        self, query: str, *, limit: int | None = None
    ) -> list[VectorSearchHit]:
        if not query.strip() or not self.settings.research_knowledge_enabled:
            return []
        try:
            await asyncio.to_thread(
                self.vector_store.ensure_research_collection,
                self.text_embedding.dimension,
            )
            vector = await asyncio.to_thread(self.text_embedding.embed_query, query)
            hits = await asyncio.to_thread(
                self.vector_store.search_research,
                vector,
                limit=limit or self.settings.research_knowledge_search_top_k,
            )
            return [
                hit
                for hit in hits
                if hit.score >= self.settings.research_knowledge_min_score
            ]
        except Exception:
            logger.warning("research_vector_search_failed", exc_info=True)
            return []

    async def search_evidence(
        self, query: str, *, limit: int | None = None
    ) -> list[ExternalEvidenceItem]:
        """Resolve vector hits back to complete, provenance-safe evidence."""

        hits = await self.search(query, limit=limit)
        evidence_ids = list(
            dict.fromkeys(
                str(hit.payload.get("evidence_id") or hit.item_id)
                for hit in hits
                if str(hit.payload.get("evidence_id") or hit.item_id).strip()
            )
        )
        if not evidence_ids:
            return []
        async with self.session_factory() as db:
            rows = (
                await db.scalars(
                    select(ResearchEvidenceModel).where(
                        ResearchEvidenceModel.evidence_id.in_(evidence_ids),
                        ResearchEvidenceModel.status == "active",
                    )
                )
            ).all()
        by_id = {row.evidence_id: row for row in rows}
        evidence: list[ExternalEvidenceItem] = []
        for hit in hits:
            evidence_id = str(
                hit.payload.get("evidence_id") or hit.item_id
            ).strip()
            row = by_id.get(evidence_id)
            if row is None:
                continue
            try:
                item = self._item_from_model(row)
                evidence.append(
                    item.model_copy(
                        update={
                            "relevance_score": max(
                                item.relevance_score,
                                min(1.0, max(0.0, float(hit.score))),
                            )
                        }
                    )
                )
            except Exception:
                logger.warning(
                    "research_evidence_restore_failed evidence_id=%s",
                    evidence_id,
                    exc_info=True,
                )
        return evidence

    @staticmethod
    def _item_from_model(row: ResearchEvidenceModel) -> ExternalEvidenceItem:
        trust_level = cast(
            Literal["high", "medium", "low", "unknown"],
            row.trust_level
            if row.trust_level in {"high", "medium", "low", "unknown"}
            else "unknown",
        )
        return ExternalEvidenceItem(
            evidence_id=row.evidence_id,
            source_type=ExternalSourceType(row.source_type),
            provider=row.provider,
            source_ref=row.source_ref,
            title=row.title,
            canonical_url=TypeAdapter(AnyHttpUrl).validate_python(row.canonical_url),
            content_excerpt=row.content_excerpt,
            authors=list(row.authors or []),
            venue=row.venue,
            published_at=ResearchKnowledgeService._as_utc(row.published_at),
            updated_at=ResearchKnowledgeService._as_utc(row.source_updated_at),
            retrieved_at=ResearchKnowledgeService._as_required_utc(row.retrieved_at),
            doi=row.doi,
            arxiv_id=row.arxiv_id,
            citation_count=row.citation_count,
            content_hash=row.content_hash,
            relevance_score=row.relevance_score,
            trust_level=trust_level,
            metadata=dict(row.source_metadata or {}),
        )

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _as_required_utc(value: datetime | None) -> datetime:
        normalized = ResearchKnowledgeService._as_utc(value)
        if normalized is None:
            raise ValueError("research evidence retrieved_at is required")
        return normalized

    def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Support both the RAG provider and the legacy embedding contract."""

        embed_documents = getattr(self.text_embedding, "embed_documents", None)
        if not callable(embed_documents):
            embed_documents = getattr(self.text_embedding, "embed_texts", None)
        if not callable(embed_documents):
            raise TypeError("text embedding provider lacks a document method")
        return cast(list[list[float]], embed_documents(texts))

    async def status(self) -> dict[str, Any]:
        async with self.session_factory() as db:
            count_rows = (
                await db.execute(
                    select(
                        ResearchEvidenceModel.status,
                        func.count(ResearchEvidenceModel.id),
                    ).group_by(ResearchEvidenceModel.status)
                )
            ).all()
            counts: dict[str, int] = {
                str(row[0]): int(row[1]) for row in count_rows
            }
            latest = await db.scalar(
                select(func.max(ResearchEvidenceModel.last_seen_at))
            )
        return {
            "enabled": self.settings.research_knowledge_enabled,
            "collection": self.settings.qdrant_research_collection,
            "counts": counts,
            "latest_seen_at": latest.isoformat() if latest else None,
            "retention_days": self.settings.research_knowledge_retention_days,
        }

    def _index_text(self, item: ExternalEvidenceItem) -> str:
        metadata = " ".join(
            f"{key}: {value}" for key, value in item.metadata.items() if value
        )
        text = "\n".join(
            part
            for part in (
                item.title,
                ", ".join(item.authors),
                item.venue,
                item.content_excerpt,
                metadata,
            )
            if part
        )
        # Keep the dedicated index bounded for the tokenizer used by the
        # local embedding provider; the database still retains the full excerpt.
        max_chars = max(400, min(self.settings.text_embedding_max_length, 800))
        return text[:max_chars]

    @classmethod
    def _vector_record(cls, item: ExternalEvidenceItem, query: str) -> dict[str, Any]:
        return {
            "evidence_id": item.evidence_id,
            "topic": query[:500],
            "source_type": item.source_type.value,
            "provider": item.provider,
            "title": item.title,
            "canonical_url": str(item.canonical_url),
            "status": "active",
            "content_hash": item.content_hash,
        }

    @classmethod
    def _model_values(
        cls,
        item: ExternalEvidenceItem,
        query: str,
        now: datetime,
        vector_indexed: bool,
    ) -> dict[str, Any]:
        return {
            "evidence_id": item.evidence_id,
            "topic": query[:500],
            "source_type": item.source_type.value,
            "provider": item.provider,
            "source_ref": item.source_ref,
            "canonical_url": str(item.canonical_url),
            "title": item.title,
            "content_excerpt": item.content_excerpt,
            "authors": item.authors,
            "venue": item.venue,
            "published_at": item.published_at,
            "source_updated_at": item.updated_at,
            "retrieved_at": item.retrieved_at,
            "last_seen_at": now,
            "doi": item.doi,
            "arxiv_id": item.arxiv_id,
            "citation_count": item.citation_count,
            "content_hash": item.content_hash,
            "relevance_score": item.relevance_score,
            "trust_level": item.trust_level,
            "source_metadata": item.metadata,
            "vector_indexed": vector_indexed,
            "status": "active",
            "updated_at": now,
        }
