from app.contracts import KnowledgeHit, RetrievalResult
from app.services.retrieval_context import EvidenceQualityEvaluator


def test_evidence_quality_distinguishes_sufficient_and_insufficient() -> None:
    evaluator = EvidenceQualityEvaluator()
    empty = RetrievalResult(
        query="q", normalized_query="q", course_ids=["CT"], latency_ms=0
    )
    assert evaluator.evaluate(empty).status == "insufficient"

    hit = KnowledgeHit(
        course_id="CT",
        course_name="电路理论",
        document_path="a.md",
        title="章节",
        content="证据",
        score=10,
        source_ref="kb://CT/a.md#chunk-1",
    )
    strong = empty.model_copy(
        update={
            "hits": [hit, hit.model_copy(update={"chunk_id": "2"})],
            "confidence": 0.8,
        }
    )
    assert evaluator.evaluate(strong).status == "sufficient"
