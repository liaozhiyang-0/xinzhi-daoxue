from app.contracts import KnowledgeHit, RetrievalResult
from app.services.retrieval_context import RetrievalContextService


def hit(course_id: str, chunk_id: str, content: str) -> KnowledgeHit:
    return KnowledgeHit(
        chunk_id=chunk_id,
        course_id=course_id,
        course_name="测试课程",
        chapter="第一章",
        section="第一节",
        document_path="教材/第一章.md",
        title="第一节",
        content=content,
        score=8,
        source_ref=f"kb://{course_id}/教材/第一章.md#chunk-{chunk_id}",
    )


def test_context_packet_is_course_scoped_deduplicated_and_bounded() -> None:
    ct = hit("CT", "1", "甲" * 80)
    result = RetrievalResult(
        query="问题",
        normalized_query="问题",
        course_ids=["CT"],
        hits=[ct, ct.model_copy(), hit("AE", "2", "乙" * 80)],
        confidence=0.8,
        latency_ms=1,
    )

    packet = RetrievalContextService(50).build(
        result, course_id="CT", intent="general_qa"
    )

    assert len(packet.evidence) == 1
    assert len(packet.evidence[0].content) == 50
    assert all(ref.startswith("kb://CT/") for ref in packet.source_refs)
