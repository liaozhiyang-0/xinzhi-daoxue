from __future__ import annotations

from pathlib import Path

import pytest
from app.contracts.research_analysis import (
    ResearchReviewItem,
    ResearchReviewSubmission,
)
from app.services.research_analysis_review import ResearchAnalysisReviewService


def _submission() -> ResearchReviewSubmission:
    return ResearchReviewSubmission(
        reviewer_id="reviewer-1",
        reviewer_role="statistician",
        items=[
            ResearchReviewItem(
                review_id="design",
                category="design",
                question="Does the design match the estimand?",
                status="accepted",
            )
        ],
        signed_off=True,
    )


def test_review_service_persists_and_reloads_signed_decision(tmp_path: Path) -> None:
    service = ResearchAnalysisReviewService()

    decision = service.persist_submission(tmp_path, "task-1", _submission())
    loaded = service.load_decision(tmp_path, "task-1")

    assert loaded == decision
    assert decision.checklist.ready_for_signoff is True
    assert decision.decision_hash
    assert (tmp_path / "task-1" / "research_review_decision.json").is_file()


def test_review_service_rejects_incomplete_signoff(tmp_path: Path) -> None:
    submission = _submission().model_copy(update={"signed_off": False})

    with pytest.raises(ValueError, match="签字前"):
        ResearchAnalysisReviewService().persist_submission(
            tmp_path, "task-1", submission
        )


def test_review_service_rejects_path_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside"):
        ResearchAnalysisReviewService().persist_submission(
            tmp_path, "..", _submission()
        )
