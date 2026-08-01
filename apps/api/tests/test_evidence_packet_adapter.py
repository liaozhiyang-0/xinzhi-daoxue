from __future__ import annotations

from app.contracts import (
    KnowledgeCourseId,
    KnowledgeHit,
    RetrievalContextPacket,
)
from app.services.evidence_packet_adapter import EvidencePacketAdapterService


def test_adapter_preserves_missing_page_and_version_as_null_with_warning() -> None:
    packet = RetrievalContextPacket(
        query="节点电压法",
        course_id="CT",
        intent="solve_problem",
        evidence=[
            KnowledgeHit(
                chunk_id="chunk-1",
                evidence_id="S1",
                document_id="doc-1",
                course_id=KnowledgeCourseId.CIRCUIT_THEORY,
                course_name="电路理论",
                chapter="节点法",
                document_path="ct/book.md",
                title="节点电压法",
                content="节点电压法正文" * 200,
                score=0.92,
                score_components={"rerank_score": 0.8},
                source_ref="kb://CT/doc-1/chunk-1",
            )
        ],
        source_refs=["kb://CT/doc-1/chunk-1"],
        evidence_status="partial",
        max_context_chars=4_000,
        rag_status="ready",
    )
    adapted = EvidencePacketAdapterService().from_context(
        packet, query="节点电压法", course_id="CT", applicable_skill_ids=["CT.NODAL"]
    )
    assert adapted.sources[0].page is None
    assert adapted.sources[0].source_version is None
    assert adapted.sources[0].support_level == "potentially_relevant"
    assert len(adapted.sources[0].content_excerpt) == 1_200
    assert any("page metadata unavailable" in item for item in adapted.warnings)


def test_unsupported_course_returns_unavailable_without_sources() -> None:
    adapted = EvidencePacketAdapterService().from_context(
        None, query="卷积", course_id="SS"
    )
    assert adapted.retrieval_status == "unavailable"
    assert adapted.sources == []
