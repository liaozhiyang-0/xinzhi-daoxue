from __future__ import annotations

from dataclasses import dataclass

from app.contracts import RetrievalContextPacket, RetrievalResult


@dataclass(frozen=True, slots=True)
class EvidenceQuality:
    status: str
    reason: str


class EvidenceQualityEvaluator:
    def evaluate(self, result: RetrievalResult) -> EvidenceQuality:
        if not result.hits:
            return EvidenceQuality("insufficient", "没有满足最低分阈值的证据")
        if result.confidence is None:
            return EvidenceQuality("unavailable", "检索器未提供置信度")
        if result.confidence >= 0.65 and len(result.hits) >= 2:
            return EvidenceQuality("sufficient", "存在多个较高置信度的课程内来源")
        if result.confidence >= 0.4:
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
        quality = self.evaluator.evaluate(result)
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
        if quality.status in {"insufficient", "unavailable"}:
            warnings.append(quality.reason)
        return RetrievalContextPacket(
            query=result.query,
            course_id=course_id,
            intent=intent,
            evidence=evidence,
            source_refs=[hit.source_ref for hit in evidence],
            evidence_status=quality.status,
            warnings=list(dict.fromkeys(warnings)),
            max_context_chars=self.max_context_chars,
        )
