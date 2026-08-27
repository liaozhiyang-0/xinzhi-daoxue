from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.contracts import (
    ExternalEvidenceItem,
    ExternalRetrievalResult,
    ExternalSourceScope,
    ExternalSourceType,
)
from app.core.config import Settings
from app.database.base import Base
from app.database.session import create_engine_and_session
from app.services.research_knowledge import ResearchKnowledgeService
from app.services.vector_store import VectorSearchHit


class FakeEmbedding:
    dimension = 3

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0, 0.0] for text in texts]

    def embed_query(self, _query: str) -> list[float]:
        return [1.0, 1.0, 0.0]


class RecoverableVectorStore:
    def __init__(self) -> None:
        self.fail_upsert = True
        self.records: list[dict[str, Any]] = []
        self.ensure_calls = 0

    def research_collection_exists(self) -> bool:
        return False

    def ensure_research_collection(self, _dimension: int) -> None:
        self.ensure_calls += 1

    def upsert_research(
        self,
        records: list[dict[str, Any]],
        _vectors: list[list[float]],
    ) -> None:
        if self.fail_upsert:
            raise RuntimeError("qdrant temporarily unavailable")
        self.records.extend(records)

    def search_research(
        self,
        _vector: list[float],
        *,
        limit: int,
        topic: str = "",
    ) -> list[VectorSearchHit]:
        del topic
        if not self.records:
            return []
        return [
            VectorSearchHit(
                item_id="point-1",
                score=0.9,
                payload={"evidence_id": self.records[0]["evidence_id"]},
            )
        ][:limit]


def _item() -> ExternalEvidenceItem:
    return ExternalEvidenceItem(
        evidence_id="openalex-reindex-1",
        source_type=ExternalSourceType.ACADEMIC_PAPER,
        provider="openalex",
        source_ref="external://openalex/W-reindex-1",
        title="Flexible electronics evidence",
        canonical_url="https://example.org/reindex-1",
        content_excerpt="A durable abstract for local research retrieval.",
        retrieved_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_research_knowledge_reindexes_rows_after_vector_outage(
    tmp_path: Path,
) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'research.db'}",
        research_knowledge_enabled=True,
        _env_file=None,
    )
    engine, session_factory = create_engine_and_session(settings.database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    vectors = RecoverableVectorStore()
    service = ResearchKnowledgeService(
        settings,
        session_factory,
        FakeEmbedding(),
        vectors,
    )
    result = ExternalRetrievalResult(
        query="flexible electronics",
        normalized_query="flexible electronics",
        source_scopes=[ExternalSourceScope.ACADEMIC],
        items=[_item()],
    )

    stored = await service.ingest(result, query=result.query)
    assert stored["stored"] == 1
    assert stored["vector_indexed"] == 0

    vectors.fail_upsert = False
    assert await service.reindex_pending() == 1
    assert vectors.ensure_calls == 2
    assert vectors.records[0]["evidence_id"] == "openalex-reindex-1"
    restored = await service.search_evidence("flexible electronics")
    assert [item.evidence_id for item in restored] == ["openalex-reindex-1"]
    assert restored[0].title == "Flexible electronics evidence"
    service.settings = service.settings.model_copy(
        update={"research_knowledge_min_score": 0.95}
    )
    assert await service.search("flexible electronics") == []
    await engine.dispose()
