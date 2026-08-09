from __future__ import annotations

import asyncio
import hashlib
import html
import inspect
import re
import xml.etree.ElementTree as ElementTree
from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any, Literal, Protocol, cast

import httpx
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from app.contracts import (
    ExternalEvidenceItem,
    ExternalRetrievalResult,
    ExternalSourceScope,
    ExternalSourceType,
)
from app.providers.retrieval.adapters import (
    ArxivQueryAdapter,
    CrossrefQueryAdapter,
    OpenAlexQueryAdapter,
    ProviderSearchContext,
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

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: float | None = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.retryable = retryable


class HttpAcademicProvider(ABC):
    provider_name: str
    source_scope = ExternalSourceScope.ACADEMIC

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15,
        min_delay_seconds: float = 0.0,
        trust_env: bool = True,
        max_concurrency: int = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            trust_env=trust_env,
        )
        self._owns_client = client is None
        self.min_delay_seconds = max(0.0, min_delay_seconds)
        self.max_concurrency = max(1, max_concurrency)
        self._rate_lock = asyncio.Lock()
        self._request_semaphore = asyncio.Semaphore(self.max_concurrency)
        self._next_request_at = 0.0
        self._requests_started = 0
        self._requests_completed = 0
        self._requests_failed = 0
        self._active_requests = 0
        self._peak_active_requests = 0

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str, *, params: dict[str, Any]) -> httpx.Response:
        try:
            response = await self._throttled_get(
                path,
                params=params,
                headers=None,
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise AcademicProviderError(f"{self.provider_name}: timeout") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise AcademicProviderError(
                    f"{self.provider_name}: rate_limited",
                    retry_after_seconds=_retry_after_seconds(exc.response),
                ) from exc
            raise AcademicProviderError(
                f"{self.provider_name}: http_{exc.response.status_code}",
                retryable=exc.response.status_code >= 500,
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
            response = await self._throttled_get(
                path,
                params=params,
                headers=request_headers,
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise AcademicProviderError(f"{self.provider_name}: timeout") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise AcademicProviderError(
                    f"{self.provider_name}: rate_limited",
                    retry_after_seconds=_retry_after_seconds(exc.response),
                ) from exc
            raise AcademicProviderError(
                f"{self.provider_name}: http_{exc.response.status_code}",
                retryable=exc.response.status_code >= 500,
            ) from exc
        except httpx.RequestError as exc:
            raise AcademicProviderError(
                f"{self.provider_name}: request_failed"
            ) from exc

    async def _post_json_with_headers(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            request_headers = {
                "User-Agent": "xinzhi-daoxue/1.0 (academic retrieval)",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            if headers:
                request_headers.update(headers)
            response = await self._throttled_post_json(
                path,
                payload=payload,
                headers=request_headers,
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise AcademicProviderError(f"{self.provider_name}: timeout") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise AcademicProviderError(
                    f"{self.provider_name}: rate_limited",
                    retry_after_seconds=_retry_after_seconds(exc.response),
                ) from exc
            raise AcademicProviderError(
                f"{self.provider_name}: http_{exc.response.status_code}",
                retryable=exc.response.status_code >= 500,
            ) from exc
        except httpx.RequestError as exc:
            raise AcademicProviderError(
                f"{self.provider_name}: request_failed"
            ) from exc

    async def _throttled_get(
        self,
        path: str,
        *,
        params: dict[str, Any],
        headers: dict[str, str] | None,
    ) -> httpx.Response:
        request_headers = {
            "User-Agent": "xinzhi-daoxue/1.0 (academic retrieval)"
        }
        if headers:
            request_headers.update(headers)
        async with self._request_semaphore:
            async with self._rate_lock:
                wait_seconds = self._next_request_at - monotonic()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                self._next_request_at = monotonic() + self.min_delay_seconds
                request_url = (
                    self.base_url
                    if not path
                    else f"{self.base_url}/{path.lstrip('/')}"
                )
            return await self._request(
                self._client.get(
                    request_url,
                    params=params,
                    headers=request_headers,
                )
            )

    async def _throttled_post_json(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        async with self._request_semaphore:
            async with self._rate_lock:
                wait_seconds = self._next_request_at - monotonic()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                self._next_request_at = monotonic() + self.min_delay_seconds
                request_url = (
                    self.base_url
                    if not path
                    else f"{self.base_url}/{path.lstrip('/')}"
                )
            return await self._request(
                self._client.post(
                    request_url,
                    json=payload,
                    headers=headers,
                )
            )

    async def _request(self, request: Any) -> httpx.Response:
        self._requests_started += 1
        self._active_requests += 1
        self._peak_active_requests = max(
            self._peak_active_requests, self._active_requests
        )
        try:
            response = await request
        except BaseException:
            self._requests_failed += 1
            raise
        else:
            self._requests_completed += 1
            return response
        finally:
            self._active_requests -= 1

    def runtime_stats(self) -> dict[str, object]:
        """Expose bounded runtime counters without including request data."""

        return {
            "min_delay_seconds": self.min_delay_seconds,
            "max_concurrency": self.max_concurrency,
            "active_requests": self._active_requests,
            "peak_active_requests": self._peak_active_requests,
            "requests_started": self._requests_started,
            "requests_completed": self._requests_completed,
            "requests_failed": self._requests_failed,
        }

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int,
        prefer_high_citation: bool = False,
    ) -> list[ExternalEvidenceItem]: ...


class ArxivAcademicProvider(HttpAcademicProvider):
    provider_name = "arxiv"

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30,
        min_delay_seconds: float = 3.0,
        max_concurrency: int = 1,
    ) -> None:
        super().__init__(
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
            min_delay_seconds=min_delay_seconds,
            max_concurrency=max_concurrency,
        )
        self.query_adapter = ArxivQueryAdapter()

    async def search(
        self, query: str, *, limit: int, prefer_high_citation: bool = False
    ) -> list[ExternalEvidenceItem]:
        return await self.search_with_context(
            ProviderSearchContext(
                query=query,
                normalized_query=query,
                limit=limit,
                prefer_high_citation=prefer_high_citation,
            )
        )

    async def search_with_context(
        self, context: ProviderSearchContext
    ) -> list[ExternalEvidenceItem]:
        provider_query = self.query_adapter.build_query(context)
        candidate_limit = min(50, max(context.limit * 2, context.limit))
        response = await self._get(
            "query",
            params={
                "search_query": provider_query.text,
                "start": 0,
                "max_results": candidate_limit,
                "sortBy": (
                    "submittedDate"
                    if context.freshness_days is not None
                    else "relevance"
                ),
                "sortOrder": "descending",
            },
        )
        try:
            root = ElementTree.fromstring(response.text)
        except ElementTree.ParseError as exc:
            raise AcademicProviderError("arxiv: invalid_xml") from exc

        now = datetime.now(UTC)
        items: list[ExternalEvidenceItem] = []
        for rank, entry in enumerate(
            root.findall(f"{{{ATOM_NAMESPACE}}}entry")[:candidate_limit]
        ):
            abstract_url = _normalize_arxiv_url(_text(entry, "id"))
            title = _clean_text(_text(entry, "title"))
            if not abstract_url or not title:
                continue
            paper_id = abstract_url.rstrip("/").split("/abs/")[-1]
            authors = [
                _clean_text(_text(author, "name"))
                for author in entry.findall(f"{{{ATOM_NAMESPACE}}}author")
            ]
            try:
                item = ExternalEvidenceItem(
                    evidence_id=f"arxiv-{paper_id.replace('/', '-')}",
                    source_type=ExternalSourceType.ACADEMIC_PAPER,
                    provider=self.provider_name,
                    source_ref=f"external://arxiv/{paper_id}",
                    title=title,
                    canonical_url=validate_http_url(abstract_url),
                    content_excerpt=_clean_text(_text(entry, "summary")),
                    authors=authors,
                    published_at=_parse_datetime(_text(entry, "published")),
                    updated_at=_parse_datetime(_text(entry, "updated")),
                    retrieved_at=now,
                    arxiv_id=paper_id,
                    relevance_score=0,
                    trust_level="medium",
                )
            except ValidationError:
                continue
            items.append(
                item.model_copy(
                    update={
                        "relevance_score": self.query_adapter.score(
                            item,
                            provider_query,
                            rank=rank,
                            prefer_high_citation=context.prefer_high_citation,
                        )
                    }
                )
            )
        items.sort(key=lambda item: item.relevance_score, reverse=True)
        return items[: context.limit]


class CrossrefAcademicProvider(HttpAcademicProvider):
    provider_name = "crossref"

    def __init__(
        self,
        *,
        base_url: str,
        mailto: str = "",
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30,
        min_delay_seconds: float = 0.5,
        max_concurrency: int = 1,
    ) -> None:
        super().__init__(
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
            min_delay_seconds=min_delay_seconds,
            max_concurrency=max_concurrency,
        )
        self.mailto = mailto.strip()
        self.query_adapter = CrossrefQueryAdapter()

    async def search(
        self, query: str, *, limit: int, prefer_high_citation: bool = False
    ) -> list[ExternalEvidenceItem]:
        return await self.search_with_context(
            ProviderSearchContext(
                query=query,
                normalized_query=query,
                limit=limit,
                prefer_high_citation=prefer_high_citation,
            )
        )

    async def search_with_context(
        self, context: ProviderSearchContext
    ) -> list[ExternalEvidenceItem]:
        provider_query = self.query_adapter.build_query(context)
        today = datetime.now(UTC).date().isoformat()
        filters = [f"until-pub-date:{today}"]
        if context.freshness_days is not None:
            from_date = (
                datetime.now(UTC).date() - timedelta(days=context.freshness_days)
            ).isoformat()
            filters.insert(0, f"from-pub-date:{from_date}")
        params: dict[str, Any] = {
            "query.bibliographic": provider_query.text,
            "rows": min(50, max(context.limit * 2, context.limit)),
            "filter": ",".join(filters),
            "select": (
                "DOI,title,author,container-title,abstract,URL,published,"
                "created,type,is-referenced-by-count"
            ),
            "sort": (
                "is-referenced-by-count"
                if context.prefer_high_citation
                else "published"
            ),
            "order": "desc",
        }
        if self.mailto:
            params["mailto"] = self.mailto
        response = await self._get("works", params=params)
        try:
            payload = response.json()
            records = payload["message"]["items"]
        except (TypeError, KeyError, ValueError) as exc:
            raise AcademicProviderError("crossref: invalid_json") from exc

        now = datetime.now(UTC)
        items: list[ExternalEvidenceItem] = []
        for rank, record in enumerate(records[: min(50, context.limit * 2)]):
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
                    canonical_url=validate_http_url(url),
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
                    relevance_score=0,
                    trust_level="high",
                    metadata={
                        "type": str(record.get("type", "")),
                        "query_adapter": "crossref_v1",
                        "provider_query": provider_query.text,
                    },
                )
            except ValidationError:
                continue
            items.append(
                item.model_copy(
                    update={
                        "relevance_score": self.query_adapter.score(
                            item,
                            provider_query,
                            rank=rank,
                            prefer_high_citation=context.prefer_high_citation,
                        )
                    }
                )
            )
        items.sort(key=lambda item: item.relevance_score, reverse=True)
        return items[: context.limit]


class SemanticScholarAcademicProvider(HttpAcademicProvider):
    provider_name = "semantic_scholar"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15,
        min_delay_seconds: float = 1.0,
        max_concurrency: int = 1,
    ) -> None:
        super().__init__(
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
            min_delay_seconds=min_delay_seconds,
            max_concurrency=max_concurrency,
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
                    canonical_url=validate_http_url(url),
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
        min_delay_seconds: float = 0.2,
        max_concurrency: int = 1,
    ) -> None:
        super().__init__(
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
            min_delay_seconds=min_delay_seconds,
            max_concurrency=max_concurrency,
        )
        self.api_key = api_key.strip()
        self.mailto = mailto.strip()
        self.query_adapter = OpenAlexQueryAdapter()

    async def search(
        self, query: str, *, limit: int, prefer_high_citation: bool = False
    ) -> list[ExternalEvidenceItem]:
        return await self.search_with_context(
            ProviderSearchContext(
                query=query,
                normalized_query=query,
                limit=limit,
                prefer_high_citation=prefer_high_citation,
            )
        )

    async def search_with_context(
        self, context: ProviderSearchContext
    ) -> list[ExternalEvidenceItem]:
        provider_query = self.query_adapter.build_query(context)
        today = datetime.now(UTC).date().isoformat()
        date_filter = f"to_publication_date:{today}"
        if context.freshness_days is not None:
            from_date = (
                datetime.now(UTC).date() - timedelta(days=context.freshness_days)
            ).isoformat()
            date_filter = (
                f"from_publication_date:{from_date},{date_filter}"
            )
        params: dict[str, Any] = {
            "search": provider_query.text,
            "per-page": min(50, max(context.limit * 2, context.limit)),
            "filter": f"has_abstract:true,{date_filter}",
            "sort": (
                "cited_by_count:desc"
                if context.prefer_high_citation
                else "publication_date:desc"
            ),
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.mailto:
            params["mailto"] = self.mailto
        response = await self._get_openalex("works", params=params)
        try:
            records = response.json()["results"]
        except (TypeError, KeyError, ValueError) as exc:
            raise AcademicProviderError("openalex: invalid_json") from exc
        if not isinstance(records, list):
            raise AcademicProviderError("openalex: invalid_results")

        now = datetime.now(UTC)
        candidates: list[ExternalEvidenceItem] = []
        for rank, record in enumerate(records[: min(50, context.limit * 4)]):
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
            item = ExternalEvidenceItem(
                evidence_id=f"openalex-{_safe_id(work_id.rsplit('/', 1)[-1])}",
                source_type=ExternalSourceType.ACADEMIC_PAPER,
                provider=self.provider_name,
                source_ref=f"external://openalex/{work_id.rsplit('/', 1)[-1]}",
                title=title,
                canonical_url=validate_http_url(canonical_url),
                content_excerpt=_openalex_abstract(
                    record.get("abstract_inverted_index")
                ),
                authors=_openalex_authors(record.get("authorships")),
                venue=str(source.get("display_name", "") or "").strip(),
                published_at=_parse_date(str(record.get("publication_date", ""))),
                retrieved_at=now,
                doi=doi.removeprefix("https://doi.org/"),
                citation_count=_citation_count(record.get("cited_by_count")),
                relevance_score=0,
                trust_level="high",
                metadata={
                    "openalex_id": work_id,
                    "query_adapter": "openalex_v1",
                    "provider_query": provider_query.text,
                },
            )
            candidates.append(
                item.model_copy(
                    update={
                        "relevance_score": self.query_adapter.score(
                            item,
                            provider_query,
                            rank=rank,
                            prefer_high_citation=context.prefer_high_citation,
                        )
                    }
                )
            )
        candidates.sort(
            key=lambda item: (
                item.relevance_score,
                item.citation_count or 0,
                item.published_at or datetime.min.replace(tzinfo=UTC),
            ),
            reverse=True,
        )
        return candidates[: context.limit]

    async def _get_openalex(
        self, path: str, *, params: dict[str, Any]
    ) -> httpx.Response:
        return await self._get(path, params=params)


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
                    canonical_url=validate_http_url(url),
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

    def __init__(
        self,
        providers: Sequence[AcademicSearchProvider],
        *,
        cache_size: int = 128,
        cache_ttl_seconds: float = 120,
        max_retries: int = 1,
        rate_limit_cooldown_seconds: float = 60.0,
        max_provider_concurrency: int = 4,
        max_query_variants: int = 2,
        provider_tiers: Sequence[Sequence[str]] | None = None,
    ) -> None:
        self.providers = tuple(providers)
        self.cache_size = max(0, cache_size)
        self.cache_ttl_seconds = max(0.0, cache_ttl_seconds)
        self.max_retries = max(0, max_retries)
        self.rate_limit_cooldown_seconds = max(0.0, rate_limit_cooldown_seconds)
        self.max_provider_concurrency = max(1, max_provider_concurrency)
        self.max_query_variants = max(1, max_query_variants)
        self._provider_semaphore = asyncio.Semaphore(
            self.max_provider_concurrency
        )
        self.provider_tiers = tuple(
            tuple(name.casefold() for name in tier if name.strip())
            for tier in (provider_tiers or ())
            if tier
        )
        self._cache: OrderedDict[
            tuple[object, ...], tuple[float, ExternalRetrievalResult]
        ] = OrderedDict()
        self._last_provider_status: dict[str, str] = {}
        self._provider_cooldown_until: dict[str, float] = {}
        self._search_calls = 0
        self._cache_hits = 0
        self._provider_attempts: dict[str, int] = {}

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
        self._search_calls += 1
        normalized = " ".join((normalized_query or query).split())
        cache_key = self._cache_key(
            normalized,
            limit=limit,
            provider_names=provider_names,
            source_scopes=source_scopes,
            freshness_days=freshness_days,
            prefer_high_citation=prefer_high_citation,
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            self._cache_hits += 1
            return cached.model_copy(
                update={
                    "query": query,
                    "retrieval_trace_id": retrieval_trace_id,
                    "cache_hit": True,
                }
            )
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
            result = ExternalRetrievalResult(
                query=query,
                normalized_query=normalized,
                source_scopes=[],
                status="disabled",
                retrieval_trace_id=retrieval_trace_id,
            )
            self._cache_put(cache_key, result)
            return result

        async def _run_provider_unbounded(
            provider: AcademicSearchProvider,
        ) -> list[ExternalEvidenceItem]:
            cooldown_remaining = self._cooldown_remaining(provider.provider_name)
            if cooldown_remaining > 0:
                raise AcademicProviderError(
                    f"{provider.provider_name}: rate_limited "
                    f"(cooldown {cooldown_remaining:.0f}s)"
                )
            kwargs: dict[str, Any] = {
                "limit": min(50, max(limit, limit * 2 if freshness_days else limit))
            }
            if prefer_high_citation and "prefer_high_citation" in inspect.signature(
                provider.search
            ).parameters:
                kwargs["prefer_high_citation"] = True
            last_error: AcademicProviderError | None = None
            for attempt in range(self.max_retries + 1):
                self._provider_attempts[provider.provider_name] = (
                    self._provider_attempts.get(provider.provider_name, 0) + 1
                )
                try:
                    context = ProviderSearchContext(
                        query=query,
                        normalized_query=normalized,
                        limit=kwargs["limit"],
                        freshness_days=freshness_days,
                        prefer_high_citation=prefer_high_citation,
                    )
                    search_with_context = getattr(provider, "search_with_context", None)
                    if callable(search_with_context):
                        return cast(
                            list[ExternalEvidenceItem],
                            await search_with_context(context),
                        )
                    return await provider.search(normalized, **kwargs)
                except AcademicProviderError as exc:
                    last_error = exc
                    if "rate_limited" in str(exc):
                        self._set_provider_cooldown(
                            provider.provider_name,
                            exc.retry_after_seconds,
                        )
                    if attempt >= self.max_retries or not exc.retryable:
                        raise
                    retry_after = exc.retry_after_seconds
                    delay = (
                        min(max(retry_after, 0.0), 30.0)
                        if retry_after is not None
                        else 0.25 * (2**attempt)
                    )
                    await asyncio.sleep(delay)
            assert last_error is not None
            raise last_error

        async def run_provider(
            provider: AcademicSearchProvider,
        ) -> list[ExternalEvidenceItem]:
            async with self._provider_semaphore:
                return await _run_provider_unbounded(provider)

        provider_groups = self._provider_groups(providers)
        called_providers: list[AcademicSearchProvider] = []
        responses: list[list[ExternalEvidenceItem] | BaseException] = []
        collected_count = 0
        for group in provider_groups:
            group_responses = await asyncio.gather(
                *(run_provider(provider) for provider in group),
                return_exceptions=True,
            )
            called_providers.extend(group)
            responses.extend(group_responses)
            collected_count += sum(
                len(response)
                for response in group_responses
                if isinstance(response, list)
            )
            if collected_count >= limit:
                break
        items: list[ExternalEvidenceItem] = []
        provider_status: dict[str, str] = {}
        warnings: list[str] = []
        successful = 0
        scopes: list[ExternalSourceScope] = []
        for provider, response in zip(called_providers, responses, strict=True):
            if isinstance(response, BaseException):
                provider_status[provider.provider_name] = (
                    "rate_limited"
                    if isinstance(response, AcademicProviderError)
                    and "rate_limited" in str(response)
                    else "failed"
                )
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
                item.relevance_score,
                item.updated_at
                or item.published_at
                or datetime.min.replace(tzinfo=UTC),
            ),
            reverse=True,
        )
        status: Literal["completed", "partial", "failed"]
        if successful == len(called_providers):
            status = "completed"
        elif deduplicated:
            status = "partial"
        else:
            status = "failed"
        result = ExternalRetrievalResult(
            query=query,
            normalized_query=normalized,
            source_scopes=scopes,
            items=_select_diverse(deduplicated, limit),
            status=status,
            warnings=warnings,
            provider_status=provider_status,
            retrieval_trace_id=retrieval_trace_id,
        )
        self._last_provider_status = dict(provider_status)
        self._cache_put(cache_key, result)
        return result

    def health(self) -> dict[str, object]:
        """Return configuration-only provider health without network calls."""

        provider_runtime: dict[str, object] = {}
        for provider in self.providers:
            runtime_stats = getattr(provider, "runtime_stats", None)
            if callable(runtime_stats):
                provider_runtime[provider.provider_name] = cast(Any, runtime_stats)()
        return {
            "configured": bool(self.providers),
            "providers": [
                {
                    "name": provider.provider_name,
                    "scope": getattr(
                        provider, "source_scope", ExternalSourceScope.ACADEMIC
                    ).value,
                    "last_status": self._last_provider_status.get(
                        provider.provider_name, "not_checked"
                    ),
                }
                for provider in self.providers
            ],
            "cache": {
                "enabled": self.cache_size > 0 and self.cache_ttl_seconds > 0,
                "entries": len(self._cache),
                "max_entries": self.cache_size,
                "ttl_seconds": self.cache_ttl_seconds,
            },
            "max_retries": self.max_retries,
            "max_provider_concurrency": self.max_provider_concurrency,
            "max_query_variants": self.max_query_variants,
            "provider_tiers": [list(tier) for tier in self.provider_tiers],
            "search_calls": self._search_calls,
            "cache_hits": self._cache_hits,
            "provider_attempts": dict(self._provider_attempts),
            "provider_runtime": provider_runtime,
            "rate_limit_cooldowns": {
                name: round(remaining, 1)
                for name in self._provider_cooldown_names()
                if (remaining := self._cooldown_remaining(name)) > 0
            },
        }

    def _provider_groups(
        self, providers: Sequence[AcademicSearchProvider]
    ) -> list[tuple[AcademicSearchProvider, ...]]:
        by_name = {
            provider.provider_name.casefold(): provider for provider in providers
        }
        if not self.provider_tiers:
            return [tuple(providers)]
        groups: list[tuple[AcademicSearchProvider, ...]] = []
        assigned: set[str] = set()
        for tier in self.provider_tiers:
            group = tuple(
                by_name[name]
                for name in tier
                if name in by_name and name not in assigned
            )
            if group:
                groups.append(group)
                assigned.update(
                    provider.provider_name.casefold() for provider in group
                )
        remaining = tuple(
            provider
            for provider in providers
            if provider.provider_name.casefold() not in assigned
        )
        if remaining:
            groups.append(remaining)
        return groups or [tuple(providers)]

    def _provider_cooldown_names(self) -> set[str]:
        return set(self._provider_cooldown_until)

    def _cooldown_remaining(self, provider_name: str) -> float:
        until = self._provider_cooldown_until.get(provider_name, 0.0)
        remaining = until - monotonic()
        if remaining <= 0:
            self._provider_cooldown_until.pop(provider_name, None)
            return 0.0
        return remaining

    def _set_provider_cooldown(
        self, provider_name: str, retry_after_seconds: float | None
    ) -> None:
        if self.rate_limit_cooldown_seconds <= 0:
            return
        delay = (
            retry_after_seconds
            if retry_after_seconds is not None
            else self.rate_limit_cooldown_seconds
        )
        self._provider_cooldown_until[provider_name] = monotonic() + max(0.0, delay)

    @staticmethod
    def _cache_key(
        normalized: str,
        *,
        limit: int,
        provider_names: Sequence[str] | None,
        source_scopes: Sequence[ExternalSourceScope] | None,
        freshness_days: int | None,
        prefer_high_citation: bool,
    ) -> tuple[object, ...]:
        return (
            normalized,
            limit,
            tuple(sorted(name.casefold() for name in provider_names or ())),
            tuple(sorted(scope.value for scope in source_scopes or ())),
            freshness_days,
            prefer_high_citation,
        )

    def _cache_get(
        self, key: tuple[object, ...]
    ) -> ExternalRetrievalResult | None:
        if self.cache_size <= 0 or self.cache_ttl_seconds <= 0:
            return None
        cached = self._cache.get(key)
        if cached is None:
            return None
        created, result = cached
        if monotonic() - created > self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return result.model_copy(deep=True)

    def _cache_put(
        self, key: tuple[object, ...], result: ExternalRetrievalResult
    ) -> None:
        if (
            self.cache_size <= 0
            or self.cache_ttl_seconds <= 0
            or result.status not in {"completed", "partial"}
            or not result.items
        ):
            return
        self._cache[key] = (monotonic(), result.model_copy(deep=True))
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

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
        )[: self.max_query_variants]
        if not variants:
            variants = [query.strip()]
        per_query_limit = min(50, max(limit * 2, limit))
        # Keep variants sequential so a provider sees one request at a time.
        # Provider fan-out remains parallel inside ``search``; this avoids
        # turning one user request into a burst that reliably triggers 429s.
        responses: list[ExternalRetrievalResult | Exception] = []
        searched_variants: list[str] = []
        for variant in variants:
            searched_variants.append(variant)
            try:
                variant_result = await self.search(
                    query,
                    normalized_query=variant,
                    limit=per_query_limit,
                    retrieval_trace_id=retrieval_trace_id,
                    provider_names=provider_names,
                    source_scopes=source_scopes,
                    freshness_days=freshness_days,
                    prefer_high_citation=prefer_high_citation,
                )
                responses.append(variant_result)
            except Exception as exc:
                responses.append(exc)
        items: list[ExternalEvidenceItem] = []
        warnings: list[str] = []
        provider_status: dict[str, str] = {}
        scopes: list[ExternalSourceScope] = []
        successful_queries = 0
        successful_responses: list[ExternalRetrievalResult] = []
        for variant, response in zip(searched_variants, responses, strict=True):
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
                item.relevance_score,
                item.updated_at
                or item.published_at
                or datetime.min.replace(tzinfo=UTC),
            ),
            reverse=True,
        )
        status: Literal["completed", "partial", "failed"]
        if successful_queries == len(searched_variants):
            status = "completed"
        elif deduplicated:
            status = "partial"
        else:
            status = "failed"
        return ExternalRetrievalResult(
            query=query,
            normalized_query=" | ".join(searched_variants),
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
            search_queries=searched_variants,
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
    retrieval_trace_id: str = "",
) -> ExternalRetrievalResult:
    """Merge approved results from multiple retrieval rounds."""

    if not results:
        return ExternalRetrievalResult(
            query=query,
            normalized_query=query,
            status="failed",
            search_round=search_round,
            retrieval_trace_id=retrieval_trace_id,
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
            item.relevance_score,
            item.updated_at
            or item.published_at
            or datetime.min.replace(tzinfo=UTC),
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
        retrieval_trace_id=(
            retrieval_trace_id
            or next(
                (
                    result.retrieval_trace_id
                    for result in results
                    if result.retrieval_trace_id
                ),
                "",
            )
        ),
        search_queries=queries[:6],
        search_round=search_round,
    )


def _text(element: ElementTree.Element, name: str) -> str:
    child = element.find(f"{{{ATOM_NAMESPACE}}}{name}")
    return child.text or "" if child is not None else ""


def validate_http_url(value: str) -> AnyHttpUrl:
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


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after", "").strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


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
