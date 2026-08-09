from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.agents.internal.contracts import AcademicPaperReview
from app.agents.internal.hub import InternalAgentHub
from app.contracts.external_retrieval import (
    ExternalEvidenceItem,
    ExternalRetrievalResult,
)
from app.core.config import Settings

_FLEXIBLE_ELECTRONICS_SCOPE_TERMS = (
    "柔性电子",
    "柔性电子器件",
    "柔性器件",
    "可拉伸电子",
    "可穿戴电子",
    "电子皮肤",
    "flexible electronics",
    "flexible electronic device",
    "flexible electronic devices",
    "stretchable electronics",
    "wearable electronics",
    "electronic skin",
    "printed electronics",
    "organic electronics",
    "flexible sensor",
    "flexible sensors",
)

_FLEXIBLE_ELECTRONICS_TECHNICAL_TERMS = (
    "器件",
    "传感器",
    "传感系统",
    "电路",
    "晶体管",
    "显示",
    "电池",
    "能源",
    "生物电子",
    "可拉伸",
    "导电",
    "薄膜",
    "柔性基底",
    "柔性材料",
    "device",
    "sensor",
    "circuit",
    "transistor",
    "display",
    "battery",
    "bioelectronics",
    "stretchable",
    "conductive",
    "thin film",
    "substrate",
)

_FLEXIBLE_ELECTRONICS_DEVICE_TERMS = (
    "器件",
    "传感器",
    "电路",
    "晶体管",
    "显示器",
    "电池",
    "电子皮肤",
    "device",
    "sensor",
    "circuit",
    "transistor",
    "display",
    "battery",
    "electronic skin",
)

_AI_SCOPE_TERMS = (
    "\u4eba\u5de5\u667a\u80fd",
    "\u751f\u6210\u5f0f\u4eba\u5de5\u667a\u80fd",
    "\u673a\u5668\u5b66\u4e60",
    "\u6df1\u5ea6\u5b66\u4e60",
    "\u5927\u6a21\u578b",
    "artificial intelligence",
    "generative ai",
    "machine learning",
    "deep learning",
    "large language model",
    "llm",
)
_MULTIMODAL_SCOPE_TERMS = (
    "\u591a\u6a21\u6001",
    "multimodal",
    "vision-language",
    "visual language",
    "image-based",
    "computer vision",
)
_AGENT_SCOPE_TERMS = (
    "\u667a\u80fd\u4f53",
    "\u667a\u80fd\u4ee3\u7406",
    "agentic",
    "agents",
    "autonomous agent",
    "tool use",
    "planning",
)


def _matches_query_scope(
    query: str,
    item: ExternalEvidenceItem,
    required_concepts: Sequence[str],
) -> bool:
    """Reject clearly off-topic evidence before model review or UI display."""

    text = " ".join((item.title, item.content_excerpt, item.venue)).casefold()
    normalized_query = query.casefold()
    flexible_request = any(
        term in normalized_query for term in _FLEXIBLE_ELECTRONICS_SCOPE_TERMS
    )
    if flexible_request:
        has_scope_term = any(term in text for term in _FLEXIBLE_ELECTRONICS_SCOPE_TERMS)
        has_technical_term = any(
            term in text for term in _FLEXIBLE_ELECTRONICS_TECHNICAL_TERMS
        )
        device_request = any(
            term in normalized_query
            for term in ("器件", "device", "devices")
        )
        has_device_term = any(
            term in text for term in _FLEXIBLE_ELECTRONICS_DEVICE_TERMS
        )
        return has_scope_term and has_technical_term and (
            not device_request or has_device_term
        )

    if _is_ai_frontier_request(normalized_query):
        if not any(term in text for term in _AI_SCOPE_TERMS):
            return False
        requested_branches: list[Sequence[str]] = []
        if any(term in normalized_query for term in _MULTIMODAL_SCOPE_TERMS):
            requested_branches.append(_MULTIMODAL_SCOPE_TERMS)
        if any(term in normalized_query for term in _AGENT_SCOPE_TERMS):
            requested_branches.append(_AGENT_SCOPE_TERMS)
        return not requested_branches or any(
            any(term in text for term in branch) for branch in requested_branches
        )

    if required_concepts:
        return any(concept.casefold() in text for concept in required_concepts)
    return True


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
        allow_non_academic: bool = False,
        allow_degraded: bool = False,
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
        requested_year_range = _requested_year_range(query)
        for item in result.items:
            item_date = item.updated_at or item.published_at
            if item_date is not None and item_date > now + timedelta(days=1):
                warnings.append(f"{item.evidence_id}: rejected future publication date")
                continue
            if (
                requested_year_range is not None
                and item_date is not None
                and not requested_year_range[0]
                <= item_date.year
                <= requested_year_range[1]
            ):
                warnings.append(
                    f"{item.evidence_id}: rejected outside requested year range"
                )
                continue
            if not item.content_excerpt.strip():
                warnings.append(f"{item.evidence_id}: rejected missing abstract")
                continue
            if not _matches_query_scope(query, item, required_concepts):
                warnings.append(f"{item.evidence_id}: rejected topic mismatch")
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

        review_candidates = [
            item
            for item in candidates
            if not allow_non_academic or item.source_type.value == "academic_paper"
        ]
        non_academic = [
            item
            for item in candidates
            if allow_non_academic and item.source_type.value != "academic_paper"
        ]
        if not review_candidates:
            return result.model_copy(
                update={
                    "items": non_academic,
                    "status": "completed",
                    "review_status": "approved",
                    "reviewed_count": 0,
                    "approved_count": len(non_academic),
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
                for item in review_candidates
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
            if allow_degraded:
                return self._degraded(
                    result,
                    candidates,
                    warnings,
                    (
                        "paper review timed out; showing locally scoped candidates "
                        "for manual verification"
                    ),
                )
            return self._failed(result, warnings, "paper review timed out")
        except Exception:
            if allow_degraded:
                return self._degraded(
                    result,
                    candidates,
                    warnings,
                    (
                        "paper review unavailable; showing locally scoped candidates "
                        "for manual verification"
                    ),
                )
            return self._failed(result, warnings, "paper review unavailable")

        candidate_ids = {item.evidence_id for item in review_candidates}
        decisions = {
            decision.evidence_id: decision
            for decision in review.decisions
            if decision.evidence_id in candidate_ids
        }
        approved_academic = [
            item
            for item in review_candidates
            if (
                decision := decisions.get(item.evidence_id)
            ) is not None
            and decision.approved
            and decision.confidence >= 0.65
        ]
        if len(decisions) != len(review_candidates):
            warnings.append(
                "paper review did not cover every candidate; uncovered items removed"
            )
        warnings.extend(
            f"{decision.evidence_id}: {decision.reason}"
            for decision in decisions.values()
            if not decision.approved or decision.confidence < 0.65
        )
        approved = [*non_academic, *approved_academic]
        if not approved:
            if allow_degraded and candidates:
                return self._degraded(
                    result,
                    candidates,
                    warnings,
                    (
                        "paper review rejected all model decisions; showing locally "
                        "scoped candidates for manual verification"
                    ),
                )
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
    def _degraded(
        result: ExternalRetrievalResult,
        candidates: list[ExternalEvidenceItem],
        warnings: list[str],
        message: str,
    ) -> ExternalRetrievalResult:
        """Keep deterministic candidates when the optional model review fails."""

        return result.model_copy(
            update={
                "items": candidates,
                "status": "partial",
                "review_status": "failed",
                "reviewed_count": 0,
                "approved_count": len(candidates),
                "warnings": [*warnings, message][:20],
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


def _is_ai_frontier_request(query: str) -> bool:
    return (
        any(term in query for term in _AI_SCOPE_TERMS)
        and any(term in query for term in _MULTIMODAL_SCOPE_TERMS)
        and any(term in query for term in _AGENT_SCOPE_TERMS)
    )


def _requested_year_range(query: str) -> tuple[int, int] | None:
    years = sorted({int(value) for value in re.findall(r"20\d{2}", query)})
    return (years[0], years[-1]) if len(years) >= 2 else None
