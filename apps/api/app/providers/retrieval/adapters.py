from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.contracts import ExternalEvidenceItem


@dataclass(frozen=True, slots=True)
class ProviderSearchContext:
    """Provider-neutral context passed to a source-specific query adapter."""

    query: str
    normalized_query: str
    limit: int
    freshness_days: int | None = None
    prefer_high_citation: bool = False


@dataclass(frozen=True, slots=True)
class ProviderQuery:
    """A provider-ready query plus tokens used for local re-ranking."""

    text: str
    terms: tuple[str, ...] = ()


class ProviderQueryAdapter(Protocol):
    """Extension point for provider-specific query and ranking behavior."""

    def build_query(self, context: ProviderSearchContext) -> ProviderQuery: ...

    def score(
        self,
        item: ExternalEvidenceItem,
        query: ProviderQuery,
        *,
        rank: int,
        prefer_high_citation: bool,
    ) -> float: ...


def _cjk(*codepoints: int) -> str:
    return "".join(chr(codepoint) for codepoint in codepoints)


_OPENALEX_ALIASES: tuple[tuple[str, str], ...] = (
    (_cjk(0x4EBA, 0x5DE5, 0x667A, 0x80FD), '"artificial intelligence"'),
    (_cjk(0x673A, 0x5668, 0x5B66, 0x4E60), '"machine learning"'),
    (_cjk(0x6DF1, 0x5EA6, 0x5B66, 0x4E60), '"deep learning"'),
    (_cjk(0x751F, 0x6210, 0x5F0F, 0x4EBA, 0x5DE5, 0x667A, 0x80FD), '"generative AI"'),
    (_cjk(0x5927, 0x6A21, 0x578B), '"large language model"'),
    (_cjk(0x57FA, 0x7840, 0x6A21, 0x578B), '"foundation model"'),
    (
        _cjk(0x67D4, 0x6027, 0x7535, 0x5B50, 0x5668, 0x4EF6),
        '"flexible electronics" device',
    ),
    (_cjk(0x67D4, 0x6027, 0x7535, 0x5B50), '"flexible electronics"'),
    (_cjk(0x67D4, 0x6027, 0x4F20, 0x611F, 0x5668), '"flexible sensor"'),
    (_cjk(0x7535, 0x5B50, 0x76AE, 0x80A4), '"electronic skin"'),
    (_cjk(0x53EF, 0x7A7F, 0x6234), "wearable"),
    (_cjk(0x4F20, 0x611F, 0x5668), "sensor"),
    (_cjk(0x663E, 0x793A, 0x5668, 0x4EF6), "display device"),
    (_cjk(0x663E, 0x793A), "display"),
    (_cjk(0x6267, 0x884C, 0x5668), "actuator"),
    (_cjk(0x4EBA, 0x673A, 0x754C, 0x9762), '"human machine interface"'),
    (_cjk(0x751F, 0x7269, 0x7535, 0x5B50), "bioelectronics"),
    (_cjk(0x667A, 0x80FD, 0x7EBA, 0x7EC7), '"smart textile"'),
    (_cjk(0x6750, 0x6599), "materials"),
    (_cjk(0x5668, 0x4EF6), "device"),
    (_cjk(0x7CFB, 0x7EDF, 0x5E94, 0x7528), '"system application"'),
    (_cjk(0x7CFB, 0x7EDF), "system"),
    (_cjk(0x5E94, 0x7528), "application"),
)

_OPENALEX_QUERY_NOISE = {
    _cjk(0x8FD1, 0x4E09, 0x5E74),
    _cjk(0x6700, 0x8FD1, 0x4E09, 0x5E74),
    _cjk(0x8FD1, 0x5E74, 0x6765),
    _cjk(0x6700, 0x65B0),
    _cjk(0x5173, 0x952E, 0x8FDB, 0x5C55),
    _cjk(0x8FDB, 0x5C55),
    _cjk(0x6709, 0x54EA, 0x4E9B),
    _cjk(0x4EC0, 0x4E48),
    _cjk(0x8BF7, 0x4F18, 0x5148, 0x68C0, 0x7D22),
    _cjk(0x4F18, 0x5148, 0x68C0, 0x7D22),
    _cjk(0x8BBA, 0x6587),
    _cjk(0x7ED3, 0x679C),
    _cjk(0x8FD4, 0x56DE),
}
_ENGLISH_TERM = re.compile(r"[a-z][a-z0-9-]{2,}", re.IGNORECASE)
_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "between",
    "by",
    "for",
    "from",
    "in",
    "key",
    "major",
    "of",
    "on",
    "or",
    "progress",
    "representative",
    "the",
    "to",
    "what",
    "which",
    "year",
    "years",
}
_SOURCE_TERMS = {"conference", "workshop", "symposium"}


class OpenAlexQueryAdapter:
    """Translate common Chinese research phrasing into OpenAlex keywords.

    OpenAlex's ``search`` field is a scholarly keyword search, not a general
    Chinese question-answer endpoint. This adapter keeps the original query
    for auditability while sending a concise provider-ready query and applying
    a small deterministic relevance pass to the returned metadata.
    """

    provider_name = "openalex"

    def build_query(self, context: ProviderSearchContext) -> ProviderQuery:
        raw = " ".join((context.normalized_query or context.query).split())
        mapped: list[str] = []
        remaining = raw
        for source, target in _OPENALEX_ALIASES:
            if source in remaining:
                mapped.append(target)
                remaining = remaining.replace(source, " ")
        remaining = " ".join(
            token for token in remaining.split() if token not in _OPENALEX_QUERY_NOISE
        )
        english = [
            token
            for token in _ENGLISH_TERM.findall(remaining)
            if token.casefold() not in _QUERY_STOPWORDS
            and (
                token.casefold() not in _SOURCE_TERMS
                or any(
                    source_term in context.query.casefold()
                    for source_term in _SOURCE_TERMS
                )
            )
        ]
        if mapped:
            text = " ".join(dict.fromkeys(mapped + english[:8]))
        else:
            text = remaining if not _contains_cjk(remaining) else ""
        if not text:
            text = (
                "flexible electronics"
                if _cjk(0x67D4, 0x6027) in raw
                else "research"
            )
        terms = tuple(dict.fromkeys(_ENGLISH_TERM.findall(text.casefold())))
        return ProviderQuery(text=" ".join(text.split()), terms=terms)

    def score(
        self,
        item: ExternalEvidenceItem,
        query: ProviderQuery,
        *,
        rank: int,
        prefer_high_citation: bool,
    ) -> float:
        searchable = f"{item.title} {item.content_excerpt}".casefold()
        matched = sum(1 for term in query.terms if term in searchable)
        coverage = matched / max(len(query.terms), 1)
        recency = _recency_score(item.published_at)
        citation = min(1.0, (item.citation_count or 0) / 250)
        rank_score = max(0.0, 1.0 - rank / 50)
        score = 0.55 * coverage + 0.2 * recency + 0.15 * rank_score
        score += 0.1 * citation if prefer_high_citation else 0.05 * citation
        return max(0.0, min(1.0, score))


class CrossrefQueryAdapter:
    """Crossref bibliographic query adapter with local relevance scoring."""

    provider_name = "crossref"

    def __init__(self) -> None:
        self._delegate = OpenAlexQueryAdapter()

    def build_query(self, context: ProviderSearchContext) -> ProviderQuery:
        return self._delegate.build_query(context)

    def score(
        self,
        item: ExternalEvidenceItem,
        query: ProviderQuery,
        *,
        rank: int,
        prefer_high_citation: bool,
    ) -> float:
        return self._delegate.score(
            item,
            query,
            rank=rank,
            prefer_high_citation=prefer_high_citation,
        )


class ArxivQueryAdapter:
    """Build conservative arXiv boolean queries from provider-neutral terms."""

    provider_name = "arxiv"

    def __init__(self) -> None:
        self._delegate = OpenAlexQueryAdapter()

    def build_query(self, context: ProviderSearchContext) -> ProviderQuery:
        query = self._delegate.build_query(context)
        terms = tuple(term for term in query.terms if term)
        if terms:
            return ProviderQuery(
                text=" AND ".join(f"all:{term}" for term in terms[:6]),
                terms=terms,
            )
        return query

    def score(
        self,
        item: ExternalEvidenceItem,
        query: ProviderQuery,
        *,
        rank: int,
        prefer_high_citation: bool,
    ) -> float:
        return self._delegate.score(
            item,
            query,
            rank=rank,
            prefer_high_citation=prefer_high_citation,
        )


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= character <= "\u9fff" for character in value)


def _recency_score(published_at: datetime | None) -> float:
    if published_at is None:
        return 0.0
    current = datetime.now(UTC)
    age_days = max(0.0, (current - published_at.astimezone(UTC)).days)
    return max(0.0, 1.0 - age_days / 3650)
