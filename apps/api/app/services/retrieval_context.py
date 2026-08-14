from __future__ import annotations

import re
from dataclasses import dataclass

from app.contracts import KnowledgeHit, RetrievalContextPacket, RetrievalResult


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
    _TEACHING_QUERY_STRUCTURE_TOKENS = frozenset(
        {
            "\u8bbe\u8ba1",
            "\u8bfe\u5802",
            "\u6559\u6848",
            "\u5206\u949f",
            "\u5305\u542b",
            "\u76ee\u6807",
            "\u6d41\u7a0b",
            "\u5f62\u6210",
            "\u6027\u8bc4\u4ef7",
            "\u8bc4\u4ef7",
            "\u8bbe\u8ba1\u4e00\u4efd",
            "\u8bf7\u4e3a",
        }
    )
    _GENERIC_QUERY_TOKENS = frozenset(
        {
            "请仅",
            "根据",
            "课程",
            "资料",
            "回答",
            "原文",
            "依据",
            "逐条",
            "说明",
            "解释",
            "什么",
            "如何",
            "为什么",
            "本地",
            "章节",
            "完整",
            "推导",
            "内容",
            "问题",
        }
    )

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
        query_override: str | None = None,
    ) -> RetrievalContextPacket:
        evidence = []
        seen_chunks: set[str] = set()
        seen_content: set[str] = set()
        used_chars = 0
        warnings = list(result.warnings)
        deduplicated_hits = self._deduplicate_overlapping_hits(result.hits)
        topic_query = (
            query_override.strip()
            if isinstance(query_override, str) and query_override.strip()
            else result.query
        )
        relevant_hits = self._filter_topic_mismatches(
            topic_query, deduplicated_hits, intent=intent
        )
        if len(relevant_hits) < len(deduplicated_hits):
            warnings.append("检索片段与问题主题不一致，已阻止其作为回答依据")
        for hit in deduplicated_hits:
            if hit not in relevant_hits:
                continue
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
            query=topic_query,
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

    @classmethod
    def _filter_topic_mismatches(
        cls, query: str, hits: list[KnowledgeHit], *, intent: str = ""
    ) -> list[KnowledgeHit]:
        """Drop lexical/vector candidates with no query-topic anchor.

        Course hints such as "电路理论课程资料" are routing context, not
        evidence that a retrieved chunk answers the user's actual question.
        When the query has meaningful topic terms, at least one of those terms
        must occur in the candidate's title, section, or content. If the query
        contains no meaningful anchor (for example, "请解释它"), retain the
        existing candidates and let the normal quality evaluator decide.
        """

        if not hits:
            return []
        course_names = {hit.course_name for hit in hits if hit.course_name}
        query_for_topics = query
        for course_name in course_names:
            query_for_topics = query_for_topics.replace(course_name, " ")
        query_tokens = cls._topic_tokens(query_for_topics)
        course_tokens = cls._topic_tokens(" ".join(course_names))
        anchor_tokens = {
            token
            for token in query_tokens
            - cls._GENERIC_QUERY_TOKENS
            - cls._TEACHING_QUERY_STRUCTURE_TOKENS
            - course_tokens
            if not token.isdigit()
            and "第" not in token
            and "章" not in token
            and "节" not in token
            and token not in {"题", "问"}
        }
        if not anchor_tokens:
            return hits
        teaching_intent = intent in {"lesson_prep", "assignment_review"}
        relevant: list[KnowledgeHit] = []
        for hit in hits:
            metadata_tokens = cls._topic_tokens(
                " ".join((hit.title, hit.chapter, hit.section))
            )
            content_tokens = cls._topic_tokens(hit.content)
            metadata_matches = anchor_tokens & metadata_tokens
            if teaching_intent and len(anchor_tokens) > 1:
                # A single shared bigram is too weak for lesson evidence. For
                # example, a query about capacitor-voltage continuity must not
                # accept every source whose title merely contains "voltage" or
                # "capacitor". Keep a teaching source only when its metadata
                # carries at least two independent topic anchors.
                if len(metadata_matches) >= 2:
                    relevant.append(hit)
            elif metadata_matches:
                relevant.append(hit)
            elif not teaching_intent and anchor_tokens & content_tokens:
                relevant.append(hit)
        return relevant

    @staticmethod
    def _topic_tokens(value: str) -> set[str]:
        tokens: set[str] = set(re.findall(r"[A-Za-z0-9]+", value.casefold()))
        for sequence in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", value):
            tokens.update(
                sequence[index : index + 2]
                for index in range(len(sequence) - 1)
            )
        return tokens

    @staticmethod
    def _token_set(value: str) -> set[str]:
        return set(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", value.casefold()))

    @classmethod
    def _deduplicate_overlapping_hits(
        cls, hits: list[KnowledgeHit]
    ) -> list[KnowledgeHit]:
        selected: list[KnowledgeHit] = []
        signatures: list[set[str]] = []
        for hit in hits:
            signature = cls._token_set(hit.content)
            source_document = hit.source_ref.split("#", 1)[0]
            duplicate = False
            for prior, prior_signature in zip(selected, signatures, strict=True):
                same_document = prior.source_ref.split("#", 1)[0] == source_document
                if not same_document or not signature:
                    continue
                overlap = len(signature & prior_signature)
                containment = overlap / max(
                    1, min(len(signature), len(prior_signature))
                )
                if containment >= 0.72:
                    duplicate = True
                    break
            if not duplicate:
                selected.append(hit)
                signatures.append(signature)
        return selected
