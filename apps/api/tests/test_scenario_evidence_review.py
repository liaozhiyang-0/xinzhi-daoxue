from datetime import UTC, datetime, timedelta
from pathlib import Path

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
                source_type="external_academic",
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
