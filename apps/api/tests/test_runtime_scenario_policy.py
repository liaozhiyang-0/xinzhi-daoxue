from app.contracts.agent import AgentRequest
from app.contracts.external_retrieval import (
    ExternalEvidenceItem,
    ExternalRetrievalResult,
    ExternalSourceType,
)
from app.contracts.scenarios import KnowledgeEvidencePolicy
from app.services.scenario_evidence_review import ScenarioEvidenceReviewService


def test_runtime_review_uses_bound_scenario_and_cited_ids() -> None:
    request = AgentRequest(
        session_id="session-test",
        user_id="user-test",
        options={
            "scenario_id": "research_frontier_radar_v1",
            "_scenario_catalog_bound": True,
            "scenario_evidence_policy": {
                "authoritative_source_types": ["academic_paper"],
                "supplemental_source_types": ["web_page"],
                "citation_required": True,
                "manual_review_required": True,
                "allow_synthetic": False,
                "freshness_days": 1095,
            },
        },
    )
    external_result = ExternalRetrievalResult(
        query="research question",
        normalized_query="research question",
        items=[
            ExternalEvidenceItem(
                evidence_id="paper-1",
                source_type=ExternalSourceType.ACADEMIC_PAPER,
                provider="test",
                source_ref="doi:10.1234/example",
                title="A reviewed paper",
                canonical_url="https://doi.org/10.1234/example",
                retrieved_at="2026-08-01T00:00:00Z",
                published_at="2026-07-01T00:00:00Z",
            )
        ],
    )
    result = ScenarioEvidenceReviewService().review_external_result(
        scenario_id="research_frontier_radar_v1",
        policy=KnowledgeEvidencePolicy.model_validate(
            request.options["scenario_evidence_policy"]
        ),
        result=external_result,
        cited_evidence_ids=("paper-1",),
    )

    assert result is not None
    assert result.scenario_id == "research_frontier_radar_v1"
    assert result.status == "needs_manual_review"
