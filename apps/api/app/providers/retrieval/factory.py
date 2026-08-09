from __future__ import annotations

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
    """Build configured external providers without making a network request."""

    semantic_key = _usable_secret(
        settings.external_semantic_scholar_api_key.get_secret_value()
    )
    providers = [
        ArxivAcademicProvider(
            base_url=settings.external_arxiv_base_url,
            timeout_seconds=settings.external_arxiv_timeout_seconds,
            min_delay_seconds=settings.external_arxiv_min_delay_seconds,
            max_concurrency=settings.external_arxiv_max_concurrency,
        ),
        CrossrefAcademicProvider(
            base_url=settings.external_crossref_base_url,
            mailto=settings.external_crossref_mailto,
            timeout_seconds=settings.external_crossref_timeout_seconds,
            min_delay_seconds=settings.external_crossref_min_delay_seconds,
            max_concurrency=settings.external_crossref_max_concurrency,
        ),
        OpenAlexAcademicProvider(
            base_url=settings.external_openalex_base_url,
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
                timeout_seconds=settings.external_cnki_timeout_seconds,
            )
        )
    if settings.external_web_search_base_url.strip():
        providers.append(
            JsonWebSearchProvider(
                base_url=settings.external_web_search_base_url,
                api_key=settings.external_web_search_api_key.get_secret_value(),
                auth_header=settings.external_web_search_auth_header,
                timeout_seconds=settings.external_web_search_timeout_seconds,
            )
        )
    if (
        settings.external_tavily_base_url.strip()
        and _usable_secret(settings.external_tavily_api_key.get_secret_value())
    ):
        providers.append(
            TavilySearchProvider(
                base_url=settings.external_tavily_base_url,
                api_key=settings.external_tavily_api_key.get_secret_value(),
                auth_header=settings.external_tavily_auth_header,
                auth_scheme=settings.external_tavily_auth_scheme,
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
    if (
        settings.external_brave_base_url.strip()
        and _usable_secret(settings.external_brave_api_key.get_secret_value())
    ):
        providers.append(
            BraveSearchProvider(
                base_url=settings.external_brave_base_url,
                api_key=settings.external_brave_api_key.get_secret_value(),
                auth_header=settings.external_brave_auth_header,
                country=settings.external_brave_country,
                search_lang=settings.external_brave_search_lang,
                max_results=settings.external_brave_max_results,
                timeout_seconds=settings.external_brave_timeout_seconds,
                min_delay_seconds=settings.external_brave_min_delay_seconds,
                max_concurrency=settings.external_brave_max_concurrency,
            )
        )
    if (
        settings.external_serpapi_base_url.strip()
        and _usable_secret(settings.external_serpapi_api_key.get_secret_value())
    ):
        providers.append(
            SerpApiSearchProvider(
                base_url=settings.external_serpapi_base_url,
                api_key=settings.external_serpapi_api_key.get_secret_value(),
                engine=settings.external_serpapi_engine,
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
    if (
        settings.external_aliyun_iqs_base_url.strip()
        and _usable_secret(settings.external_aliyun_iqs_api_key.get_secret_value())
    ):
        providers.append(
            AliyunIqsSearchProvider(
                base_url=settings.external_aliyun_iqs_base_url,
                api_key=settings.external_aliyun_iqs_api_key.get_secret_value(),
                engine_type=settings.external_aliyun_iqs_engine_type,
                time_range=settings.external_aliyun_iqs_time_range,
                max_results=settings.external_aliyun_iqs_max_results,
                timeout_seconds=settings.external_aliyun_iqs_timeout_seconds,
                min_delay_seconds=settings.external_aliyun_iqs_min_delay_seconds,
                max_concurrency=settings.external_aliyun_iqs_max_concurrency,
            )
        )
    if (
        settings.external_bocha_base_url.strip()
        and _usable_secret(settings.external_bocha_api_key.get_secret_value())
    ):
        providers.append(
            BochaSearchProvider(
                base_url=settings.external_bocha_base_url,
                api_key=settings.external_bocha_api_key.get_secret_value(),
                auth_header=settings.external_bocha_auth_header,
                auth_scheme=settings.external_bocha_auth_scheme,
                freshness=settings.external_bocha_freshness,
                summary=settings.external_bocha_summary,
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
        max_provider_concurrency=(
            settings.external_retrieval_max_provider_concurrency
        ),
        max_query_variants=settings.external_retrieval_max_query_variants,
        provider_tiers=(
            ("openalex", "crossref", "arxiv"),
            ("searxng",),
            ("aliyun_iqs", "bocha", "tavily"),
            ("news_rss",),
        ),
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
