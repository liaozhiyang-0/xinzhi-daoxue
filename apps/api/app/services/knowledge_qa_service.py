from __future__ import annotations

from dataclasses import dataclass

from app.contracts import (
    AgentRequest,
    AgentResult,
    Artifact,
    ArtifactType,
    RetrievalContextPacket,
    RetrievalResult,
)
from app.services.knowledge_base import KnowledgeBaseService
from app.services.rag_retrieval import RAGRetrievalService
from app.services.retrieval_context import RetrievalContextService

DISCLAIMER = "当前为本地知识库检索整理结果，不是讯飞星辰模型生成的正式回答。"


@dataclass(frozen=True, slots=True)
class KnowledgeQAExecution:
    result: AgentResult
    retrieval: RetrievalResult
    context: RetrievalContextPacket


class KnowledgeQAService:
    """Local retrieval-only LEARN_01 implementation with traceable evidence."""

    def __init__(
        self,
        knowledge_base: KnowledgeBaseService,
        context_service: RetrievalContextService,
        rag_retrieval: RAGRetrievalService | None = None,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.context_service = context_service
        self.rag_retrieval = rag_retrieval

    def run(self, agent_id: str, request: AgentRequest) -> KnowledgeQAExecution:
        question = self._question(request)
        retrieval = (
            self.rag_retrieval.search(
                query_text=question,
                course_id=request.course_id,
                intent=request.intent.value,
                target_agent_id=agent_id,
                top_k=self.knowledge_base.settings.knowledge_default_top_k,
            )
            if self.rag_retrieval is not None
            else self.knowledge_base.search_result(
                question,
                [request.course_id],
                self.knowledge_base.settings.knowledge_default_top_k,
            )
        )
        return self.from_retrieval(agent_id, request, retrieval)

    def from_retrieval(
        self,
        agent_id: str,
        request: AgentRequest,
        retrieval: RetrievalResult,
    ) -> KnowledgeQAExecution:
        question = self._question(request)
        context = self.context_service.build(
            retrieval,
            course_id=request.course_id,
            intent=request.intent.value,
        )
        chapters = list(dict.fromkeys(hit.chapter for hit in context.evidence))
        excerpts = [
            {
                "chapter": hit.chapter,
                "title": hit.title,
                "excerpt": hit.content[:240],
                "score": hit.score,
                "source_ref": hit.source_ref,
                "document_id": hit.document_id,
                "evidence_id": hit.evidence_id,
                "content_type": hit.content_type,
                "related_images": [
                    image.model_dump(mode="json") for image in hit.related_images
                ],
            }
            for hit in context.evidence
        ]
        summary = f"检索到 {len(context.evidence)} 个课程内证据片段；" + (
            f"优先核对章节：{'、'.join(chapters[:3])}。"
            if chapters
            else "暂无可推荐章节。"
        )
        content = {
            "mode": "retrieval_only",
            "question": question,
            "course_id": request.course_id,
            "related_chapters": chapters,
            "summary": summary,
            "core_retrieval_summary": excerpts,
            "suggested_reading": [hit.document_path for hit in context.evidence],
            "evidence_status": context.evidence_status,
            "retrieval_mode": context.retrieval_mode,
            "retrieved_context": context.to_retrieved_context(),
            "sources": context.source_refs,
            "warnings": [DISCLAIMER, *context.warnings],
        }
        artifact = Artifact(
            artifact_type=ArtifactType.ANSWER,
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content=content,
            source_refs=context.source_refs,
            confidence=retrieval.confidence,
        )
        result = AgentResult(
            agent_id=agent_id,
            provider="local",
            answer=f"{DISCLAIMER}\n{summary}",
            structured_result=content,
            artifacts=[artifact],
            citations=context.source_refs,
            warnings=list(dict.fromkeys([DISCLAIMER, *context.warnings])),
            confidence=retrieval.confidence,
            rag_status=retrieval.rag_status,
            evidence_status=context.evidence_status,
            related_images=[
                item.model_dump(mode="json") for item in retrieval.image_hits
            ],
            retrieval_trace_id=retrieval.retrieval_trace_id,
            retrieval_latency_ms=retrieval.latency_ms,
            index_version=retrieval.index_version,
        )
        result.metrics.retrieval_calls = 1
        return KnowledgeQAExecution(result=result, retrieval=retrieval, context=context)

    @staticmethod
    def _question(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
