from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.agents.internal.contracts import AcademicPaperReview
from app.agents.internal.hub import InternalAgentHub
from app.contracts.external_retrieval import (
    ExternalEvidenceItem,
    ExternalRetrievalResult,
)
from app.core.config import Settings


class AcademicPaperReviewService:
    """Require one model review pass before external papers reach the UI."""

    agent_id = "ACADEMIC_PAPER_REVIEW_LOCAL_V1"

    def __init__(self, hub: InternalAgentHub, settings: Settings) -> None:
        self.hub = hub
        self.settings = settings

    async def review(
        self,
        query: str,
        result: ExternalRetrievalResult,
        *,
        request_id: str = "",
        required_concepts: Sequence[str] = (),
        excluded_concepts: Sequence[str] = (),
    ) -> ExternalRetrievalResult:
        if not result.items:
            return result.model_copy(update={"review_status": "not_run"})
        if not self.settings.external_retrieval_review_enabled:
            return result.model_copy(
                update={
                    "items": [],
                    "status": "failed",
                    "review_status": "failed",
                    "reviewed_count": 0,
                    "approved_count": 0,
                    "warnings": [
                        *result.warnings,
                        "paper review disabled; no external papers were displayed",
                    ],
                }
            )

        now = datetime.now(UTC)
        candidates: list[ExternalEvidenceItem] = []
        warnings = list(result.warnings)
        for item in result.items:
            item_date = item.updated_at or item.published_at
            if item_date is not None and item_date > now + timedelta(days=1):
                warnings.append(f"{item.evidence_id}: rejected future publication date")
                continue
            if not item.content_excerpt.strip():
                warnings.append(f"{item.evidence_id}: rejected missing abstract")
                continue
            candidates.append(item)
        if not candidates:
            return result.model_copy(
                update={
                    "items": [],
                    "status": "failed",
                    "review_status": "rejected",
                    "reviewed_count": 0,
                    "approved_count": 0,
                    "warnings": warnings[:20],
                }
            )

        payload = {
            "user_query": query,
            "as_of_date": now.date().isoformat(),
            "citation_instruction": (
                "Use citation_count as a ranking preference when present; missing "
                "citation_count must not by itself reject a relevant paper."
            ),
            "scope_instruction": (
                "The paper must materially address the requested concepts. Do not "
                "approve a generic AI or generic healthcare paper when a narrower "
                "domain such as medical imaging is requested."
                if required_concepts
                else (
                    "The request has no narrower required concepts; judge the "
                    "broad topic."
                )
            ),
            "required_concepts": list(required_concepts),
            "excluded_concepts": list(excluded_concepts),
            "candidates": [
                {
                    "evidence_id": item.evidence_id,
                    "title": item.title,
                    "abstract": item.content_excerpt[:3000],
                    "source": item.provider,
                    "venue": item.venue,
                    "citation_count": item.citation_count,
                    "published_at": _isoformat_datetime(
                        item.updated_at or item.published_at
                    ),
                }
                for item in candidates
            ],
        }
        try:
            async with asyncio.timeout(
                self.settings.external_retrieval_review_timeout_seconds
            ):
                review_result = await self.hub.run_text(
                    self.agent_id,
                    input_text=json.dumps(payload, ensure_ascii=False),
                    request_id=request_id or None,
                    max_tokens=self.settings.external_retrieval_review_max_tokens,
                    extra_options={"_allow_route_fallback": False},
                )
            review = AcademicPaperReview.model_validate(review_result.structured_result)
        except TimeoutError:
            return self._failed(result, warnings, "paper review timed out")
        except Exception:
            return self._failed(result, warnings, "paper review unavailable")

        candidate_ids = {item.evidence_id for item in candidates}
        decisions = {
            decision.evidence_id: decision
            for decision in review.decisions
            if decision.evidence_id in candidate_ids
        }
        approved = [
            item
            for item in candidates
            if (
                decision := decisions.get(item.evidence_id)
            ) is not None
            and decision.approved
            and decision.confidence >= 0.65
        ]
        if len(decisions) != len(candidates):
            warnings.append(
                "paper review did not cover every candidate; uncovered items removed"
            )
        warnings.extend(
            f"{decision.evidence_id}: {decision.reason}"
            for decision in decisions.values()
            if not decision.approved or decision.confidence < 0.65
        )
        if not approved:
            warnings.append("paper review rejected all candidates")
        return result.model_copy(
            update={
                "items": approved,
                "status": "completed" if approved else "failed",
                "review_status": "approved" if approved else "rejected",
                "reviewed_count": len(decisions),
                "approved_count": len(approved),
                "warnings": warnings[:20],
            }
        )

    @staticmethod
    def _failed(
        result: ExternalRetrievalResult,
        warnings: list[str],
        message: str,
    ) -> ExternalRetrievalResult:
        return result.model_copy(
            update={
                "items": [],
                "status": "failed",
                "review_status": "failed",
                "reviewed_count": 0,
                "approved_count": 0,
                "warnings": [*warnings, message][:20],
            }
        )


def _isoformat_datetime(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""
