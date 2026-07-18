from __future__ import annotations

from dataclasses import dataclass

from app.contracts import RetrievalContextPacket, RetrievalResult


@dataclass(frozen=True, slots=True)
class EvidenceQuality:
    status: str
    reason: str


class EvidenceQualityEvaluator:
    def __init__(
        self,
        *,
        sufficient_min_score: float = 0.65,
        partial_min_score: float = 0.4,
        sufficient_min_sources: int = 2,
    ) -> None:
        self.sufficient_min_score = sufficient_min_score
        self.partial_min_score = partial_min_score
        self.sufficient_min_sources = sufficient_min_sources

    def evaluate(self, result: RetrievalResult) -> EvidenceQuality:
        if not result.hits:
            return EvidenceQuality("insufficient", "没有满足最低分阈值的证据")
        if result.confidence is None:
            return EvidenceQuality("failed", "检索器未提供置信度")
        source_count = len(
            {hit.document_id or hit.document_path for hit in result.hits}
        )
        if (
            result.confidence >= self.sufficient_min_score
            and source_count >= self.sufficient_min_sources
        ):
            return EvidenceQuality("sufficient", "存在多个较高置信度的课程内来源")
        if result.confidence >= self.partial_min_score:
            return EvidenceQuality("partial", "已命中课程内来源，但证据仍需人工核对")
        return EvidenceQuality("insufficient", "命中分数不足以支持稳定的知识整理")


class RetrievalContextService:
    def __init__(
        self,
        max_context_chars: int,
        evaluator: EvidenceQualityEvaluator | None = None,
    ) -> None:
        self.max_context_chars = max_context_chars
        self.evaluator = evaluator or EvidenceQualityEvaluator()

    def build(
        self,
        result: RetrievalResult,
        *,
        course_id: str,
        intent: str,
    ) -> RetrievalContextPacket:
        evidence = []
        seen_chunks: set[str] = set()
        seen_content: set[str] = set()
        used_chars = 0
        warnings = list(result.warnings)
        for hit in result.hits:
            if hit.course_id.value != course_id:
                warnings.append(f"已丢弃跨课程来源: {hit.source_ref}")
                continue
            signature = " ".join(hit.content.split()).casefold()
            if hit.chunk_id in seen_chunks or signature in seen_content:
                continue
            remaining = self.max_context_chars - used_chars
            if remaining <= 0:
                break
            content = hit.content[:remaining]
            if not content:
                break
            evidence.append(hit.model_copy(update={"content": content}))
            seen_chunks.add(hit.chunk_id)
            seen_content.add(signature)
            used_chars += len(content)
        if len(evidence) < len(result.hits):
            warnings.append("上下文已按字符预算截断或去重")
        quality = self.evaluator.evaluate(result.model_copy(update={"hits": evidence}))
        if quality.status in {"insufficient", "failed"}:
            warnings.append(quality.reason)
        numbered_evidence = [
            hit.model_copy(update={"evidence_id": f"S{index}"})
            for index, hit in enumerate(evidence, start=1)
        ]
        return RetrievalContextPacket(
            query=result.query,
            course_id=course_id,
            intent=intent,
            evidence=numbered_evidence,
            source_refs=[hit.source_ref for hit in numbered_evidence],
            evidence_status=quality.status,
            retrieval_mode=result.retrieval_mode,
            warnings=list(dict.fromkeys(warnings)),
            max_context_chars=self.max_context_chars,
            rag_status=result.rag_status,
            embedding_status=result.embedding_status,
            vector_store_status=result.vector_store_status,
            reranker_status=result.reranker_status,
            query_modalities=result.query_modalities,
            retrieval_trace_id=result.retrieval_trace_id,
            latency_ms=result.latency_ms,
            index_version=result.index_version,
        )
