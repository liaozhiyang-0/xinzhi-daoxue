from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from pydantic import ValidationError

from app.contracts import ExternalEvidenceItem, ExternalSourceScope, ExternalSourceType
from app.providers.retrieval.academic import (
    AcademicProviderError,
    HttpAcademicProvider,
    validate_http_url,
)


class JsonWebSearchProvider(HttpAcademicProvider):
    """Adapter for a configured JSON search gateway.

    The gateway contract is deliberately small: ``results`` must be a list
    containing ``title`` and ``url``; ``content``/``snippet``, ``score`` and
    ``published_date`` are optional. This keeps provider credentials and
    vendor-specific SDKs outside the agent runtime.
    """

    provider_name = "web_json"
    source_scope = ExternalSourceScope.WEB

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        auth_header: str = "x-api-key",
        client: Any = None,
        timeout_seconds: float = 15,
        min_delay_seconds: float = 1,
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
        self.auth_header = auth_header.strip() or "x-api-key"

    async def search(
        self,
        query: str,
        *,
        limit: int,
        prefer_high_citation: bool = False,
    ) -> list[ExternalEvidenceItem]:
        del prefer_high_citation
        headers = {self.auth_header: self.api_key} if self.api_key else None
        response = await self._get_with_headers(
            "",
            params={"query": query, "limit": limit},
            headers=headers,
        )
        try:
            records = response.json()["results"]
        except (TypeError, KeyError, ValueError) as exc:
            raise AcademicProviderError("web_json: invalid_json") from exc
        if not isinstance(records, list):
            raise AcademicProviderError("web_json: invalid_results")

        now = datetime.now(UTC)
        items: list[ExternalEvidenceItem] = []
        for rank, record in enumerate(records[:limit]):
            if not isinstance(record, dict):
                continue
            title = str(record.get("title", "")).strip()
            url = str(record.get("url", "")).strip()
            if not title or not url:
                continue
            evidence_id = f"web-{_safe_id(url) or rank}"
            score = _score(record.get("score"), rank, limit)
            items.append(
                ExternalEvidenceItem(
                    evidence_id=evidence_id[:64],
                    source_type=ExternalSourceType.WEB_PAGE,
                    provider=self.provider_name,
                    source_ref=f"external://web/{evidence_id}",
                    title=title,
                    canonical_url=validate_http_url(url),
                    content_excerpt=str(
                        record.get("content", record.get("snippet", "")) or ""
                    ).strip(),
                    published_at=_parse_date(record.get("published_date")),
                    retrieved_at=now,
                    relevance_score=score,
                    trust_level="medium",
                    metadata={
                        "gateway": self.base_url,
                        "raw_rank": rank,
                    },
                )
            )
        return items


class TavilySearchProvider(HttpAcademicProvider):
    """Tavily POST search adapter with bounded, excerpt-only responses."""

    provider_name = "tavily"
    source_scope = ExternalSourceScope.WEB

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        search_depth: str = "basic",
        topic: str = "general",
        include_answer: bool = False,
        include_raw_content: bool = False,
        max_results: int = 5,
        client: Any = None,
        timeout_seconds: float = 30,
        min_delay_seconds: float = 1,
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
        self.auth_header = auth_header.strip() or "Authorization"
        self.auth_scheme = auth_scheme.strip() or "Bearer"
        self.search_depth = search_depth.strip() or "basic"
        self.topic = topic.strip() or "general"
        self.include_answer = include_answer
        self.include_raw_content = include_raw_content
        self.max_results = max(1, max_results)

    async def search(
        self,
        query: str,
        *,
        limit: int,
        prefer_high_citation: bool = False,
    ) -> list[ExternalEvidenceItem]:
        del prefer_high_citation
        bounded_limit = min(limit, self.max_results, 20)
        response = await self._post_json_with_headers(
            "",
            payload={
                "query": query,
                "search_depth": self.search_depth,
                "topic": self.topic,
                "max_results": bounded_limit,
                "include_answer": self.include_answer,
                "include_raw_content": self.include_raw_content,
                "include_images": False,
                "include_favicon": False,
            },
            headers={
                self.auth_header: f"{self.auth_scheme} {self.api_key}".strip()
            },
        )
        try:
            records = response.json()["results"]
        except (TypeError, KeyError, ValueError) as exc:
            raise AcademicProviderError("tavily: invalid_json") from exc
        if not isinstance(records, list):
            raise AcademicProviderError("tavily: invalid_results")
        return _map_web_records(
            provider=self.provider_name,
            base_url=self.base_url,
            records=records,
            limit=bounded_limit,
            content_keys=("content",),
            date_keys=("published_date",),
        )


class BraveSearchProvider(HttpAcademicProvider):
    """Brave Web Search adapter using the documented token header."""

    provider_name = "brave"
    source_scope = ExternalSourceScope.WEB

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        auth_header: str = "X-Subscription-Token",
        country: str = "CN",
        search_lang: str = "zh",
        max_results: int = 5,
        client: Any = None,
        timeout_seconds: float = 30,
        min_delay_seconds: float = 1,
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
        self.auth_header = auth_header.strip() or "X-Subscription-Token"
        self.country = country.strip().upper() or "CN"
        self.search_lang = search_lang.strip() or "zh"
        self.max_results = max(1, max_results)

    async def search(
        self,
        query: str,
        *,
        limit: int,
        prefer_high_citation: bool = False,
    ) -> list[ExternalEvidenceItem]:
        del prefer_high_citation
        bounded_limit = min(limit, self.max_results, 20)
        response = await self._get_with_headers(
            "",
            params={
                "q": query,
                "count": bounded_limit,
                "offset": 0,
                "country": self.country,
                "search_lang": self.search_lang,
                "result_filter": "web",
                "text_decorations": "false",
                "safesearch": "off",
            },
            headers={self.auth_header: self.api_key},
        )
        try:
            records = response.json().get("web", {}).get("results", [])
        except (AttributeError, TypeError, ValueError) as exc:
            raise AcademicProviderError("brave: invalid_json") from exc
        if not isinstance(records, list):
            raise AcademicProviderError("brave: invalid_results")
        return _map_web_records(
            provider=self.provider_name,
            base_url=self.base_url,
            records=records,
            limit=bounded_limit,
            content_keys=("description", "snippet"),
            date_keys=("page_age", "published_date"),
        )


class SerpApiSearchProvider(HttpAcademicProvider):
    """SerpApi Google-compatible search adapter."""

    provider_name = "serpapi"
    source_scope = ExternalSourceScope.WEB

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        engine: str = "google",
        max_results: int = 5,
        client: Any = None,
        timeout_seconds: float = 30,
        min_delay_seconds: float = 1,
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
        self.engine = engine.strip() or "google"
        self.max_results = max(1, max_results)

    async def search(
        self,
        query: str,
        *,
        limit: int,
        prefer_high_citation: bool = False,
    ) -> list[ExternalEvidenceItem]:
        del prefer_high_citation
        bounded_limit = min(limit, self.max_results, 20)
        response = await self._get(
            "",
            params={
                "engine": self.engine,
                "q": query,
                "api_key": self.api_key,
                "output": "json",
                "num": bounded_limit,
                "hl": "zh-cn",
                "gl": "cn",
            },
        )
        try:
            records = response.json().get("organic_results", [])
        except (AttributeError, TypeError, ValueError) as exc:
            raise AcademicProviderError("serpapi: invalid_json") from exc
        if not isinstance(records, list):
            raise AcademicProviderError("serpapi: invalid_results")
        return _map_web_records(
            provider=self.provider_name,
            base_url=self.base_url,
            records=records,
            limit=bounded_limit,
            content_keys=("snippet", "description"),
            date_keys=("date",),
        )


class AliyunIqsSearchProvider(HttpAcademicProvider):
    """Alibaba IQS UnifiedSearch adapter for domestic web fallback."""

    provider_name = "aliyun_iqs"
    source_scope = ExternalSourceScope.WEB

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        engine_type: str = "Generic",
        time_range: str = "NoLimit",
        max_results: int = 5,
        client: Any = None,
        timeout_seconds: float = 30,
        min_delay_seconds: float = 1,
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
        self.engine_type = engine_type.strip() or "Generic"
        self.time_range = time_range.strip() or "NoLimit"
        self.max_results = max(1, max_results)

    async def search(
        self,
        query: str,
        *,
        limit: int,
        prefer_high_citation: bool = False,
    ) -> list[ExternalEvidenceItem]:
        del prefer_high_citation
        bounded_limit = min(limit, self.max_results, 20)
        payload: dict[str, Any] = {
            "query": query,
            "engineType": self.engine_type,
            "timeRange": self.time_range,
            "contents": {
                "mainText": False,
                "markdownText": False,
                "summary": False,
                "rerankScore": True,
            },
        }
        if self.engine_type.casefold() != "generic":
            payload["advancedParams"] = {"numResults": str(bounded_limit)}
        response = await self._post_json_with_headers(
            "",
            payload=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        try:
            records = response.json()["pageItems"]
        except (TypeError, KeyError, ValueError) as exc:
            raise AcademicProviderError("aliyun_iqs: invalid_json") from exc
        if not isinstance(records, list):
            raise AcademicProviderError("aliyun_iqs: invalid_results")
        return _map_web_records(
            provider=self.provider_name,
            base_url=self.base_url,
            records=records,
            limit=bounded_limit,
            content_keys=("summary", "snippet", "mainText"),
            date_keys=("publishedTime",),
            score_keys=("rerankScore", "score"),
        )


class BochaSearchProvider(HttpAcademicProvider):
    """Bocha AI Web Search adapter."""

    provider_name = "bocha"
    source_scope = ExternalSourceScope.WEB

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        freshness: str = "noLimit",
        summary: bool = True,
        max_results: int = 5,
        client: Any = None,
        timeout_seconds: float = 30,
        min_delay_seconds: float = 1,
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
        self.auth_header = auth_header.strip() or "Authorization"
        self.auth_scheme = auth_scheme.strip() or "Bearer"
        self.freshness = freshness.strip() or "noLimit"
        self.summary = summary
        self.max_results = max(1, max_results)

    async def search(
        self,
        query: str,
        *,
        limit: int,
        prefer_high_citation: bool = False,
    ) -> list[ExternalEvidenceItem]:
        del prefer_high_citation
        bounded_limit = min(limit, self.max_results, 50)
        response = await self._post_json_with_headers(
            "",
            payload={
                "query": query,
                "freshness": self.freshness,
                "summary": self.summary,
                "count": bounded_limit,
            },
            headers={
                self.auth_header: f"{self.auth_scheme} {self.api_key}".strip()
            },
        )
        try:
            payload = response.json()
            records = payload.get("data", {}).get("webPages", {}).get("value", [])
            if not records:
                records = payload.get("results", [])
        except (AttributeError, TypeError, ValueError) as exc:
            raise AcademicProviderError("bocha: invalid_json") from exc
        if not isinstance(records, list):
            raise AcademicProviderError("bocha: invalid_results")
        return _map_web_records(
            provider=self.provider_name,
            base_url=self.base_url,
            records=records,
            limit=bounded_limit,
            content_keys=("summary", "snippet", "name"),
            date_keys=("datePublished", "publishedDate", "published_date"),
            url_keys=("url", "link"),
        )


class SearxngSearchProvider(HttpAcademicProvider):
    """Adapter for a local SearXNG JSON search endpoint."""

    provider_name = "searxng"
    source_scope = ExternalSourceScope.WEB

    def __init__(
        self,
        *,
        base_url: str,
        result_format: str = "json",
        categories: str = "general",
        language: str = "zh-CN",
        client: Any = None,
        timeout_seconds: float = 30,
        min_delay_seconds: float = 1,
        trust_env: bool = False,
        max_concurrency: int = 1,
    ) -> None:
        super().__init__(
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
            min_delay_seconds=min_delay_seconds,
            trust_env=trust_env,
            max_concurrency=max_concurrency,
        )
        self.result_format = result_format.strip() or "json"
        self.categories = categories.strip() or "general"
        self.language = language.strip() or "zh-CN"

    async def search(
        self,
        query: str,
        *,
        limit: int,
        prefer_high_citation: bool = False,
    ) -> list[ExternalEvidenceItem]:
        del prefer_high_citation
        response = await self._get(
            "",
            params={
                "q": query,
                "format": self.result_format,
                "categories": self.categories,
                "language": self.language,
                "safesearch": 0,
                "pageno": 1,
            },
        )
        try:
            records = response.json()["results"]
        except (TypeError, KeyError, ValueError) as exc:
            raise AcademicProviderError("searxng: invalid_json") from exc
        if not isinstance(records, list):
            raise AcademicProviderError("searxng: invalid_results")

        now = datetime.now(UTC)
        items: list[ExternalEvidenceItem] = []
        for rank, record in enumerate(records[:limit]):
            if not isinstance(record, dict):
                continue
            title = str(record.get("title", "")).strip()
            url = str(record.get("url", record.get("link", ""))).strip()
            if not title or not url:
                continue
            evidence_id = f"searxng-{_safe_id(url) or rank}"
            items.append(
                ExternalEvidenceItem(
                    evidence_id=evidence_id[:64],
                    source_type=ExternalSourceType.WEB_PAGE,
                    provider=self.provider_name,
                    source_ref=f"external://searxng/{evidence_id}",
                    title=title,
                    canonical_url=validate_http_url(url),
                    content_excerpt=str(
                        record.get("content", record.get("snippet", "")) or ""
                    ).strip(),
                    published_at=_parse_date(
                        record.get("publishedDate", record.get("published_date"))
                    ),
                    retrieved_at=now,
                    relevance_score=_score(record.get("score"), rank, limit),
                    trust_level="medium",
                    metadata={
                        "gateway": self.base_url,
                        "engine": str(record.get("engine", "") or ""),
                        "raw_rank": rank,
                    },
                )
            )
        return items


class NewsRssSearchProvider(HttpAcademicProvider):
    """Public RSS search adapter for reports and conference signals."""

    provider_name = "news_rss"
    source_scope = ExternalSourceScope.WEB

    def __init__(
        self,
        *,
        base_url: str,
        client: Any = None,
        timeout_seconds: float = 15,
        min_delay_seconds: float = 1,
        max_concurrency: int = 1,
    ) -> None:
        super().__init__(
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
            min_delay_seconds=min_delay_seconds,
            max_concurrency=max_concurrency,
        )

    async def search(
        self,
        query: str,
        *,
        limit: int,
        prefer_high_citation: bool = False,
    ) -> list[ExternalEvidenceItem]:
        del prefer_high_citation
        response = await self._get(
            "",
            params={
                "q": query,
                "hl": "zh-CN",
                "gl": "CN",
                "ceid": "CN:zh-Hans",
            },
        )
        try:
            root = ElementTree.fromstring(response.text)
        except ElementTree.ParseError as exc:
            raise AcademicProviderError("news_rss: invalid_xml") from exc
        now = datetime.now(UTC)
        category = _rss_category(query)
        items: list[ExternalEvidenceItem] = []
        for rank, entry in enumerate(root.findall("./channel/item")[:limit]):
            title = _xml_text(entry.find("title"))
            url = _xml_text(entry.find("link"))
            if not title or not url:
                continue
            published = _parse_rss_date(_xml_text(entry.find("pubDate")))
            evidence_id = f"rss-{_safe_id(url) or rank}"[:64]
            description = _xml_text(entry.find("description"))
            source = _xml_text(entry.find("source"))
            items.append(
                ExternalEvidenceItem(
                    evidence_id=evidence_id,
                    source_type=ExternalSourceType.WEB_PAGE,
                    provider=self.provider_name,
                    source_ref=f"external://news/{evidence_id}",
                    title=title,
                    canonical_url=validate_http_url(url),
                    content_excerpt=description[:12000],
                    venue=source,
                    published_at=published,
                    retrieved_at=now,
                    relevance_score=max(0.0, 1.0 - rank / max(limit, 1)),
                    trust_level="medium",
                    metadata={
                        "category": category,
                        "source": source,
                        "feed": self.base_url,
                        "raw_rank": rank,
                    },
                )
            )
        return items


def _map_web_records(
    *,
    provider: str,
    base_url: str,
    records: list[Any],
    limit: int,
    content_keys: tuple[str, ...],
    date_keys: tuple[str, ...],
    score_keys: tuple[str, ...] = ("score",),
    url_keys: tuple[str, ...] = ("url", "link"),
) -> list[ExternalEvidenceItem]:
    now = datetime.now(UTC)
    items: list[ExternalEvidenceItem] = []
    for rank, record in enumerate(records[:limit]):
        if not isinstance(record, dict):
            continue
        title = _first_record_value(record, ("title", "name"))
        url = _first_record_value(record, url_keys)
        if not title or not url:
            continue
        excerpt = _first_record_value(record, content_keys)
        published = _first_record_value(record, date_keys)
        score_value = next(
            (record.get(key) for key in score_keys if record.get(key) is not None),
            None,
        )
        evidence_id = f"{provider}-{_safe_id(url) or rank}"[:64]
        try:
            items.append(
                ExternalEvidenceItem(
                    evidence_id=evidence_id,
                    source_type=ExternalSourceType.WEB_PAGE,
                    provider=provider,
                    source_ref=f"external://{provider}/{evidence_id}",
                    title=_clean_markup(title),
                    canonical_url=validate_http_url(url),
                    content_excerpt=_clean_markup(excerpt)[:12_000],
                    published_at=_parse_date(published),
                    retrieved_at=now,
                    relevance_score=_score(score_value, rank, limit),
                    trust_level="medium",
                    metadata={
                        "gateway": base_url,
                        "raw_rank": rank,
                    },
                )
            )
        except (ValidationError, ValueError):
            continue
    return items


def _first_record_value(record: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _clean_markup(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")


def _score(value: object, rank: int, limit: int) -> float:
    try:
        parsed = float(value) if isinstance(value, (int, float, str)) else 0.0
    except (TypeError, ValueError):
        parsed = 0.0
    if parsed <= 0:
        parsed = 1.0 - rank / max(limit, 1)
    return max(0.0, min(1.0, parsed))


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _xml_text(node: ElementTree.Element | None) -> str:
    if node is None:
        return ""
    return re.sub(r"<[^>]+>", " ", "".join(node.itertext())).strip()


def _parse_rss_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _rss_category(query: str) -> str:
    normalized = query.casefold()
    if any(
        term in normalized
        for term in ("会议", "conference", "workshop", "symposium")
    ):
        return "conference"
    return "web_report"
