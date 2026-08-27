from __future__ import annotations

import ipaddress
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class ExternalSourceType(StrEnum):
    """Externally retrieved source categories.

    Local course knowledge remains represented by ``KnowledgeHit``. Keeping the
    two contracts separate prevents an external URL from being treated as a
    course-scoped ``kb://`` citation before its provenance is validated.
    """

    ACADEMIC_PAPER = "academic_paper"
    WEB_PAGE = "web_page"
    USER_SOURCE = "user_source"


class ExternalSourceScope(StrEnum):
    ACADEMIC = "academic"
    WEB = "web"
    USER = "user"


class ExternalEvidenceSupport(StrEnum):
    RETRIEVED = "retrieved"
    POTENTIALLY_RELEVANT = "potentially_relevant"
    SUPPORTS_CLAIM = "supports_claim"
    CONFLICTS = "conflicts"
    UNKNOWN = "unknown"


class ExternalRetrievalPolicy(BaseModel):
    """Declarative limits for a future external retrieval execution plan."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    source_scopes: list[ExternalSourceScope] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list, max_length=16)
    max_results: int = Field(default=8, ge=1, le=50)
    max_fetches: int = Field(default=4, ge=0, le=20)
    max_iterations: int = Field(default=2, ge=1, le=3)
    freshness_days: int | None = Field(default=None, ge=1, le=3650)
    allow_full_text: bool = False
    require_citations: bool = True
    generation_injection: bool = False
    timeout_seconds: float = Field(default=90, gt=0, le=180)
    intent_gate_mode: Literal["signals_or_intent", "signals_only", "always"] = (
        "signals_or_intent"
    )
    intent_allowlist: list[str] = Field(default_factory=list, max_length=16)
    intent_score_threshold: int = Field(default=2, ge=1, le=10)

    @field_validator("providers")
    @classmethod
    def normalize_providers(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().casefold() for value in values if value.strip()]
        return list(dict.fromkeys(normalized))

    @field_validator("intent_allowlist")
    @classmethod
    def normalize_intent_allowlist(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().casefold() for value in values if value.strip()]
        return list(dict.fromkeys(normalized))

    @field_validator("source_scopes")
    @classmethod
    def deduplicate_scopes(
        cls, values: list[ExternalSourceScope]
    ) -> list[ExternalSourceScope]:
        return list(dict.fromkeys(values))


class ExternalEvidenceItem(BaseModel):
    """A bounded, provenance-preserving external evidence item.

    This is metadata/excerpt evidence, not a license to copy an entire source.
    Full-text retrieval and copyright decisions belong to a later Provider.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=64)
    source_type: ExternalSourceType
    provider: str = Field(min_length=1, max_length=64)
    source_ref: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=1000)
    canonical_url: AnyHttpUrl
    content_excerpt: str = Field(default="", max_length=12_000)
    authors: list[str] = Field(default_factory=list, max_length=64)
    venue: str = Field(default="", max_length=500)
    published_at: datetime | None = None
    updated_at: datetime | None = None
    retrieved_at: datetime
    doi: str = Field(default="", max_length=256)
    arxiv_id: str = Field(default="", max_length=128)
    citation_count: int | None = Field(default=None, ge=0)
    locator: str = Field(default="", max_length=500)
    license_or_access: str = Field(default="", max_length=500)
    content_hash: str = Field(default="", max_length=128)
    relevance_score: float = Field(default=0, ge=0, le=1)
    trust_level: Literal["high", "medium", "low", "unknown"] = "unknown"
    support_level: ExternalEvidenceSupport = ExternalEvidenceSupport.UNKNOWN
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider", "source_ref", "title", "content_excerpt")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        has_control_character = any(
            ord(character) < 32 and character not in "\n\r\t" for character in value
        )
        if has_control_character:
            raise ValueError("external evidence text contains control characters")
        return value.strip() if value != value.strip() else value

    @field_validator("canonical_url")
    @classmethod
    def require_public_http_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme not in {"http", "https"}:
            raise ValueError("external evidence URL must use http or https")
        if value.username or value.password:
            raise ValueError("external evidence URL must not contain credentials")
        hostname = (value.host or "").casefold()
        if hostname == "localhost":
            raise ValueError("external evidence URL must not target localhost")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
        ):
            raise ValueError("external evidence URL must target a public address")
        return value

    @field_validator("retrieved_at", "published_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("external evidence timestamps must include a timezone")
        return value.astimezone(UTC) if value is not None else None

    @field_validator("authors")
    @classmethod
    def normalize_authors(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values if value.strip()]
        return list(dict.fromkeys(normalized))


class ExternalRetrievalResult(BaseModel):
    """Provider-neutral result for future external retrieval orchestration."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    normalized_query: str = Field(min_length=1, max_length=2000)
    source_scopes: list[ExternalSourceScope] = Field(default_factory=list)
    items: list[ExternalEvidenceItem] = Field(default_factory=list, max_length=50)
    status: Literal["disabled", "completed", "partial", "failed"] = "completed"
    warnings: list[str] = Field(default_factory=list, max_length=20)
    provider_status: dict[str, str] = Field(default_factory=dict)
    latency_ms: int = Field(default=0, ge=0)
    retrieval_trace_id: str = Field(default="", max_length=128)
    cache_hit: bool = False
    review_status: Literal["not_run", "approved", "rejected", "failed"] = "not_run"
    reviewed_count: int = Field(default=0, ge=0)
    approved_count: int = Field(default=0, ge=0)
    search_queries: list[str] = Field(default_factory=list, max_length=6)
    search_round: int = Field(default=1, ge=1, le=5)

    @field_validator("source_scopes")
    @classmethod
    def deduplicate_result_scopes(
        cls, values: list[ExternalSourceScope]
    ) -> list[ExternalSourceScope]:
        return list(dict.fromkeys(values))


class ExternalRetrievalIntentDecision(BaseModel):
    """Auditable decision explaining whether a request may contact the web."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["retrieve", "skip"]
    category: Literal[
        "explicit_request",
        "freshness",
        "research",
        "citation",
        "current_facts",
        "agent_intent",
        "none",
    ] = "none"
    score: int = Field(default=0, ge=0, le=20)
    threshold: int = Field(default=2, ge=1, le=10)
    reason_codes: list[str] = Field(default_factory=list, max_length=8)
    matched_signals: list[str] = Field(default_factory=list, max_length=8)
