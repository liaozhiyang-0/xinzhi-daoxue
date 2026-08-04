from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

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
    ) -> None:
        super().__init__(
            base_url=base_url,
            client=client,
            timeout_seconds=timeout_seconds,
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
