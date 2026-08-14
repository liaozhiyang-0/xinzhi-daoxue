from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from app.contracts import (
    AgentRequest,
    AgentResult,
    Artifact,
    ArtifactType,
    RetrievalContextPacket,
    RetrievalResult,
)
from app.services.evidence_excerpt import display_evidence_excerpt
from app.services.knowledge_base import KnowledgeBaseService
from app.services.math_formatting_service import MATH_OUTPUT_INSTRUCTION
from app.services.model_service import ModelService
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
        model_service: ModelService | None = None,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.context_service = context_service
        self.rag_retrieval = rag_retrieval
        self.model_service = model_service

    async def run_with_generation(
        self, agent_id: str, request: AgentRequest
    ) -> KnowledgeQAExecution:
        execution = await asyncio.to_thread(self.run, agent_id, request)
        # The formal learning UI explicitly opts out of cloud execution. In
        # that mode the retrieval result is already the local answer; do not
        # enter the model gateway for this request.
        if request.options.get("allow_cloud") is False:
            return execution
        model_service = self.model_service
        if model_service is None or not execution.context.evidence:
            return execution
        context = execution.context.to_retrieved_context()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是电子信息课程助学助手。只能依据给定证据回答；"
                    "引用时使用证据编号如[S1]。证据不足时列出条件和缺失信息，"
                    f"不得伪造页码、参数或参考文献。{MATH_OUTPUT_INSTRUCTION}"
                ),
            },
            {
                "role": "user",
                "content": f"问题：{self._question(request)}\n\n课程证据：\n{context}",
            },
        ]
        try:
            generated = await model_service.generate_for_task(
                "knowledge_answer",
                messages=messages,
                request_id=str(request.options.get("request_id", "")) or None,
            )
        except Exception as exc:
            execution.result.warnings.append(
                f"model_generation_unavailable:{type(exc).__name__}"
            )
            execution.result.fallback_used = True
            execution.result.fallback_reason = "model_generation_unavailable"
            return execution

        generated_content = re.sub(
            r"(?<!\[)\b(S\d+)\b(?!\])", r"[\1]", generated.content
        )
        evidence_by_id = {
            item.evidence_id: item.source_ref for item in execution.context.evidence
        }
        declared = set(re.findall(r"\[(S\d+)\]", generated_content))
        citations = [
            source
            for evidence_id, source in evidence_by_id.items()
            if evidence_id in declared
        ]
        if not citations:
            execution.result.warnings.append("模型回答未包含可验证的证据编号")
        execution.result.provider = generated.provider
        execution.result.answer = generated_content
        execution.result.citations = citations
        execution.result.structured_result.update(
            {
                "mode": "local_rag_model_generation",
                "answer_text": generated_content,
                "verified_evidence_ids": sorted(declared & evidence_by_id.keys()),
                "generation_model": generated.model,
                "generation_usage": (
                    generated.usage.model_dump(exclude_none=True)
                    if generated.usage is not None
                    else {}
                ),
            }
        )
        execution.result.metrics.model_calls += 1
        for artifact in execution.result.artifacts:
            artifact.content.update(execution.result.structured_result)
            artifact.source_refs = list(citations)
        return execution

    def run(self, agent_id: str, request: AgentRequest) -> KnowledgeQAExecution:
        question = self._question(request)
        if self.rag_retrieval is None:
            retrieval = self._local_lexical_search(question, request.course_id)
        else:
            try:
                retrieval = self.rag_retrieval.search(
                    query_text=question,
                    course_id=request.course_id,
                    intent=request.intent.value,
                    target_agent_id=agent_id,
                    top_k=self.knowledge_base.settings.knowledge_default_top_k,
                )
            except Exception as exc:
                retrieval = self._local_lexical_search(
                    question,
                    request.course_id,
                    warning=f"local_lexical_fallback:{type(exc).__name__}",
                )
            if not retrieval.hits:
                lexical = self._local_lexical_search(
                    question,
                    request.course_id,
                    warning="local_lexical_fallback:no_rag_hits",
                )
                if lexical.hits:
                    retrieval = lexical
        return self.from_retrieval(agent_id, request, retrieval)

    def _local_lexical_search(
        self, question: str, course_id: str, warning: str | None = None
    ) -> RetrievalResult:
        result = self.knowledge_base.search_result(
            question,
            [course_id],
            self.knowledge_base.settings.knowledge_default_top_k,
        )
        if warning:
            result = result.model_copy(
                update={"warnings": list(dict.fromkeys([*result.warnings, warning]))}
            )
        return result

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
            query_override=question,
        )
        chapters = list(dict.fromkeys(hit.chapter for hit in context.evidence))
        excerpts = [
            {
                "chapter": hit.chapter,
                "title": hit.title,
                "excerpt": display_evidence_excerpt(hit.content, max_chars=240),
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
        answer = self._build_grounded_answer(question, context, summary)
        result = AgentResult(
            agent_id=agent_id,
            provider="local",
            answer=answer,
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
    def _build_grounded_answer(
        question: str, context: RetrievalContextPacket, summary: str
    ) -> str:
        if not context.evidence:
            return (
                f"## {question}\n\n"
                "暂时没有在当前课程知识库中检索到足够依据。"
                "可以补充课程范围、关键词或上传相关资料后再问。"
            )
        lines = [
            f"## {question}",
            "",
            "### 先给结论",
            f"这是一个知识讲解问题。{summary}。下面的说明仅使用当前本地课程资料中的内容，引用标记对应右侧可打开的原文。",
            "",
            "### 核心讲解",
            "- 先掌握资料中的定义、工作条件和关键组成，再结合工作过程理解结论。",
            "- 如果需要计算或设计，应以资料中的公式、参数约束和例题步骤为准，"
            "不把概念说明误当成具体数值求解。",
            "",
            "### 本地资料依据",
        ]
        for evidence in context.evidence[:4]:
            excerpt = display_evidence_excerpt(evidence.content, max_chars=520)
            label = evidence.chapter or evidence.title or evidence.document_path
            lines.extend([f"- [{evidence.evidence_id}] {label}", f"  {excerpt}"])
        lines.extend(
            [
                "",
                "### 下一步",
                "如果你希望继续深入，可以指定“工作原理”“参数计算”“拓扑对比”或“设计例题”，系统会沿用本地资料继续检索。",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _question(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
