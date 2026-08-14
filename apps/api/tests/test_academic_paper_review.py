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


@pytest.mark.asyncio
async def test_frontier_review_keeps_candidates_on_model_failure(
) -> None:
    class FailingHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("model unavailable")

    result = ExternalRetrievalResult(
        query="2024-2026 generative AI multimodal agents",
        normalized_query="generative ai multimodal agents",
        items=[evidence_item("paper-1", "Generative AI and multimodal agents")],
    )
    reviewed = await AcademicPaperReviewService(
        cast(Any, FailingHub()), Settings(_env_file=None)
    ).review(
        "2024-2026 generative AI multimodal agents",
        result,
        allow_degraded=True,
    )

    assert [item.evidence_id for item in reviewed.items] == ["paper-1"]
    assert reviewed.status == "partial"
    assert reviewed.review_status == "failed"
    assert reviewed.approved_count == 1
    assert "manual verification" in reviewed.warnings[-1]


@pytest.mark.asyncio
async def test_frontier_review_degrades_when_model_rejects_scoped_candidates() -> None:
    class RejectingHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                structured_result={
                    "decisions": [
                        {
                            "evidence_id": "paper-1",
                            "approved": False,
                            "confidence": 0.9,
                            "reason": "needs manual verification",
                        }
                    ]
                }
            )

    relevant = evidence_item(
        "paper-1", "Generative AI multimodal agent systems"
    ).model_copy(
        update={
            "content_excerpt": (
                "This paper studies generative AI, multimodal models, and "
                "agentic tool use."
            ),
            "published_at": datetime(2025, 1, 1, tzinfo=UTC),
        }
    )
    old = relevant.model_copy(
        update={
            "evidence_id": "old-paper",
            "published_at": datetime(2022, 1, 1, tzinfo=UTC),
        }
    )
    result = ExternalRetrievalResult(
        query="2024-2026 generative AI multimodal agents",
        normalized_query="generative ai multimodal agents",
        items=[relevant, old],
    )

    reviewed = await AcademicPaperReviewService(
        cast(Any, RejectingHub()), Settings(_env_file=None)
    ).review(
        "2024-2026 generative AI multimodal agents",
        result,
        allow_degraded=True,
    )

    assert [item.evidence_id for item in reviewed.items] == ["paper-1"]
    assert reviewed.status == "partial"
    assert reviewed.review_status == "failed"
    assert "outside requested year range" in " ".join(reviewed.warnings)
    assert "manual verification" in reviewed.warnings[-1]


@pytest.mark.asyncio
async def test_frontier_review_preserves_valid_non_academic_sources() -> None:
    class FakeHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                structured_result={
                    "decisions": [
                        {
                            "evidence_id": "paper-1",
                            "approved": True,
                            "confidence": 0.95,
                            "reason": "relevant",
                        }
                    ]
                }
            )

    report = evidence_item(
        "report-1", "Flexible electronics device industry report"
    )
    report = report.model_copy(
        update={
            "source_type": ExternalSourceType.WEB_PAGE,
            "provider": "news_rss",
            "source_ref": "external://news/report-1",
            "metadata": {"category": "web_report"},
        }
    )
    result = ExternalRetrievalResult(
        query="flexible electronics progress",
        normalized_query="flexible electronics progress",
        items=[
            evidence_item("paper-1", "Flexible electronics device relevant paper"),
            report,
        ],
    )
    reviewed = await AcademicPaperReviewService(
        cast(Any, FakeHub()), Settings(_env_file=None)
    ).review("flexible electronics progress", result, allow_non_academic=True)

    assert [item.evidence_id for item in reviewed.items] == ["report-1", "paper-1"]
    assert reviewed.approved_count == 2


@pytest.mark.asyncio
async def test_recent_search_rejects_undated_and_old_candidates() -> None:
    class FakeHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                structured_result={
                    "decisions": [
                        {
                            "evidence_id": "recent-paper",
                            "approved": True,
                            "confidence": 0.95,
                            "reason": "relevant and dated",
                        }
                    ]
                }
            )

    recent = evidence_item("recent-paper", "Artificial Intelligence Systems")
    missing_date = recent.model_copy(
        update={"evidence_id": "missing-date", "published_at": None}
    )
    old = recent.model_copy(
        update={
            "evidence_id": "old-paper",
            "published_at": datetime(2018, 1, 1, tzinfo=UTC),
        }
    )
    result = ExternalRetrievalResult(
        query="recent artificial intelligence papers",
        normalized_query="recent artificial intelligence",
        items=[recent, missing_date, old],
    )

    reviewed = await AcademicPaperReviewService(
        cast(Any, FakeHub()), Settings(_env_file=None)
    ).review("recent artificial intelligence papers", result)

    assert [item.evidence_id for item in reviewed.items] == ["recent-paper"]
    assert "missing-date: rejected missing publication date" in reviewed.warnings
    assert "old-paper: rejected outside relative date window" in reviewed.warnings


@pytest.mark.asyncio
async def test_frontier_review_rejects_off_topic_non_academic_sources() -> None:
    class FakeHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                structured_result={
                    "decisions": [
                        {
                            "evidence_id": "paper-1",
                            "approved": True,
                            "confidence": 0.95,
                            "reason": "relevant flexible electronic device paper",
                        }
                    ]
                }
            )

    blood_bag_report = evidence_item("report-1", "Global blood bag industry report")
    blood_bag_report = blood_bag_report.model_copy(
        update={
            "source_type": ExternalSourceType.WEB_PAGE,
            "provider": "news_rss",
            "source_ref": "external://news/report-1",
            "metadata": {"category": "web_report"},
            "content_excerpt": "Blood bag manufacturing and market trends.",
        }
    )
    relevant_paper = evidence_item(
        "paper-1", "Flexible electronic device sensor progress"
    ).model_copy(
        update={
            "content_excerpt": (
                "This paper studies flexible electronic devices and "
                "stretchable sensors."
            )
        }
    )
    result = ExternalRetrievalResult(
        query="近三年柔性电子器件的关键进展是什么？",
        normalized_query="flexible electronics devices recent progress",
        items=[blood_bag_report, relevant_paper],
    )
    reviewed = await AcademicPaperReviewService(
        cast(Any, FakeHub()), Settings(_env_file=None)
    ).review(
        "近三年柔性电子器件的关键进展是什么？",
        result,
        allow_non_academic=True,
    )

    assert [item.evidence_id for item in reviewed.items] == ["paper-1"]
    assert "report-1: rejected topic mismatch" in reviewed.warnings
