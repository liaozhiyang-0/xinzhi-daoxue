from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.contracts.external_retrieval import ExternalRetrievalResult
from app.contracts.scenarios import (
    KnowledgeEvidencePolicy,
    ScenarioDefinition,
    ScenarioEvidenceReviewRequest,
    ScenarioEvidenceReviewResponse,
    ScenarioEvidenceSource,
)


class ScenarioEvidenceReviewService:
    """Apply a scenario's source and citation policy without contacting providers."""

    _EXTERNAL_SOURCE_TYPES = frozenset(
        {"academic_paper", "web_page", "user_source"}
    )

    def review(
        self,
        scenario: ScenarioDefinition,
        request: ScenarioEvidenceReviewRequest,
        *,
        now: datetime | None = None,
    ) -> ScenarioEvidenceReviewResponse:
        return self._review(
            scenario.id,
            scenario.evidence_policy,
            request,
            now=now,
        )

    def review_external_result(
        self,
        *,
        scenario_id: str,
        policy: KnowledgeEvidencePolicy,
        result: ExternalRetrievalResult,
        cited_evidence_ids: Collection[str] = (),
        now: datetime | None = None,
    ) -> ScenarioEvidenceReviewResponse:
        """Review provider-neutral external evidence against a bound scenario.

        External retrieval providers do not know the product scenario policy.
        This adapter converts their provenance-preserving result into the same
        review contract used by the API endpoint, keeping citation and manual
        review decisions in one place.
        """

        cited = set(cited_evidence_ids)
        request = ScenarioEvidenceReviewRequest(
            sources=[
                ScenarioEvidenceSource(
                    source_type=item.source_type.value,
                    source_ref=item.source_ref,
                    cited=item.evidence_id in cited,
                    synthetic=item.metadata.get("synthetic") is True,
                    published_at=item.published_at,
                )
                for item in result.items
            ]
        )
        return self._review(scenario_id, policy, request, now=now)

    @classmethod
    def _review(
        cls,
        scenario_id: str,
        policy: KnowledgeEvidencePolicy,
        request: ScenarioEvidenceReviewRequest,
        *,
        now: datetime | None = None,
    ) -> ScenarioEvidenceReviewResponse:
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
            policy_source_type = cls._policy_source_type(source.source_type, policy)
            if policy_source_type is None:
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
            if policy_source_type in policy.supplemental_source_types:
                warnings.append(f"supplemental_source_requires_review:{source.source_ref}")

        if policy.citation_required and not accepted:
            warnings.append("no_accepted_sources")
            status: Literal["approved", "needs_manual_review", "rejected"] = (
                "rejected"
            )
        elif policy.citation_required and cited_count == 0:
            warnings.append("accepted_sources_without_citations")
            status = "rejected"
        elif rejected:
            status = "rejected"
        elif policy.manual_review_required:
            status = "needs_manual_review"
        else:
            status = "approved"
        return ScenarioEvidenceReviewResponse(
            scenario_id=scenario_id,
            status=status,
            checked_count=len(request.sources),
            cited_count=cited_count,
            accepted_source_refs=accepted,
            rejected_source_refs=rejected,
            warnings=warnings,
        )

    @classmethod
    def _policy_source_type(
        cls, source_type: str, policy: KnowledgeEvidencePolicy
    ) -> str | None:
        allowed = set(policy.authoritative_source_types) | set(
            policy.supplemental_source_types
        )
        if source_type in allowed:
            return source_type
        if (
            source_type in cls._EXTERNAL_SOURCE_TYPES
            and "external_reference" in policy.supplemental_source_types
        ):
            return "external_reference"
        return None
