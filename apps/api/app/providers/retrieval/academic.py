from __future__ import annotations

import asyncio
import hashlib
import html
import inspect
import re
import xml.etree.ElementTree as ElementTree
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

import httpx
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from app.contracts import (
    ExternalEvidenceItem,
    ExternalRetrievalResult,
    ExternalSourceScope,
    ExternalSourceType,
)

ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
HTML_TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")
_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


class AcademicSearchProvider(Protocol):
    provider_name: str
    source_scope: ExternalSourceScope

    async def search(
        self, query: str, *, limit: int, prefer_high_citation: bool = False
    ) -> list[ExternalEvidenceItem]: ...


class AcademicProviderError(RuntimeError):
    """A source-specific error that the aggregate service can isolate."""


class HttpAcademicProvider(ABC):
    provider_name: str
    source_scope = ExternalSourceScope.ACADEMIC

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds)
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str, *, params: dict[str, Any]) -> httpx.Response:
        try:
            response = await self._client.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params,
                headers={"User-Agent": "xinzhi-daoxue/1.0 (academic retrieval)"},
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise AcademicProviderError(f"{self.provider_name}: timeout") from exc
        except httpx.HTTPStatusError as exc:
            raise AcademicProviderError(
                f"{self.provider_name}: http_{exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise AcademicProviderError(
                f"{self.provider_name}: request_failed"
            ) from exc

    async def _get_with_headers(
        self,
        path: str,
        *,
        params: dict[str, Any],
        headers: dict[str, str] | None,
    ) -> httpx.Response:
        try:
            request_headers = {
                "User-Agent": "xinzhi-daoxue/1.0 (academic retrieval)"
            }
            if headers:
                request_headers.update(headers)
            response = await self._client.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params,
                headers=request_headers,
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise AcademicProviderError(f"{self.provider_name}: timeout") from exc
        except httpx.HTTPStatusError as exc:
            raise AcademicProviderError(
                f"{self.provider_name}: http_{exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise AcademicProviderError(
                f"{self.provider_name}: request_failed"
            ) from exc

    @abstractmethod
    async def search(self, query: str, *, limit: int) -> list[ExternalEvidenceItem]: ...


class ArxivAcademicProvider(HttpAcademicProvider):
    provider_name = "arxiv"

    async def search(
        self, query: str, *, limit: int, prefer_high_citation: bool = False
    ) -> list[ExternalEvidenceItem]:
        response = await self._get(
            "query",
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": limit,
                "sortBy": "submittedDate" if _looks_fresh_query(query) else "relevance",
                "sortOrder": "descending",
            },
        )
        try:
            root = ElementTree.fromstring(response.text)
        except ElementTree.ParseError as exc:
            raise AcademicProviderError("arxiv: invalid_xml") from exc

        now = datetime.now(UTC)
        items: list[ExternalEvidenceItem] = []
        for rank, entry in enumerate(root.findall(f"{{{ATOM_NAMESPACE}}}entry")):
            abstract_url = _normalize_arxiv_url(_text(entry, "id"))
            title = _clean_text(_text(entry, "title"))
            if not abstract_url or not title:
                continue
            paper_id = abstract_url.rstrip("/").split("/abs/")[-1]
            authors = [
                _clean_text(_text(author, "name"))
                for author in entry.findall(f"{{{ATOM_NAMESPACE}}}author")
            ]
            items.append(
                ExternalEvidenceItem(
                    evidence_id=f"arxiv-{paper_id.replace('/', '-')}",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref=f"external://arxiv/{paper_id}",
                    title=title,
                    canonical_url=_http_url(abstract_url),
                    content_excerpt=_clean_text(_text(entry, "summary")),
                    authors=authors,
                    published_at=_parse_datetime(_text(entry, "published")),
                    updated_at=_parse_datetime(_text(entry, "updated")),
                    retrieved_at=now,
                    arxiv_id=paper_id,
                    relevance_score=max(0.0, 1.0 - rank / max(limit, 1)),
                    trust_level="medium",
                )
            )
        return items


class CrossrefAcademicProvider(HttpAcademicProvider):
    provider_name = "crossref"

    async def search(
        self, query: str, *, limit: int, prefer_high_citation: bool = False
    ) -> list[ExternalEvidenceItem]:
        today = datetime.now(UTC).date().isoformat()
        response = await self._get(
            "works",
            params={
                "query.bibliographic": query,
                "rows": min(50, max(limit * 4, limit)),
                "filter": f"until-pub-date:{today}",
                "select": (
                    "DOI,title,author,container-title,abstract,URL,published,"
                    "created,type,is-referenced-by-count"
                ),
                "sort": (
                    "is-referenced-by-count" if prefer_high_citation else "published"
                ),
                "order": "desc",
            },
        )
        try:
            payload = response.json()
            records = payload["message"]["items"]
        except (TypeError, KeyError, ValueError) as exc:
            raise AcademicProviderError("crossref: invalid_json") from exc

        now = datetime.now(UTC)
        items: list[ExternalEvidenceItem] = []
        for rank, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            title = _first_string(record.get("title"))
            doi = str(record.get("DOI", "")).strip()
            url = f"https://doi.org/{doi}" if doi else str(record.get("URL", ""))
            if not title or not url.startswith(("http://", "https://")):
                continue
            stable_id = doi or _stable_id(title)
            try:
                item = ExternalEvidenceItem(
                    evidence_id=f"crossref-{_safe_id(stable_id)}",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref=f"external://crossref/{stable_id}",
                    title=title,
                    canonical_url=_http_url(url),
                    content_excerpt=_clean_text(str(record.get("abstract", ""))),
                    authors=_authors(record.get("author")),
                    venue=_first_string(record.get("container-title")),
                    published_at=_crossref_date(record.get("published")),
                    updated_at=_crossref_date(record.get("updated")),
                    retrieved_at=now,
                    doi=doi,
                    citation_count=_citation_count(
                        record.get("is-referenced-by-count")
                    ),
                    relevance_score=max(0.0, 1.0 - rank / max(limit, 1)),
                    trust_level="high",
                    metadata={"type": str(record.get("type", ""))},
                )
            except ValidationError:
                continue
            items.append(item)
        return items


class SemanticScholarAcademicProvider(HttpAcademicProvider):
    provider_name = "semantic_scholar"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        super().__init__(
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
        )
        self.api_key = api_key

    async def search(
        self, query: str, *, limit: int, prefer_high_citation: bool = False
    ) -> list[ExternalEvidenceItem]:
        headers = {"x-api-key": self.api_key} if self.api_key else None
        response = await self._get_with_headers(
            "paper/search",
            params={
                "query": query,
                "limit": limit,
                "fields": (
                    "paperId,title,abstract,authors,venue,year,publicationDate,"
                    "url,externalIds,citationCount"
                ),
            },
            headers=headers,
        )
        try:
            records = response.json()["data"]
        except (TypeError, KeyError, ValueError) as exc:
            raise AcademicProviderError("semantic_scholar: invalid_json") from exc

        now = datetime.now(UTC)
        items: list[ExternalEvidenceItem] = []
        for rank, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            paper_id = str(record.get("paperId", "")).strip()
            title = str(record.get("title", "")).strip()
            if not paper_id or not title:
                continue
            external_ids = record.get("externalIds") or {}
            doi = str(external_ids.get("DOI", "")).strip()
            arxiv_id = str(external_ids.get("ArXiv", "")).strip()
            url = str(record.get("url", "")).strip() or (
                f"https://www.semanticscholar.org/paper/{paper_id}"
            )
            items.append(
                ExternalEvidenceItem(
                    evidence_id=f"semantic-scholar-{_safe_id(paper_id)}",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref=f"external://semantic-scholar/{paper_id}",
                    title=title,
                    canonical_url=_http_url(url),
                    content_excerpt=str(record.get("abstract", "") or "").strip(),
                    authors=[
                        str(author.get("name", "")).strip()
                        for author in record.get("authors", [])
                        if (
                            isinstance(author, dict)
                            and str(author.get("name", "")).strip()
                        )
                    ],
                    venue=str(record.get("venue", "") or "").strip(),
                    published_at=_parse_date(str(record.get("publicationDate", ""))),
                    retrieved_at=now,
                    doi=doi,
                    arxiv_id=arxiv_id,
                    citation_count=_citation_count(record.get("citationCount")),
                    relevance_score=max(0.0, 1.0 - rank / max(limit, 1)),
                    trust_level="medium",
                )
            )
        return items


class OpenAlexAcademicProvider(HttpAcademicProvider):
    """OpenAlex works search with abstract reconstruction from its index."""

    provider_name = "openalex"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        mailto: str = "",
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        super().__init__(
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
        )
        self.api_key = api_key.strip()
        self.mailto = mailto.strip()

    async def search(
        self, query: str, *, limit: int, prefer_high_citation: bool = False
    ) -> list[ExternalEvidenceItem]:
        today = datetime.now(UTC).date().isoformat()
        params: dict[str, Any] = {
            "search": query,
            "per-page": min(50, max(limit * 4, limit)),
            "filter": f"has_abstract:true,to_publication_date:{today}",
            "sort": (
                "cited_by_count:desc"
                if prefer_high_citation
                else "publication_date:desc"
            ),
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.mailto:
            params["mailto"] = self.mailto
        response = await self._get("works", params=params)
        try:
            records = response.json()["results"]
        except (TypeError, KeyError, ValueError) as exc:
            raise AcademicProviderError("openalex: invalid_json") from exc
        if not isinstance(records, list):
            raise AcademicProviderError("openalex: invalid_results")

        now = datetime.now(UTC)
        items: list[ExternalEvidenceItem] = []
        for rank, record in enumerate(records[:limit]):
            if not isinstance(record, dict):
                continue
            title = str(record.get("title", "")).strip()
            work_id = str(record.get("id", "")).strip()
            if not title or not work_id:
                continue
            doi = str(record.get("doi", "")).strip()
            location = record.get("primary_location") or {}
            canonical_url = (
                doi
                or str(location.get("landing_page_url", "")).strip()
                or work_id
            )
            if not canonical_url.startswith(("http://", "https://")):
                continue
            source = location.get("source") or {}
            items.append(
                ExternalEvidenceItem(
                    evidence_id=f"openalex-{_safe_id(work_id.rsplit('/', 1)[-1])}",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref=f"external://openalex/{work_id.rsplit('/', 1)[-1]}",
                    title=title,
                    canonical_url=_http_url(canonical_url),
                    content_excerpt=_openalex_abstract(record.get("abstract_inverted_index")),
                    authors=_openalex_authors(record.get("authorships")),
                    venue=str(source.get("display_name", "") or "").strip(),
                    published_at=_parse_date(str(record.get("publication_date", ""))),
                    retrieved_at=now,
                    doi=doi.removeprefix("https://doi.org/"),
                    citation_count=_citation_count(record.get("cited_by_count")),
                    relevance_score=max(0.0, 1.0 - rank / max(limit, 1)),
                    trust_level="high",
                    metadata={"openalex_id": work_id},
                )
            )
        return items


class CnkiAcademicProvider(HttpAcademicProvider):
    """CNKI adapter for an authorized JSON gateway or institutional proxy.

    CNKI does not expose a stable anonymous public metadata API. The gateway
    contract keeps credentials and institutional access outside this service.
    """

    provider_name = "cnki"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        auth_header: str = "x-api-key",
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 8,
    ) -> None:
        super().__init__(
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
        )
        self.api_key = api_key.strip()
        self.auth_header = auth_header.strip() or "x-api-key"

    async def search(
        self, query: str, *, limit: int, prefer_high_citation: bool = False
    ) -> list[ExternalEvidenceItem]:
        if not self.base_url:
            raise AcademicProviderError(
                "cnki: not_configured (an authorized JSON gateway is required)"
            )
        headers = {self.auth_header: self.api_key} if self.api_key else None
        response = await self._get_with_headers(
            "",
            params={"query": query, "limit": limit},
            headers=headers,
        )
        try:
            payload = response.json()
            records = payload.get("results", payload.get("data", []))
        except (AttributeError, TypeError, ValueError) as exc:
            raise AcademicProviderError("cnki: invalid_json") from exc
        if not isinstance(records, list):
            raise AcademicProviderError("cnki: invalid_results")

        now = datetime.now(UTC)
        items: list[ExternalEvidenceItem] = []
        for rank, record in enumerate(records[:limit]):
            if not isinstance(record, dict):
                continue
            title = str(record.get("title", "")).strip()
            url = str(
                record.get("url", record.get("link", record.get("canonical_url", "")))
            ).strip()
            if not title or not url:
                continue
            doi = str(record.get("doi", "")).strip()
            items.append(
                ExternalEvidenceItem(
                    evidence_id=f"cnki-{_safe_id(str(record.get('id', rank)))}",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref=f"external://cnki/{_safe_id(url)}",
                    title=title,
                    canonical_url=_http_url(url),
                    content_excerpt=str(
                        record.get(
                            "abstract", record.get("content", record.get("snippet", ""))
                        )
                        or ""
                    ).strip(),
                    authors=_record_authors(record.get("authors")),
                    venue=str(
                        record.get("venue", record.get("journal", "")) or ""
                    ).strip(),
                    published_at=_parse_date(str(record.get("published_date", ""))),
                    retrieved_at=now,
                    doi=doi,
                    citation_count=_citation_count(
                        record.get(
                            "citation_count",
                            record.get("cited_by_count", record.get("citations")),
                        )
                    ),
                    relevance_score=max(0.0, 1.0 - rank / max(limit, 1)),
                    trust_level="medium",
                    metadata={"gateway": self.base_url},
                )
            )
        return items


class AcademicSearchService:
    """Fan out to academic providers and return a bounded, deduplicated result."""

    def __init__(self, providers: Sequence[AcademicSearchProvider]) -> None:
        self.providers = tuple(providers)

    async def search(
        self,
        query: str,
        *,
        limit: int = 8,
        normalized_query: str | None = None,
        retrieval_trace_id: str = "",
        provider_names: Sequence[str] | None = None,
        source_scopes: Sequence[ExternalSourceScope] | None = None,
        freshness_days: int | None = None,
        prefer_high_citation: bool = False,
    ) -> ExternalRetrievalResult:
        normalized = " ".join((normalized_query or query).split())
        allowed = (
            {name.casefold() for name in provider_names} if provider_names else None
        )
        allowed_scopes = set(source_scopes) if source_scopes else None
        providers = tuple(
            provider
            for provider in self.providers
            if (allowed is None or provider.provider_name.casefold() in allowed)
            and (
                allowed_scopes is None
                or getattr(provider, "source_scope", ExternalSourceScope.ACADEMIC)
                in allowed_scopes
            )
        )
        if not providers:
            return ExternalRetrievalResult(
                query=query,
                normalized_query=normalized,
                source_scopes=[],
                status="disabled",
                retrieval_trace_id=retrieval_trace_id,
            )

        async def run_provider(
            provider: AcademicSearchProvider,
        ) -> list[ExternalEvidenceItem]:
            kwargs: dict[str, Any] = {
                "limit": min(50, max(limit, limit * 3 if freshness_days else limit))
            }
            if prefer_high_citation and "prefer_high_citation" in inspect.signature(
                provider.search
            ).parameters:
                kwargs["prefer_high_citation"] = True
            return await provider.search(normalized, **kwargs)

        responses = await asyncio.gather(
            *(run_provider(provider) for provider in providers),
            return_exceptions=True,
        )
        items: list[ExternalEvidenceItem] = []
        provider_status: dict[str, str] = {}
        warnings: list[str] = []
        successful = 0
        scopes: list[ExternalSourceScope] = []
        for provider, response in zip(providers, responses, strict=True):
            if isinstance(response, BaseException):
                provider_status[provider.provider_name] = "failed"
                if isinstance(response, AcademicProviderError):
                    warnings.append(str(response))
                else:
                    warnings.append(f"{provider.provider_name}: unavailable")
                continue
            successful += 1
            provider_status[provider.provider_name] = "completed"
            scope = getattr(provider, "source_scope", ExternalSourceScope.ACADEMIC)
            if scope not in scopes:
                scopes.append(scope)
            items.extend(response)
            if not response:
                warnings.append(f"{provider.provider_name}: no records returned")

        deduplicated = _deduplicate(items)
        if freshness_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=freshness_days)
            grouped: dict[str, list[ExternalEvidenceItem]] = {}
            for item in deduplicated:
                grouped.setdefault(item.provider, []).append(item)
            freshness_filtered: list[ExternalEvidenceItem] = []
            for _provider_name, provider_items in grouped.items():
                fresh_items = [
                    item
                    for item in provider_items
                    for item_date in [(item.updated_at or item.published_at)]
                    if item_date is not None and item_date >= cutoff
                ]
                if fresh_items:
                    freshness_filtered.extend(fresh_items)
                    continue
                # Keep a useful, verifiable fallback when one source has no
                # records inside the requested window. The warning makes the
                # freshness trade-off visible without hiding other sources.
                freshness_filtered.extend(provider_items)
                warnings.append(
                    "no results within the last "
                    f"{freshness_days} days; "
                    "showing the most recent available records"
                )
            deduplicated = freshness_filtered
        deduplicated.sort(
            key=lambda item: (
                (item.citation_count is not None)
                if prefer_high_citation
                else False,
                (item.citation_count or -1) if prefer_high_citation else 0,
                item.updated_at
                or item.published_at
                or datetime.min.replace(tzinfo=UTC),
                item.relevance_score,
            ),
            reverse=True,
        )
        status: Literal["completed", "partial", "failed"]
        if successful == len(providers):
            status = "completed"
        elif deduplicated:
            status = "partial"
        else:
            status = "failed"
        return ExternalRetrievalResult(
            query=query,
            normalized_query=normalized,
            source_scopes=scopes,
            items=_select_diverse(deduplicated, limit),
            status=status,
            warnings=warnings,
            provider_status=provider_status,
            retrieval_trace_id=retrieval_trace_id,
        )

    async def search_many(
        self,
        query: str,
        *,
        query_variants: Sequence[str],
        limit: int = 8,
        retrieval_trace_id: str = "",
        provider_names: Sequence[str] | None = None,
        source_scopes: Sequence[ExternalSourceScope] | None = None,
        freshness_days: int | None = None,
        prefer_high_citation: bool = False,
    ) -> ExternalRetrievalResult:
        """Search several model-generated variants and merge them once.

        Each variant still uses the normal provider fan-out. The merge happens
        here so deduplication, freshness policy, and source diversity remain
        identical for one-query and planned-query searches.
        """

        variants = list(
            dict.fromkeys(
                value.strip() for value in query_variants if value.strip()
            )
        )[:4]
        if not variants:
            variants = [query.strip()]
        per_query_limit = min(50, max(limit * 2, limit))
        # Keep variants sequential so a provider sees one request at a time.
        # Provider fan-out remains parallel inside ``search``; this avoids
        # turning one user request into a burst that reliably triggers 429s.
        responses: list[ExternalRetrievalResult | Exception] = []
        for variant in variants:
            try:
                responses.append(
                    await self.search(
                        query,
                        normalized_query=variant,
                        limit=per_query_limit,
                        retrieval_trace_id=retrieval_trace_id,
                        provider_names=provider_names,
                        source_scopes=source_scopes,
                        freshness_days=freshness_days,
                        prefer_high_citation=prefer_high_citation,
                    )
                )
            except Exception as exc:
                responses.append(exc)
        items: list[ExternalEvidenceItem] = []
        warnings: list[str] = []
        provider_status: dict[str, str] = {}
        scopes: list[ExternalSourceScope] = []
        successful_queries = 0
        successful_responses: list[ExternalRetrievalResult] = []
        for variant, response in zip(variants, responses, strict=True):
            if isinstance(response, Exception):
                warnings.append(
                    f"query variant failed: {variant[:120]} ({type(response).__name__})"
                )
                continue
            successful_queries += 1
            successful_responses.append(response)
            items.extend(response.items)
            warnings.extend(response.warnings)
            for provider, provider_state in response.provider_status.items():
                previous = provider_status.get(provider)
                provider_status[provider] = (
                    "completed"
                    if previous == "completed" and provider_state == "completed"
                    else provider_state
                    if previous is None
                    else "partial"
                )
            for scope in response.source_scopes:
                if scope not in scopes:
                    scopes.append(scope)

        deduplicated = _deduplicate(items)
        deduplicated.sort(
            key=lambda item: (
                item.updated_at
                or item.published_at
                or datetime.min.replace(tzinfo=UTC),
                item.relevance_score,
            ),
            reverse=True,
        )
        status: Literal["completed", "partial", "failed"]
        if successful_queries == len(variants):
            status = "completed"
        elif deduplicated:
            status = "partial"
        else:
            status = "failed"
        return ExternalRetrievalResult(
            query=query,
            normalized_query=" | ".join(variants),
            source_scopes=scopes,
            # Keep a larger, query-covered candidate pool for model review.
            # The caller applies the user-facing result limit after review.
            items=_select_query_coverage(
                successful_responses,
                min(16, max(limit * 2, limit)),
            ),
            status=status,
            warnings=list(dict.fromkeys(warnings))[:20],
            provider_status=provider_status,
            retrieval_trace_id=retrieval_trace_id,
            search_queries=variants,
        )

    async def close(self) -> None:
        for provider in self.providers:
            closer = getattr(provider, "close", None)
            if closer is not None:
                await closer()


def merge_academic_results(
    results: Sequence[ExternalRetrievalResult],
    *,
    query: str,
    limit: int,
    prefer_high_citation: bool = False,
    search_round: int = 1,
) -> ExternalRetrievalResult:
    """Merge approved results from multiple retrieval rounds."""

    if not results:
        return ExternalRetrievalResult(
            query=query,
            normalized_query=query,
            status="failed",
            search_round=search_round,
        )
    items = _deduplicate(
        [item for result in results for item in result.items]
    )
    items.sort(
        key=lambda item: (
            (item.citation_count is not None)
            if prefer_high_citation
            else False,
            (item.citation_count or -1) if prefer_high_citation else 0,
            item.updated_at
            or item.published_at
            or datetime.min.replace(tzinfo=UTC),
            item.relevance_score,
        ),
        reverse=True,
    )
    scopes: list[ExternalSourceScope] = []
    provider_status: dict[str, str] = {}
    warnings: list[str] = []
    queries: list[str] = []
    for result in results:
        for scope in result.source_scopes:
            if scope not in scopes:
                scopes.append(scope)
        for provider, status in result.provider_status.items():
            previous = provider_status.get(provider)
            provider_status[provider] = (
                status if previous is None or previous == status else "partial"
            )
        warnings.extend(result.warnings)
        for search_query in result.search_queries:
            if search_query not in queries:
                queries.append(search_query)
    selected = _select_diverse(items, limit)
    return ExternalRetrievalResult(
        query=query,
        normalized_query=" | ".join(queries) or query,
        source_scopes=scopes,
        items=selected,
        status="completed" if selected else "failed",
        warnings=list(dict.fromkeys(warnings))[:20],
        provider_status=provider_status,
        reviewed_count=sum(result.reviewed_count for result in results),
        approved_count=len(selected),
        review_status="approved" if selected else "rejected",
        search_queries=queries[:6],
        search_round=search_round,
    )


def _text(element: ElementTree.Element, name: str) -> str:
    child = element.find(f"{{{ATOM_NAMESPACE}}}{name}")
    return child.text or "" if child is not None else ""


def _http_url(value: str) -> AnyHttpUrl:
    return _HTTP_URL_ADAPTER.validate_python(value)


def _normalize_arxiv_url(value: str) -> str:
    """Expose a stable HTTPS link even when arXiv returns an HTTP entry id."""

    if value.startswith("http://arxiv.org/"):
        return f"https://arxiv.org/{value.split('http://arxiv.org/', 1)[1]}"
    if value.startswith("http://export.arxiv.org/"):
        return f"https://arxiv.org/{value.split('http://export.arxiv.org/', 1)[1]}"
    return value


def _clean_text(value: str) -> str:
    return WHITESPACE.sub(" ", html.unescape(HTML_TAG.sub(" ", value))).strip()


def _parse_datetime(value: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_date(value: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        return datetime.fromisoformat(f"{value.strip()}T00:00:00+00:00")
    except ValueError:
        return None


def _crossref_date(value: object) -> datetime | None:
    if not isinstance(value, dict):
        return None
    parts = value.get("date-parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
        return None
    values = parts[0]
    if not values or not isinstance(values[0], int):
        return None
    year = values[0]
    month = values[1] if len(values) > 1 and isinstance(values[1], int) else 1
    day = values[2] if len(values) > 2 and isinstance(values[2], int) else 1
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None


def _first_string(value: object) -> str:
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    return str(value or "").strip()


def _citation_count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count is not None and count >= 0 else None


def _looks_fresh_query(query: str) -> bool:
    normalized = query.casefold()
    return any(
        token in normalized
        for token in ("最新", "近期", "最近", "今年", "latest", "recent", "newest")
    )


def _authors(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for author in value:
        if not isinstance(author, dict):
            continue
        name = " ".join(
            part.strip()
            for part in (str(author.get("given", "")), str(author.get("family", "")))
            if part.strip()
        )
        if name:
            result.append(name)
    return result


def _record_authors(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    if all(isinstance(author, str) for author in value):
        return [author.strip() for author in value if author.strip()]
    return _openalex_authors(value)


def _openalex_authors(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for authorship in value:
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author") or {}
        name = str(author.get("display_name", "")).strip()
        if name:
            result.append(name)
    # OpenAlex can return very large collaboration author lists. Keep the
    # evidence contract bounded without discarding the paper itself.
    return list(dict.fromkeys(result))[:64]


def _openalex_abstract(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    words: list[tuple[int, str]] = []
    for word, positions in value.items():
        if not isinstance(word, str) or not isinstance(positions, list):
            continue
        words.extend(
            (position, word)
            for position in positions
            if isinstance(position, int)
        )
    return " ".join(word for _, word in sorted(words))


def _stable_id(value: str) -> str:
    return hashlib.sha256(value.casefold().encode("utf-8")).hexdigest()[:20]


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")[:96]


def _deduplicate(items: Sequence[ExternalEvidenceItem]) -> list[ExternalEvidenceItem]:
    seen: set[str] = set()
    result: list[ExternalEvidenceItem] = []
    for item in sorted(items, key=lambda value: value.relevance_score, reverse=True):
        key = _deduplication_key(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _select_query_coverage(
    responses: Sequence[ExternalRetrievalResult], limit: int
) -> list[ExternalEvidenceItem]:
    """Round-robin query variants before applying the display limit."""

    selected: list[ExternalEvidenceItem] = []
    seen: set[str] = set()
    max_items = max((len(response.items) for response in responses), default=0)
    for offset in range(max_items):
        for response in responses:
            if offset >= len(response.items):
                continue
            item = response.items[offset]
            key = _deduplication_key(item)
            if key in seen:
                continue
            seen.add(key)
            selected.append(item)
            if len(selected) >= limit:
                return selected
    return selected


def _deduplication_key(item: ExternalEvidenceItem) -> str:
    keys = [
        item.doi.casefold(),
        item.arxiv_id.casefold(),
        str(item.canonical_url).casefold().rstrip("/"),
        " ".join(item.title.casefold().split()),
    ]
    return next((value for value in keys if value), item.evidence_id)


def _select_diverse(
    items: Sequence[ExternalEvidenceItem], limit: int
) -> list[ExternalEvidenceItem]:
    """Prefer one recent result per provider before filling remaining slots."""

    selected: list[ExternalEvidenceItem] = []
    selected_ids: set[str] = set()
    providers: set[str] = set()
    for item in items:
        if item.provider in providers:
            continue
        selected.append(item)
        selected_ids.add(item.evidence_id)
        providers.add(item.provider)
        if len(selected) >= limit:
            return selected
    for item in items:
        if item.evidence_id in selected_ids:
            continue
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected
