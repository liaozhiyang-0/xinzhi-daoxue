from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
from app.contracts import ExternalEvidenceItem, ExternalSourceType
from app.providers.retrieval import (
    AcademicSearchService,
    ArxivAcademicProvider,
    CnkiAcademicProvider,
    CrossrefAcademicProvider,
    OpenAlexAcademicProvider,
    SemanticScholarAcademicProvider,
)

ARXIV_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v2</id>
    <title>  A signal paper  </title>
    <summary>An abstract about filters.</summary>
    <published>2024-01-03T12:00:00Z</published>
    <updated>2024-02-03T12:00:00Z</updated>
    <author><name>Alice Example</name></author>
  </entry>
</feed>
"""


def transport_for(
    payload: str, *, content_type: str = "application/json"
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.scheme == "https"
        return httpx.Response(
            200,
            headers={"content-type": content_type},
            content=payload.encode("utf-8"),
        )

    return httpx.MockTransport(handler)


async def test_arxiv_provider_parses_atom_metadata() -> None:
    client = httpx.AsyncClient(
        transport=transport_for(ARXIV_XML, content_type="application/atom+xml")
    )
    try:
        provider = ArxivAcademicProvider(
            base_url="https://export.arxiv.org/api", client=client
        )
        items = await provider.search("signal processing", limit=3)
    finally:
        await client.aclose()

    assert len(items) == 1
    assert items[0].arxiv_id == "2401.12345v2"
    assert str(items[0].canonical_url) == "https://arxiv.org/abs/2401.12345v2"
    assert items[0].authors == ["Alice Example"]
    assert items[0].content_excerpt == "An abstract about filters."


async def test_crossref_provider_normalizes_doi_and_abstract() -> None:
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1234/example",
                    "title": ["A paper title"],
                    "author": [{"given": "Alice", "family": "Example"}],
                    "container-title": ["Test Journal"],
                    "abstract": "<jats:p>A paper abstract.</jats:p>",
                    "published": {"date-parts": [[2024, 2, 3]]},
                }
            ]
        }
    }
    client = httpx.AsyncClient(
        transport=transport_for(json.dumps(payload)),
    )
    try:
        provider = CrossrefAcademicProvider(
            base_url="https://api.crossref.org", client=client
        )
        items = await provider.search("signal processing", limit=3)
    finally:
        await client.aclose()

    assert items[0].doi == "10.1234/example"
    assert str(items[0].canonical_url) == "https://doi.org/10.1234/example"
    assert items[0].content_excerpt == "A paper abstract."
    assert items[0].venue == "Test Journal"


async def test_semantic_scholar_provider_preserves_external_ids() -> None:
    payload = {
        "data": [
            {
                "paperId": "paper-1",
                "title": "A graph paper",
                "abstract": "An abstract.",
                "authors": [{"name": "Bob Example"}],
                "venue": "Test Conference",
                "publicationDate": "2025-01-02",
                "url": "https://www.semanticscholar.org/paper/paper-1",
                "externalIds": {"DOI": "10.1234/graph", "ArXiv": "2501.00001"},
            }
        ]
    }
    client = httpx.AsyncClient(transport=transport_for(json.dumps(payload)))
    try:
        provider = SemanticScholarAcademicProvider(
            base_url="https://api.semanticscholar.org/graph/v1", client=client
        )
        items = await provider.search("graph learning", limit=3)
    finally:
        await client.aclose()

    assert items[0].doi == "10.1234/graph"
    assert items[0].arxiv_id == "2501.00001"
    assert items[0].authors == ["Bob Example"]


async def test_openalex_provider_reconstructs_abstract_and_metadata() -> None:
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "title": "An electronics paper",
                "doi": "https://doi.org/10.1234/electronics",
                "publication_date": "2025-02-03",
                "abstract_inverted_index": {"An": [0], "electronics": [1], "abstract.": [2]},
                "authorships": [{"author": {"display_name": "Alice Example"}}],
                "primary_location": {
                    "landing_page_url": "https://example.org/paper",
                    "source": {"display_name": "Example Journal"},
                },
            }
        ]
    }
    client = httpx.AsyncClient(transport=transport_for(json.dumps(payload)))
    try:
        provider = OpenAlexAcademicProvider(
            base_url="https://api.openalex.org", client=client
        )
        items = await provider.search("electronics", limit=3)
    finally:
        await client.aclose()

    assert items[0].provider == "openalex"
    assert items[0].content_excerpt == "An electronics abstract."
    assert items[0].authors == ["Alice Example"]
    assert items[0].venue == "Example Journal"


async def test_cnki_provider_uses_authorized_gateway_contract() -> None:
    payload = {
        "results": [
            {
                "id": "cnki-1",
                "title": "电子信息技术研究",
                "url": "https://kns.cnki.net/kcms/detail/1.html",
                "abstract": "本文研究电子信息技术。",
                "authors": ["张三"],
                "journal": "电子学报",
                "published_date": "2025-04-01",
            }
        ]
    }
    client = httpx.AsyncClient(transport=transport_for(json.dumps(payload)))
    try:
        provider = CnkiAcademicProvider(
            base_url="https://cnki-gateway.example/api/search", client=client
        )
        items = await provider.search("电子信息", limit=3)
    finally:
        await client.aclose()

    assert items[0].provider == "cnki"
    assert items[0].content_excerpt == "本文研究电子信息技术。"
    assert items[0].authors == ["张三"]
    assert items[0].venue == "电子学报"


async def test_academic_search_service_deduplicates_and_isolates_failures() -> None:
    class SuccessfulProvider:
        provider_name = "success"

        async def search(self, query: str, *, limit: int) -> list[ExternalEvidenceItem]:
            del query, limit
            item = ExternalEvidenceItem(
                evidence_id="success-1",
                source_type=ExternalSourceType.ACADEMIC_PAPER,
                provider=self.provider_name,
                source_ref="external://success/10.1234/example",
                title="Same paper",
                canonical_url="https://doi.org/10.1234/example",
                doi="10.1234/example",
                retrieved_at=datetime.now(UTC),
            )
            return [item, item.model_copy(update={"evidence_id": "success-2"})]

    class FailingProvider:
        provider_name = "failing"

        async def search(self, query: str, *, limit: int) -> list[ExternalEvidenceItem]:
            del query, limit
            raise RuntimeError("fixture failure")

    result = await AcademicSearchService(
        [SuccessfulProvider(), FailingProvider()]
    ).search("query", limit=3)

    assert result.status == "partial"
    assert result.provider_status == {"success": "completed", "failing": "failed"}
    assert result.warnings == ["failing: unavailable"]
    assert len(result.items) == 1


async def test_academic_search_service_filters_and_sorts_by_freshness() -> None:
    now = datetime.now(UTC)

    class Provider:
        provider_name = "freshness-fixture"

        async def search(self, query: str, *, limit: int) -> list[ExternalEvidenceItem]:
            del query, limit
            return [
                ExternalEvidenceItem(
                    evidence_id="old-paper",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref="external://fixture/old",
                    title="Old paper",
                    canonical_url="https://example.org/old",
                    published_at=now - timedelta(days=100),
                    retrieved_at=now,
                ),
                ExternalEvidenceItem(
                    evidence_id="new-paper",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref="external://fixture/new",
                    title="New paper",
                    canonical_url="https://example.org/new",
                    published_at=now - timedelta(days=2),
                    retrieved_at=now,
                ),
            ]

    result = await AcademicSearchService([Provider()]).search(
        "latest electronics papers", limit=5, freshness_days=30
    )

    assert [item.evidence_id for item in result.items] == ["new-paper"]


async def test_academic_search_service_keeps_available_fallback_when_window_is_empty() -> None:
    now = datetime.now(UTC)

    class Provider:
        provider_name = "fallback-fixture"

        async def search(self, query: str, *, limit: int) -> list[ExternalEvidenceItem]:
            del query, limit
            return [
                ExternalEvidenceItem(
                    evidence_id="available-paper",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref="external://fixture/available",
                    title="Available paper",
                    canonical_url="https://example.org/available",
                    published_at=now - timedelta(days=100),
                    retrieved_at=now,
                )
            ]

    result = await AcademicSearchService([Provider()]).search(
        "latest electronics papers", limit=5, freshness_days=30
    )

    assert [item.evidence_id for item in result.items] == ["available-paper"]
    assert result.warnings == [
        "no results within the last 30 days; showing the most recent available records"
    ]
