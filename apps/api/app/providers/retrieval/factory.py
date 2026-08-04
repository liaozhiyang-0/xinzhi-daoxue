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
from app.providers.retrieval.web import JsonWebSearchProvider


def create_external_search_service(settings: Settings) -> AcademicSearchService:
    """Build configured external providers without making a network request."""

    providers = [
        ArxivAcademicProvider(
            base_url=settings.external_arxiv_base_url,
            timeout_seconds=settings.external_retrieval_timeout_seconds,
        ),
        CrossrefAcademicProvider(
            base_url=settings.external_crossref_base_url,
            timeout_seconds=settings.external_retrieval_timeout_seconds,
        ),
        OpenAlexAcademicProvider(
            base_url=settings.external_openalex_base_url,
            api_key=settings.external_openalex_api_key.get_secret_value(),
            mailto=settings.external_openalex_mailto,
            timeout_seconds=settings.external_retrieval_timeout_seconds,
        ),
        SemanticScholarAcademicProvider(
            base_url=settings.external_semantic_scholar_base_url,
            api_key=settings.external_semantic_scholar_api_key.get_secret_value(),
            timeout_seconds=settings.external_retrieval_timeout_seconds,
        ),
    ]
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
    return AcademicSearchService(
        providers,
        cache_size=settings.external_retrieval_cache_size,
        cache_ttl_seconds=settings.external_retrieval_cache_ttl_seconds,
        max_retries=settings.external_retrieval_provider_retries,
    )
