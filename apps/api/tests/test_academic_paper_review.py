from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from app.contracts import (
    ExternalEvidenceItem,
    ExternalRetrievalResult,
    ExternalSourceType,
)
from app.core.config import Settings
from app.services.academic_paper_review import AcademicPaperReviewService


def evidence_item(evidence_id: str, title: str) -> ExternalEvidenceItem:
    return ExternalEvidenceItem(
        evidence_id=evidence_id,
        source_type=ExternalSourceType.ACADEMIC_PAPER,
        provider="openalex",
        source_ref=f"external://openalex/{evidence_id}",
        title=title,
        canonical_url=f"https://example.org/{evidence_id}",
        content_excerpt=(
            "This abstract discusses artificial intelligence and machine learning."
        ),
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        retrieved_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_paper_review_only_keeps_model_approved_candidates() -> None:
    class FakeHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                structured_result={
                    "decisions": [
                        {
                            "evidence_id": "paper-1",
                            "approved": True,
                            "confidence": 0.95,
                            "reason": "主题和摘要都匹配人工智能",
                        },
                        {
                            "evidence_id": "paper-2",
                            "approved": False,
                            "confidence": 0.98,
                            "reason": "与主题无关",
                        },
                    ]
                }
            )

    result = ExternalRetrievalResult(
        query="最新人工智能论文",
        normalized_query="artificial intelligence",
        items=[
            evidence_item("paper-1", "Artificial Intelligence Systems"),
            evidence_item("paper-2", "A History of Medieval Trade"),
        ],
    )
    reviewed = await AcademicPaperReviewService(
        cast(Any, FakeHub()), Settings(_env_file=None)
    ).review("最新人工智能论文", result)

    assert [item.evidence_id for item in reviewed.items] == ["paper-1"]
    assert reviewed.review_status == "approved"
    assert reviewed.reviewed_count == 2
    assert reviewed.approved_count == 1


@pytest.mark.asyncio
async def test_paper_review_fails_closed_when_model_is_unavailable() -> None:
    class FailingHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("model unavailable")

    result = ExternalRetrievalResult(
        query="latest AI papers",
        normalized_query="artificial intelligence",
        items=[evidence_item("paper-1", "Artificial Intelligence Systems")],
    )
    reviewed = await AcademicPaperReviewService(
        cast(Any, FailingHub()), Settings(_env_file=None)
    ).review("latest AI papers", result)

    assert reviewed.items == []
    assert reviewed.review_status == "failed"
    assert "paper review unavailable" in reviewed.warnings
