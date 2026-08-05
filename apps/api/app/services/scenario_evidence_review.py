from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from app.contracts.scenarios import (
    ScenarioDefinition,
    ScenarioEvidenceReviewRequest,
    ScenarioEvidenceReviewResponse,
)


class ScenarioEvidenceReviewService:
    """Apply a scenario's source and citation policy without contacting providers."""

    def review(
        self,
        scenario: ScenarioDefinition,
        request: ScenarioEvidenceReviewRequest,
        *,
        now: datetime | None = None,
    ) -> ScenarioEvidenceReviewResponse:
        policy = scenario.evidence_policy
        allowed = set(policy.authoritative_source_types) | set(
            policy.supplemental_source_types
        )
        accepted: list[str] = []
        rejected: list[str] = []
        warnings: list[str] = []
        cited_count = 0
        current_time = now or datetime.now(UTC)
        freshness_cutoff = (
            current_time - timedelta(days=policy.freshness_days)
            if policy.freshness_days is not None
            else None
        )
        seen_refs: set[str] = set()

        for source in request.sources:
            if source.source_ref in seen_refs:
                warnings.append(f"duplicate_source_ref:{source.source_ref}")
                continue
            seen_refs.add(source.source_ref)
            rejected_reason: str | None = None
            if source.source_type not in allowed:
                rejected_reason = f"unsupported_source_type:{source.source_type}"
            elif source.synthetic and not policy.allow_synthetic:
                rejected_reason = "synthetic_source_not_allowed"
            elif (
                freshness_cutoff is not None
                and source.published_at is not None
                and (
                    source.published_at.tzinfo is None
                    or source.published_at < freshness_cutoff
                )
            ):
                rejected_reason = "source_outside_freshness_window"
            if rejected_reason is not None:
                rejected.append(source.source_ref)
                warnings.append(f"{rejected_reason}:{source.source_ref}")
                continue
            accepted.append(source.source_ref)
            cited_count += int(source.cited)
            if source.source_type in policy.supplemental_source_types:
                warnings.append(f"supplemental_source_requires_review:{source.source_ref}")

        if policy.citation_required and accepted and cited_count == 0:
            warnings.append("accepted_sources_without_citations")
            status: Literal["approved", "needs_manual_review", "rejected"] = "rejected"
        elif rejected:
            status = "rejected"
        elif policy.manual_review_required:
            status = "needs_manual_review"
        else:
            status = "approved"
        return ScenarioEvidenceReviewResponse(
            scenario_id=scenario.id,
            status=status,
            checked_count=len(request.sources),
            cited_count=cited_count,
            accepted_source_refs=accepted,
            rejected_source_refs=rejected,
            warnings=warnings,
        )
