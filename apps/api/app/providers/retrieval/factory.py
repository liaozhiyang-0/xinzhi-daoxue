from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence

import httpx

from app.contracts import ExternalRetrievalResult, ExternalSourceScope
from app.core.config import Settings
from app.providers.retrieval.academic import (
    AcademicSearchService,
    ArxivAcademicProvider,
    CnkiAcademicProvider,
    CrossrefAcademicProvider,
    OpenAlexAcademicProvider,
    SemanticScholarAcademicProvider,
)
from app.providers.retrieval.web import (
    AliyunIqsSearchProvider,
    BochaSearchProvider,
    BraveSearchProvider,
    JsonWebSearchProvider,
    NewsRssSearchProvider,
    SearxngSearchProvider,
    SerpApiSearchProvider,
    TavilySearchProvider,
)


def create_external_search_service(settings: Settings) -> AcademicSearchService:
    """Create a deferred service without opening network clients during boot."""

    provider_names = _configured_provider_names(settings)
    return DeferredAcademicSearchService(
        lambda: _build_external_search_service(settings),
        provider_names=provider_names,
        cache_size=settings.external_retrieval_cache_size,
        cache_ttl_seconds=settings.external_retrieval_cache_ttl_seconds,
        max_query_variants=settings.external_retrieval_max_query_variants,
    )


class DeferredAcademicSearchService(AcademicSearchService):
    """Lazy facade preserving the normal AcademicSearchService contract."""

    def __init__(
        self,
        builder: Callable[[], AcademicSearchService],
        *,
        provider_names: tuple[str, ...],
        cache_size: int,
        cache_ttl_seconds: float,
        max_query_variants: int,
    ) -> None:
        super().__init__(
            (),
            cache_size=cache_size,
            cache_ttl_seconds=cache_ttl_seconds,
            max_query_variants=max_query_variants,
        )
        self._builder = builder
        self._provider_names = provider_names
        self._service: AcademicSearchService | None = None
        self._build_lock = asyncio.Lock()

    async def _ensure_service(self) -> AcademicSearchService:
        if self._service is not None:
            return self._service
        async with self._build_lock:
            if self._service is None:
                self._service = self._builder()
        return self._service

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
        service = await self._ensure_service()
        return await service.search(
            query,
            limit=limit,
            normalized_query=normalized_query,
            retrieval_trace_id=retrieval_trace_id,
            provider_names=provider_names,
            source_scopes=source_scopes,
            freshness_days=freshness_days,
            prefer_high_citation=prefer_high_citation,
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
        service = await self._ensure_service()
        return await service.search_many(
            query,
            query_variants=query_variants,
            limit=limit,
            retrieval_trace_id=retrieval_trace_id,
            provider_names=provider_names,
            source_scopes=source_scopes,
            freshness_days=freshness_days,
            prefer_high_citation=prefer_high_citation,
        )

    def fallback_provider_names(
        self,
        *,
        provider_names: Sequence[str] | None = None,
        source_scopes: Sequence[ExternalSourceScope] | None = None,
    ) -> tuple[str, ...]:
        if self._service is None:
            return tuple(
                name
                for name in self._provider_names
                if name.casefold() not in {"openalex", "crossref", "arxiv"}
            )
        return self._service.fallback_provider_names(
            provider_names=provider_names,
            source_scopes=source_scopes,
        )

    def health(self) -> dict[str, object]:
        if self._service is not None:
            return self._service.health()
        return {
            "configured": bool(self._provider_names),
            "deferred": True,
            "providers": [
                {"name": name, "last_status": "not_initialized"}
                for name in self._provider_names
            ],
            "cache": {
                "enabled": self.cache_size > 0 and self.cache_ttl_seconds > 0,
                "entries": 0,
                "max_entries": self.cache_size,
                "ttl_seconds": self.cache_ttl_seconds,
            },
        }

    async def close(self) -> None:
        if self._service is not None:
            await self._service.close()


def _build_external_search_service(settings: Settings) -> AcademicSearchService:
    """Build configured providers and one shared TLS transport."""

    shared_client = httpx.AsyncClient(
        timeout=httpx.Timeout(_max_external_timeout(settings)),
        follow_redirects=True,
        trust_env=True,
    )

    semantic_key = _usable_secret(
        settings.external_semantic_scholar_api_key.get_secret_value()
    )
    providers = [
        ArxivAcademicProvider(
            base_url=settings.external_arxiv_base_url,
            client=shared_client,
            timeout_seconds=settings.external_arxiv_timeout_seconds,
            min_delay_seconds=settings.external_arxiv_min_delay_seconds,
            max_concurrency=settings.external_arxiv_max_concurrency,
        ),
        CrossrefAcademicProvider(
            base_url=settings.external_crossref_base_url,
            client=shared_client,
            mailto=settings.external_crossref_mailto,
            timeout_seconds=settings.external_crossref_timeout_seconds,
            min_delay_seconds=settings.external_crossref_min_delay_seconds,
            max_concurrency=settings.external_crossref_max_concurrency,
        ),
        OpenAlexAcademicProvider(
            base_url=settings.external_openalex_base_url,
            client=shared_client,
            api_key=settings.external_openalex_api_key.get_secret_value(),
            mailto=settings.external_openalex_mailto,
            timeout_seconds=settings.external_openalex_timeout_seconds,
            min_delay_seconds=settings.external_openalex_min_delay_seconds,
            max_concurrency=settings.external_openalex_max_concurrency,
        ),
    ]
    if settings.external_semantic_scholar_base_url.strip() and (
        semantic_key or settings.external_semantic_scholar_allow_unauthenticated
    ):
        providers.append(
            SemanticScholarAcademicProvider(
                base_url=settings.external_semantic_scholar_base_url,
                api_key=semantic_key,
                client=shared_client,
                timeout_seconds=settings.external_semantic_scholar_timeout_seconds,
                min_delay_seconds=settings.external_semantic_scholar_min_delay_seconds,
                max_concurrency=settings.external_semantic_scholar_max_concurrency,
            )
        )
    if settings.external_cnki_base_url.strip():
        providers.append(
            CnkiAcademicProvider(
                base_url=settings.external_cnki_base_url,
                api_key=settings.external_cnki_api_key.get_secret_value(),
                auth_header=settings.external_cnki_auth_header,
                client=shared_client,
                timeout_seconds=settings.external_cnki_timeout_seconds,
            )
        )
    if settings.external_web_search_base_url.strip():
        providers.append(
            JsonWebSearchProvider(
                base_url=settings.external_web_search_base_url,
                api_key=settings.external_web_search_api_key.get_secret_value(),
                auth_header=settings.external_web_search_auth_header,
                client=shared_client,
                timeout_seconds=settings.external_web_search_timeout_seconds,
            )
        )
    if settings.external_tavily_base_url.strip() and _usable_secret(
        settings.external_tavily_api_key.get_secret_value()
    ):
        providers.append(
            TavilySearchProvider(
                base_url=settings.external_tavily_base_url,
                api_key=settings.external_tavily_api_key.get_secret_value(),
                auth_header=settings.external_tavily_auth_header,
                auth_scheme=settings.external_tavily_auth_scheme,
                client=shared_client,
                search_depth=settings.external_tavily_search_depth,
                topic=settings.external_tavily_topic,
                include_answer=settings.external_tavily_include_answer,
                include_raw_content=settings.external_tavily_include_raw_content,
                max_results=settings.external_tavily_max_results,
                timeout_seconds=settings.external_tavily_timeout_seconds,
                min_delay_seconds=settings.external_tavily_min_delay_seconds,
                max_concurrency=settings.external_tavily_max_concurrency,
            )
        )
    if settings.external_brave_base_url.strip() and _usable_secret(
        settings.external_brave_api_key.get_secret_value()
    ):
        providers.append(
            BraveSearchProvider(
                base_url=settings.external_brave_base_url,
                api_key=settings.external_brave_api_key.get_secret_value(),
                auth_header=settings.external_brave_auth_header,
                country=settings.external_brave_country,
                search_lang=settings.external_brave_search_lang,
                client=shared_client,
                max_results=settings.external_brave_max_results,
                timeout_seconds=settings.external_brave_timeout_seconds,
                min_delay_seconds=settings.external_brave_min_delay_seconds,
                max_concurrency=settings.external_brave_max_concurrency,
            )
        )
    if settings.external_serpapi_base_url.strip() and _usable_secret(
        settings.external_serpapi_api_key.get_secret_value()
    ):
        providers.append(
            SerpApiSearchProvider(
                base_url=settings.external_serpapi_base_url,
                api_key=settings.external_serpapi_api_key.get_secret_value(),
                engine=settings.external_serpapi_engine,
                client=shared_client,
                max_results=settings.external_serpapi_max_results,
                timeout_seconds=settings.external_serpapi_timeout_seconds,
                min_delay_seconds=settings.external_serpapi_min_delay_seconds,
                max_concurrency=settings.external_serpapi_max_concurrency,
            )
        )
    if settings.external_searxng_base_url.strip():
        providers.append(
            SearxngSearchProvider(
                base_url=settings.external_searxng_base_url,
                result_format=settings.external_searxng_format,
                categories=settings.external_searxng_categories,
                language=settings.external_searxng_language,
                timeout_seconds=settings.external_searxng_timeout_seconds,
                min_delay_seconds=settings.external_searxng_min_delay_seconds,
                max_concurrency=settings.external_searxng_max_concurrency,
            )
        )
    if settings.external_aliyun_iqs_base_url.strip() and _usable_secret(
        settings.external_aliyun_iqs_api_key.get_secret_value()
    ):
        providers.append(
            AliyunIqsSearchProvider(
                base_url=settings.external_aliyun_iqs_base_url,
                api_key=settings.external_aliyun_iqs_api_key.get_secret_value(),
                engine_type=settings.external_aliyun_iqs_engine_type,
                time_range=settings.external_aliyun_iqs_time_range,
                client=shared_client,
                max_results=settings.external_aliyun_iqs_max_results,
                timeout_seconds=settings.external_aliyun_iqs_timeout_seconds,
                min_delay_seconds=settings.external_aliyun_iqs_min_delay_seconds,
                max_concurrency=settings.external_aliyun_iqs_max_concurrency,
            )
        )
    if settings.external_bocha_base_url.strip() and _usable_secret(
        settings.external_bocha_api_key.get_secret_value()
    ):
        providers.append(
            BochaSearchProvider(
                base_url=settings.external_bocha_base_url,
                api_key=settings.external_bocha_api_key.get_secret_value(),
                auth_header=settings.external_bocha_auth_header,
                auth_scheme=settings.external_bocha_auth_scheme,
                freshness=settings.external_bocha_freshness,
                summary=settings.external_bocha_summary,
                client=shared_client,
                max_results=settings.external_bocha_max_results,
                timeout_seconds=settings.external_bocha_timeout_seconds,
                min_delay_seconds=settings.external_bocha_min_delay_seconds,
                max_concurrency=settings.external_bocha_max_concurrency,
            )
        )
    if settings.external_news_rss_base_url.strip():
        providers.append(
            NewsRssSearchProvider(
                base_url=settings.external_news_rss_base_url,
                client=shared_client,
                timeout_seconds=settings.external_news_rss_timeout_seconds,
                min_delay_seconds=settings.external_news_rss_min_delay_seconds,
                max_concurrency=settings.external_news_rss_max_concurrency,
            )
        )
    return AcademicSearchService(
        providers,
        cache_size=settings.external_retrieval_cache_size,
        cache_ttl_seconds=settings.external_retrieval_cache_ttl_seconds,
        max_retries=settings.external_retrieval_provider_retries,
        rate_limit_cooldown_seconds=(
            settings.external_retrieval_rate_limit_cooldown_seconds
        ),
        max_provider_concurrency=(settings.external_retrieval_max_provider_concurrency),
        max_query_variants=settings.external_retrieval_max_query_variants,
        provider_tiers=(
            ("openalex", "crossref", "arxiv"),
            ("semantic_scholar", "cnki"),
            ("searxng",),
            ("web_json",),
            ("aliyun_iqs", "bocha", "tavily", "brave", "serpapi"),
            ("news_rss",),
        ),
        owned_clients=(shared_client,),
    )


def _usable_secret(value: str) -> str:
    """Return credentials only when they are not common placeholder text."""

    normalized = value.strip()
    if not normalized:
        return ""
    folded = normalized.casefold()
    placeholders = {
        "your-api-key",
        "your_api_key",
        "your key",
        "你的apikey",
        "你的semantic_scholar_api_key",
    }
    if folded in placeholders or folded.startswith("your_"):
        return ""
    return normalized


def _configured_provider_names(settings: Settings) -> tuple[str, ...]:
    """Return provider metadata without constructing any HTTP transports."""

    names = ["arxiv", "crossref", "openalex"]
    if settings.external_semantic_scholar_base_url.strip() and (
        _usable_secret(settings.external_semantic_scholar_api_key.get_secret_value())
        or settings.external_semantic_scholar_allow_unauthenticated
    ):
        names.append("semantic_scholar")
    if settings.external_cnki_base_url.strip():
        names.append("cnki")
    if settings.external_web_search_base_url.strip():
        names.append("web_json")
    optional = (
        ("tavily", settings.external_tavily_base_url, settings.external_tavily_api_key),
        ("brave", settings.external_brave_base_url, settings.external_brave_api_key),
        (
            "serpapi",
            settings.external_serpapi_base_url,
            settings.external_serpapi_api_key,
        ),
        (
            "aliyun_iqs",
            settings.external_aliyun_iqs_base_url,
            settings.external_aliyun_iqs_api_key,
        ),
        ("bocha", settings.external_bocha_base_url, settings.external_bocha_api_key),
    )
    for name, base_url, api_key in optional:
        if base_url.strip() and _usable_secret(api_key.get_secret_value()):
            names.append(name)
    if settings.external_searxng_base_url.strip():
        names.append("searxng")
    if settings.external_news_rss_base_url.strip():
        names.append("news_rss")
    return tuple(names)


def _max_external_timeout(settings: Settings) -> float:
    """Use one transport timeout; providers still pass their own request timeout."""

    values = (
        settings.external_arxiv_timeout_seconds,
        settings.external_crossref_timeout_seconds,
        settings.external_openalex_timeout_seconds,
        settings.external_semantic_scholar_timeout_seconds,
        settings.external_cnki_timeout_seconds,
        settings.external_web_search_timeout_seconds,
        settings.external_tavily_timeout_seconds,
        settings.external_brave_timeout_seconds,
        settings.external_serpapi_timeout_seconds,
        settings.external_searxng_timeout_seconds,
        settings.external_aliyun_iqs_timeout_seconds,
        settings.external_bocha_timeout_seconds,
        settings.external_news_rss_timeout_seconds,
    )
    return max(0.1, max(values))
