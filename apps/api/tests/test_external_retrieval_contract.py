from datetime import UTC, datetime

import pytest
from app.contracts import (
    ExternalEvidenceItem,
    ExternalRetrievalPolicy,
    ExternalRetrievalResult,
    ExternalSourceScope,
    ExternalSourceType,
)
from pydantic import ValidationError


def evidence(**updates: object) -> ExternalEvidenceItem:
    payload: dict[str, object] = {
        "evidence_id": "E1",
        "source_type": ExternalSourceType.ACADEMIC_PAPER,
        "provider": "crossref",
        "source_ref": "external://crossref/10.1234/example",
        "title": "A bounded paper result",
        "canonical_url": "https://doi.org/10.1234/example",
        "content_excerpt": "A short abstract excerpt.",
        "retrieved_at": datetime.now(UTC),
        "doi": "10.1234/example",
    }
    payload.update(updates)
    return ExternalEvidenceItem.model_validate(payload)


def test_external_evidence_preserves_paper_provenance() -> None:
    item = evidence(authors=[" Alice ", "Alice"], venue="Test Journal")

    assert item.source_type == ExternalSourceType.ACADEMIC_PAPER
    assert item.authors == ["Alice"]
    assert item.canonical_url.scheme == "https"
    assert item.retrieved_at.tzinfo is not None


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/paper.pdf",
        "https://user:password@example.com/paper",
        "http://127.0.0.1:8000/admin",
    ],
)
def test_external_evidence_rejects_unsafe_url_shapes(url: str) -> None:
    with pytest.raises(ValidationError):
        evidence(canonical_url=url)


def test_external_policy_is_bounded_and_deduplicated() -> None:
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC, ExternalSourceScope.ACADEMIC],
        providers=[" CrossRef ", "crossref"],
        max_iterations=2,
        max_fetches=4,
    )

    assert policy.source_scopes == [ExternalSourceScope.ACADEMIC]
    assert policy.providers == ["crossref"]


def test_external_result_accepts_partial_provider_failure() -> None:
    result = ExternalRetrievalResult(
        query="latest signal processing papers",
        normalized_query="latest signal processing papers",
        source_scopes=[ExternalSourceScope.ACADEMIC],
        items=[evidence()],
        status="partial",
        provider_status={"arxiv": "timeout", "crossref": "completed"},
        warnings=["arxiv timed out"],
    )

    assert result.status == "partial"
    assert result.provider_status["arxiv"] == "timeout"
