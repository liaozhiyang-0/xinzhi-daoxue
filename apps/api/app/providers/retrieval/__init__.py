from app.providers.retrieval.academic import (
    AcademicSearchProvider,
    AcademicSearchService,
    ArxivAcademicProvider,
    CnkiAcademicProvider,
    CrossrefAcademicProvider,
    OpenAlexAcademicProvider,
    SemanticScholarAcademicProvider,
    merge_academic_results,
)
from app.providers.retrieval.factory import create_external_search_service
from app.providers.retrieval.web import JsonWebSearchProvider

__all__ = [
    "AcademicSearchProvider",
    "AcademicSearchService",
    "ArxivAcademicProvider",
    "CnkiAcademicProvider",
    "CrossrefAcademicProvider",
    "OpenAlexAcademicProvider",
    "SemanticScholarAcademicProvider",
    "merge_academic_results",
    "JsonWebSearchProvider",
    "create_external_search_service",
]
