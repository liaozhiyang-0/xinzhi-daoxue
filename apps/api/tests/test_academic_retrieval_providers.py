from __future__ import annotations

import asyncio
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
    ProviderSearchContext,
    SemanticScholarAcademicProvider,
)
from app.providers.retrieval.academic import AcademicProviderError

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


async def test_arxiv_context_uses_boolean_query_and_bounded_candidates() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update({key: value for key, value in request.url.params.multi_items()})
        return httpx.Response(
            200,
            headers={"content-type": "application/atom+xml"},
            content=ARXIV_XML.encode("utf-8"),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = ArxivAcademicProvider(
            base_url="https://export.arxiv.org/api",
            client=client,
            min_delay_seconds=0,
        )
        items = await provider.search_with_context(
            ProviderSearchContext(
                query="近三年柔性电子器件进展",
                normalized_query="近三年柔性电子器件进展",
                limit=2,
                freshness_days=1095,
            )
        )
    finally:
        await client.aclose()

    assert items
    assert "all:flexible" in captured["search_query"]
    assert "all:electronics" in captured["search_query"]
    assert captured["max_results"] == "4"


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


async def test_crossref_context_uses_polite_pool_and_date_filter() -> None:
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1234/flexible",
                    "title": ["Flexible electronics sensor"],
                    "published": {"date-parts": [[2025, 2, 3]]},
                    "URL": "https://doi.org/10.1234/flexible",
                    "container-title": ["Flexible Journal"],
                }
            ]
        }
    }
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update({key: value for key, value in request.url.params.multi_items()})
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=json.dumps(payload).encode("utf-8"),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = CrossrefAcademicProvider(
            base_url="https://api.crossref.org",
            mailto="research@example.org",
            client=client,
            min_delay_seconds=0,
        )
        items = await provider.search_with_context(
            ProviderSearchContext(
                query="近三年柔性电子器件进展",
                normalized_query="近三年柔性电子器件进展",
                limit=2,
                freshness_days=1095,
            )
        )
    finally:
        await client.aclose()

    assert items[0].metadata["query_adapter"] == "crossref_v1"
    assert captured["mailto"] == "research@example.org"
    assert "from-pub-date:" in captured["filter"]
    assert "flexible electronics" in captured["query.bibliographic"]


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
                "abstract_inverted_index": {
                    "An": [0],
                    "electronics": [1],
                    "abstract.": [2],
                },
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


async def test_http_provider_tracks_request_counts_and_peak_concurrency() -> None:
    active = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        del request
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=json.dumps({"message": {"items": []}}).encode("utf-8"),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = CrossrefAcademicProvider(
            base_url="https://api.crossref.org",
            client=client,
            min_delay_seconds=0,
            max_concurrency=1,
        )
        await asyncio.gather(
            provider.search("electronics", limit=1),
            provider.search("flexible electronics", limit=1),
        )
    finally:
        await client.aclose()

    stats = provider.runtime_stats()
    assert stats["requests_started"] == 2
    assert stats["requests_completed"] == 2
    assert stats["peak_active_requests"] == 1
    assert peak == 1


async def test_openalex_adapter_translates_question_and_applies_date_filter() -> None:
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W456",
                "title": "Flexible electronics sensor platform",
                "publication_date": "2025-02-03",
                "abstract_inverted_index": {
                    "Flexible": [0],
                    "electronics": [1],
                    "sensor": [2],
                },
                "primary_location": {
                    "landing_page_url": "https://example.org/flexible",
                    "source": {"display_name": "Flexible Journal"},
                },
            }
        ]
    }
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update({key: value for key, value in request.url.params.multi_items()})
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=json.dumps(payload).encode("utf-8"),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = OpenAlexAcademicProvider(
            base_url="https://api.openalex.org", client=client
        )
        items = await provider.search_with_context(
            ProviderSearchContext(
                query="近三年柔性电子器件有哪些关键进展？",
                normalized_query="近三年柔性电子器件有哪些关键进展？",
                limit=3,
                freshness_days=1095,
            )
        )
    finally:
        await client.aclose()

    assert items
    assert "flexible electronics" in captured["search"]
    assert "from_publication_date:" in captured["filter"]
    assert "to_publication_date:" in captured["filter"]
    assert items[0].metadata["query_adapter"] == "openalex_v1"


async def test_openalex_retries_rate_limit_using_retry_after() -> None:
    calls = 0
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W789",
                "title": "A flexible electronics paper",
                "publication_date": "2025-02-03",
                "abstract_inverted_index": {"Flexible": [0], "electronics": [1]},
                "primary_location": {
                    "landing_page_url": "https://example.org/flexible-789"
                },
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=json.dumps(payload).encode("utf-8"),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = OpenAlexAcademicProvider(
            base_url="https://api.openalex.org",
            client=client,
            min_delay_seconds=0,
        )
        result = await AcademicSearchService(
            [provider], cache_size=0, max_retries=1
        ).search("flexible electronics", limit=1)
    finally:
        await client.aclose()

    assert calls == 2
    assert result.status == "completed"
    assert result.provider_status == {"openalex": "completed"}
    assert result.items[0].evidence_id == "openalex-W789"


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


async def test_academic_search_service_keeps_available_fallback_when_window_is_empty(
) -> None:
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


async def test_academic_search_service_retries_and_caches_successful_results() -> None:
    calls = 0

    class Provider:
        provider_name = "retry-fixture"

        async def search(self, query: str, *, limit: int) -> list[ExternalEvidenceItem]:
            nonlocal calls
            del query, limit
            calls += 1
            if calls == 1:
                raise AcademicProviderError("retry-fixture: timeout")
            return [
                ExternalEvidenceItem(
                    evidence_id="retry-paper",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref="external://fixture/retry",
                    title="Retry paper",
                    canonical_url="https://example.org/retry",
                    retrieved_at=datetime.now(UTC),
                )
            ]

    service = AcademicSearchService(
        [Provider()], cache_size=4, cache_ttl_seconds=60, max_retries=1
    )
    first = await service.search("retry query", limit=3, retrieval_trace_id="trace-1")
    second = await service.search("retry query", limit=3, retrieval_trace_id="trace-2")

    assert first.items[0].evidence_id == "retry-paper"
    assert calls == 2
    assert second.cache_hit is True
    assert second.retrieval_trace_id == "trace-2"
    assert service.health()["cache"]["entries"] == 1


async def test_academic_search_service_cools_down_rate_limited_provider() -> None:
    calls = 0

    class RateLimitedProvider:
        provider_name = "rate-limited-fixture"

        async def search(self, query: str, *, limit: int) -> list[ExternalEvidenceItem]:
            nonlocal calls
            del query, limit
            calls += 1
            raise AcademicProviderError("rate-limited-fixture: rate_limited")

    service = AcademicSearchService(
        [RateLimitedProvider()],
        cache_size=0,
        max_retries=0,
        rate_limit_cooldown_seconds=60,
    )

    first = await service.search("cooldown query", limit=1)
    second = await service.search("cooldown query 2", limit=1)

    assert first.provider_status == {"rate-limited-fixture": "rate_limited"}
    assert second.provider_status == {"rate-limited-fixture": "rate_limited"}
    assert calls == 1
    assert service.health()["rate_limit_cooldowns"]


async def test_academic_search_service_prioritizes_relevance_before_recency() -> None:
    now = datetime.now(UTC)

    class Provider:
        provider_name = "ranking-fixture"

        async def search(self, query: str, *, limit: int) -> list[ExternalEvidenceItem]:
            del query, limit
            return [
                ExternalEvidenceItem(
                    evidence_id="recent-low-relevance",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref="external://ranking/recent",
                    title="Recent but weak match",
                    canonical_url="https://example.org/recent",
                    published_at=now,
                    retrieved_at=now,
                    relevance_score=0.2,
                ),
                ExternalEvidenceItem(
                    evidence_id="older-high-relevance",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref="external://ranking/older",
                    title="Older but strong match",
                    canonical_url="https://example.org/older",
                    published_at=now - timedelta(days=90),
                    retrieved_at=now,
                    relevance_score=0.9,
                ),
            ]

    result = await AcademicSearchService(
        [Provider()], cache_size=0, max_retries=0
    ).search("ranking query", limit=2)

    assert [item.evidence_id for item in result.items] == [
        "older-high-relevance",
        "recent-low-relevance",
    ]


async def test_academic_search_service_stops_after_satisfied_provider_tier() -> None:
    calls = {"first": 0, "fallback": 0}

    class FirstProvider:
        provider_name = "first"

        async def search(self, query: str, *, limit: int) -> list[ExternalEvidenceItem]:
            del query, limit
            calls["first"] += 1
            return [
                ExternalEvidenceItem(
                    evidence_id="first-result",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref="external://first/result",
                    title="First result",
                    canonical_url="https://example.org/first",
                    retrieved_at=datetime.now(UTC),
                )
            ]

    class FallbackProvider:
        provider_name = "fallback"

        async def search(self, query: str, *, limit: int) -> list[ExternalEvidenceItem]:
            del query, limit
            calls["fallback"] += 1
            return []

    service = AcademicSearchService(
        [FirstProvider(), FallbackProvider()],
        cache_size=0,
        max_retries=0,
        provider_tiers=(("first",), ("fallback",)),
    )
    result = await service.search("tiered query", limit=1)

    assert result.status == "completed"
    assert result.provider_status == {"first": "completed"}
    assert calls == {"first": 1, "fallback": 0}


async def test_academic_search_service_exposes_remaining_fallback_tiers() -> None:
    class Provider:
        def __init__(self, name: str) -> None:
            self.provider_name = name

    service = AcademicSearchService(
        [Provider("primary"), Provider("fallback"), Provider("last-resort")],
        cache_size=0,
        provider_tiers=(("primary",), ("fallback",), ("last-resort",)),
    )

    assert service.fallback_provider_names() == ("fallback", "last-resort")


async def test_academic_search_many_covers_all_variants_before_review() -> None:
    calls: list[str] = []

    class Provider:
        provider_name = "variant-fixture"

        async def search(self, query: str, *, limit: int) -> list[ExternalEvidenceItem]:
            del limit
            calls.append(query)
            return [
                ExternalEvidenceItem(
                    evidence_id="variant-result",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref="external://variant/result",
                    title="Variant result",
                    canonical_url="https://example.org/variant",
                    retrieved_at=datetime.now(UTC),
                )
            ]

    service = AcademicSearchService([Provider()], cache_size=0, max_retries=0)
    result = await service.search_many(
        "variant query",
        query_variants=["first variant", "second variant", "third variant"],
        limit=1,
    )

    assert result.status == "completed"
    assert calls == ["first variant", "second variant"]
    assert result.search_queries == ["first variant", "second variant"]
