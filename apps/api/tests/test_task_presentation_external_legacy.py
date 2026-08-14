from app.agents import AgentRegistry
from app.contracts import AgentResult
from app.services.task_presentation import build_task_views


def test_legacy_external_search_view_restores_evidence_summary() -> None:
    definition = AgentRegistry().get("RESEARCH_01_ACADEMIC_SEARCH_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="external_retrieval",
        course_id="CT",
        intent="general_qa",
        answer="A source-backed answer.",
        structured_result={
            "external_search": True,
            "external_search_status": "completed",
            "external_search_view": [
                {
                    "evidence_id": "paper-legacy",
                    "source_type": "academic_paper",
                    "provider": "arxiv",
                    "title": "Legacy paper",
                    "url": "https://arxiv.org/abs/2501.00001",
                    "abstract": "A traceable abstract.",
                }
            ],
        },
    )

    presentation, _, _ = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={},
        timings={},
    )

    assert "\u5916\u90e8\u8bc1\u636e" in presentation.source_summary
    assert "\u5916\u90e8\u68c0\u7d22" not in presentation.source_summary
