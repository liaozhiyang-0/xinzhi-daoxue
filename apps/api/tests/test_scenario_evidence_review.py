from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.contracts.external_retrieval import (
    ExternalEvidenceItem,
    ExternalRetrievalResult,
    ExternalSourceType,
)
from app.contracts.scenarios import (
    ScenarioEvidenceReviewRequest,
    ScenarioEvidenceSource,
)
from app.services.scenario_catalog import ScenarioCatalog
from app.services.scenario_evidence_review import ScenarioEvidenceReviewService

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_authoritative_cited_source_requires_manual_review() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    scenario = catalog.get("research_frontier_radar_v1")
    request = ScenarioEvidenceReviewRequest(
        sources=[
            ScenarioEvidenceSource(
                source_type="academic_paper",
                source_ref="doi:10.1234/example",
                cited=True,
                published_at=datetime.now(UTC) - timedelta(days=30),
            )
        ]
    )

    result = ScenarioEvidenceReviewService().review(scenario, request)

    assert result.status == "needs_manual_review"
    assert result.accepted_source_refs == ["doi:10.1234/example"]
    assert result.cited_count == 1


def test_unknown_or_uncited_sources_are_rejected() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    scenario = catalog.get("faculty_course_copilot_v1")
    request = ScenarioEvidenceReviewRequest(
        sources=[
            ScenarioEvidenceSource(
                source_type="unknown_source",
                source_ref="unknown:1",
            ),
            ScenarioEvidenceSource(
                source_type="course_asset_manifest",
                source_ref="kb://CT/course.md",
            ),
        ]
    )

    result = ScenarioEvidenceReviewService().review(scenario, request)

    assert result.status == "rejected"
    assert result.rejected_source_refs == ["unknown:1"]
    assert "accepted_sources_without_citations" in result.warnings


def test_external_result_adapter_preserves_citations_and_provenance() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    scenario = catalog.get("research_frontier_radar_v1")
    item = ExternalEvidenceItem(
        evidence_id="paper-1",
        source_type=ExternalSourceType.ACADEMIC_PAPER,
        provider="test",
        source_ref="doi:10.1234/example",
        title="A reviewed paper",
        canonical_url="https://doi.org/10.1234/example",
        retrieved_at=datetime.now(UTC),
        published_at=datetime.now(UTC) - timedelta(days=30),
    )
    retrieval = ExternalRetrievalResult(
        query="grounded research",
        normalized_query="grounded research",
        items=[item],
    )

    result = ScenarioEvidenceReviewService().review_external_result(
        scenario_id=scenario.id,
        policy=scenario.evidence_policy,
        result=retrieval,
        cited_evidence_ids={"paper-1"},
    )

    assert result.status == "needs_manual_review"
    assert result.accepted_source_refs == ["doi:10.1234/example"]
    assert result.cited_count == 1


def test_generic_external_reference_policy_accepts_known_provider_types() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    scenario = catalog.get("faculty_course_copilot_v1")
    item = ExternalEvidenceItem(
        evidence_id="web-1",
        source_type=ExternalSourceType.WEB_PAGE,
        provider="test",
        source_ref="https://example.org/teaching",
        title="Teaching reference",
        canonical_url="https://example.org/teaching",
        retrieved_at=datetime.now(UTC),
    )
    retrieval = ExternalRetrievalResult(
        query="teaching reference",
        normalized_query="teaching reference",
        items=[item],
    )

    result = ScenarioEvidenceReviewService().review_external_result(
        scenario_id=scenario.id,
        policy=scenario.evidence_policy,
        result=retrieval,
        cited_evidence_ids={"web-1"},
    )

    assert result.status == "needs_manual_review"
    assert result.accepted_source_refs == ["https://example.org/teaching"]
    assert (
        "supplemental_source_requires_review:https://example.org/teaching"
        in result.warnings
    )
