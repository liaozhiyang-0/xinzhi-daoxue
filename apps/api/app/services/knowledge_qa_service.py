from __future__ import annotations

import asyncio
import json
import logging
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
from app.contracts.learning import LearningPathDraft
from app.services.evidence_excerpt import display_evidence_excerpt
from app.services.knowledge_base import KnowledgeBaseService
from app.services.math_formatting_service import MATH_OUTPUT_INSTRUCTION
from app.services.model_service import ModelService
from app.services.rag_retrieval import RAGRetrievalService
from app.services.response_depth import (
    ResponseDepthPolicy,
    depth_instruction,
    policy_for,
)
from app.services.retrieval_context import RetrievalContextService

DISCLAIMER = "当前答案依据课程知识库证据整理；未知字段和发布决定仍需人工复核。"
LOGGER = logging.getLogger(__name__)


def _requested_plan_days(question: str) -> int | None:
    """Read an explicit learning-plan horizon without inventing one."""

    match = re.search(r"(\d+)\s*天", question)
    if match:
        return int(match.group(1))
    week_match = re.search(r"(\d+)\s*周", question)
    if week_match:
        return int(week_match.group(1)) * 7
    chinese_weeks = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5}
    for label, weeks in chinese_weeks.items():
        if f"{label}周" in question:
            return weeks * 7
    return None


def _planned_days(staged_plan: list[dict[str, object] | str]) -> int:
    """Estimate covered days from explicit day/week markers in model output."""

    day_values: list[int] = []
    week_values: list[int] = []
    for item in staged_plan:
        if not isinstance(item, dict):
            continue
        for key in ("day", "days", "day_number"):
            value = item.get(key)
            if isinstance(value, int) and value > 0:
                day_values.append(value)
                break
        for key in ("week", "week_number"):
            value = item.get(key)
            if isinstance(value, int) and value > 0:
                week_values.append(value)
                break
    if day_values:
        return max(day_values)
    if week_values:
        return max(week_values) * 7
    return len(staged_plan)


@dataclass(frozen=True, slots=True)
class KnowledgeQAExecution:
    result: AgentResult
    retrieval: RetrievalResult
    context: RetrievalContextPacket


class KnowledgeQAService:
    """Evidence-grounded retrieval with optional model synthesis."""

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
        if request.options.get("allow_cloud") is False:
            return execution
        model_service = self.model_service
        governance = self._is_governance_request(request)
        learning_path = self._is_learning_path_request(request)
        # These two showcase contracts contain first-class user evidence:
        # governance audits the asset records in the prompt and the learning
        # path audits the supplied score history.  A missing local chunk must
        # not prevent the model from organizing that evidence.  Ordinary
        # knowledge QA keeps the stricter retrieval-only boundary below.
        model_synthesis_required = governance or learning_path
        # A governance request must still be useful when retrieval has no
        # matching chunk: the raw asset records in the question are valid
        # input, while course evidence is an optional supporting source.
        if model_service is None:
            if governance:
                return self._model_synthesis_required(
                    execution, "model_service_not_configured"
                )
            if learning_path:
                return self._model_synthesis_required(
                    execution,
                    "model_service_not_configured",
                    learning_path=True,
                )
        if model_service is None or (
            not execution.context.evidence and not model_synthesis_required
        ):
            return execution
        policy = policy_for(request.options, "knowledge_qa")
        context = execution.context.to_retrieved_context()
        evidence_context = (
            context
            if execution.context.evidence
            else "未检索到课程证据；不得把课程知识库内容当作已提供的资产元数据。"
        )
        if governance:
            system_prompt = (
                "你是课程知识库治理审查助手。请把用户给出的资产记录和检索证据整理成可执行的审查报告。"
                "资产标题与版本号只能来自用户原始输入；来源、审批状态、审批人、权限和链接若未提供必须写‘未知’。"
                "检索证据只能支持课程内容或版本关系的说明，不能被当作资产元数据。"
                "版本号不同只能标为‘可能需要复核’，不能直接断言内容冲突。"
                "不要批准、发布或回滚任何资产；明确列出发布阻塞项、发布前/后/回滚检查清单。"
                "回答必须按‘结论、逐项资产核对、版本冲突、发布阻塞项、发布前/后/回滚清单’组织，"
                "让每个资产都能看到已知字段、未知字段和对应证据边界。"
                "引用检索证据时使用真实证据编号如[S1]，不得编造编号、页码、链接或审批结论。"
            )
            user_prompt = (
                f"用户原始请求（资产记录的唯一来源）：\n{self._question(request)}\n\n"
                f"课程检索证据（仅作辅助依据）：\n{evidence_context}"
            )
            task_type = "knowledge_answer"
        elif learning_path:
            requested_days = _requested_plan_days(self._question(request))
            horizon_instruction = (
                f"覆盖至少{requested_days}天"
                if requested_days is not None
                else "覆盖用户明确要求的完整时间范围"
            )
            system_prompt = (
                "你是学习证据诊断助手。请只根据用户提供的作答记录、分数、"
                "错误描述和课程检索证据整理学习路径；把观察到的证据、"
                "合理推测和未知信息分开。一次错误不能直接推出能力定论，"
                "不得虚构历史成绩、阈值或课程标准。输出应包含：证据摘要、"
                f"最可能的薄弱知识点（带置信度和依据）、先修关系、{horizon_instruction}的"
                "分阶段计划、至少两道验证任务、完成证据和需要教师介入的节点。"
                "如果请求指定了周数或天数，staged_plan必须用连续的day或week字段覆盖完整周期，"
                "不得擅自缩短为7天或另一个默认周期。"
                "课程证据只能使用真实编号如[S1]，不得编造编号。"
                "只输出一个 JSON 对象，字段必须是：evidence_summary、"
                "weak_knowledge_points、prerequisite_path、staged_plan、"
                "verification_tasks、completion_evidence、"
                "teacher_intervention_points。不要输出 Markdown。"
            )
            user_prompt = (
                f"用户原始记录（唯一的学习证据来源）：\n{self._question(request)}\n\n"
                f"课程检索证据（仅作辅助依据）：\n{evidence_context}"
            )
            task_type = "knowledge_answer"
        else:
            system_prompt = (
                "你是电子信息课程助学助手。只能依据给定证据回答；"
                "引用时使用证据编号如[S1]。证据不足时列出条件和缺失信息，"
                f"不得伪造页码、参数或参考文献。{MATH_OUTPUT_INSTRUCTION}"
            )
            user_prompt = f"问题：{self._question(request)}\n\n课程证据：\n{context}"
            task_type = "knowledge_answer"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        messages[-1]["content"] = (
            f"{messages[-1]['content']}\n\n{depth_instruction(policy)}"
        )
        try:
            if learning_path:
                generated = await model_service.generate_json_for_task(
                    task_type,
                    messages=messages,
                    schema=LearningPathDraft,
                    request_id=str(request.options.get("request_id", "")) or None,
                    extra_options={"max_tokens": policy.max_output_tokens},
                )
            else:
                generated = await model_service.generate_for_task(
                    task_type,
                    messages=messages,
                    request_id=str(request.options.get("request_id", "")) or None,
                    extra_options={"max_tokens": policy.max_output_tokens},
                )
        except Exception as exc:
            LOGGER.exception(
                "knowledge_model_generation_failed provider=%s learning_path=%s "
                "error_type=%s error=%s",
                getattr(model_service, "__class__", type(model_service)).__name__,
                learning_path,
                type(exc).__name__,
                str(exc),
            )
            execution.result.warnings.append(
                f"model_generation_unavailable:{type(exc).__name__}"
            )
            if governance or learning_path:
                return self._model_synthesis_required(
                    execution,
                    "model_generation_unavailable",
                    learning_path=learning_path,
                )
            execution.result.fallback_used = True
            execution.result.fallback_reason = "model_generation_unavailable"
            return execution

        if (governance or learning_path) and generated.provider.strip().lower() in {
            "mock",
            "development_mock",
        }:
            execution.result.warnings.append(
                "该展示案例不能使用 Mock 模型作为可发布的大模型整理结果"
            )
            return self._model_synthesis_required(
                execution,
                "model_generation_mock",
                learning_path=learning_path,
            )

        if not generated.content.strip():
            execution.result.warnings.append("model_generation_empty")
            if governance or learning_path:
                return self._model_synthesis_required(
                    execution,
                    "model_generation_empty",
                    learning_path=learning_path,
                )
            execution.result.fallback_used = True
            execution.result.fallback_reason = "model_generation_empty"
            return execution

        learning_path_draft: LearningPathDraft | None = None
        if learning_path:
            learning_path_draft = LearningPathDraft.model_validate_json(
                generated.content
            )
            generated_content = self._render_learning_path_draft(
                learning_path_draft
            )
        else:
            generated_content = generated.content
        generated_content = re.sub(
            r"(?<!\[)\b(S\d+)\b(?!\])", r"[\1]", generated_content
        )
        evidence_by_id = {
            item.evidence_id: item.source_ref for item in execution.context.evidence
        }
        declared = set(re.findall(r"\[(S\d+)\]", generated_content))
        invalid_ids = declared - evidence_by_id.keys()
        if invalid_ids:
            generated_content = re.sub(
                r"\[(S\d+)\]",
                lambda match: (
                    match.group(0)
                    if match.group(1) in evidence_by_id
                    else "[未核验证据]"
                ),
                generated_content,
            )
            declared -= invalid_ids
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
        execution.result.metrics.provider_latency_ms = (
            execution.result.metrics.provider_latency_ms or 0
        ) + generated.elapsed_ms
        execution.result.metrics.model_latency_ms = (
            execution.result.metrics.model_latency_ms or 0
        ) + generated.elapsed_ms
        if generated.usage is not None:
            execution.result.metrics.input_tokens = generated.usage.prompt_tokens
            execution.result.metrics.output_tokens = generated.usage.completion_tokens
        execution.result.structured_result.update(
            {
                "mode": (
                    "governance_model_generation"
                    if governance
                    else (
                        "learning_path_model_generation"
                        if learning_path
                        else "local_rag_model_generation"
                    )
                ),
                "answer_text": generated_content,
                "verified_evidence_ids": sorted(declared & evidence_by_id.keys()),
                "generation_model": generated.model,
                "generation_usage": (
                    generated.usage.model_dump(exclude_none=True)
                    if generated.usage is not None
                    else {}
                ),
                "synthesis_trace": {
                    "task_type": task_type,
                    "raw_request_included": True,
                    "evidence_ids": sorted(evidence_by_id),
                    "source_refs": list(dict.fromkeys(evidence_by_id.values())),
                },
            }
        )
        if learning_path_draft is not None:
            draft_data = learning_path_draft.model_dump(mode="json")
            requested_days = _requested_plan_days(self._question(request))
            planned_days = _planned_days(learning_path_draft.staged_plan)
            plan_horizon_check = {
                "status": (
                    "passed"
                    if requested_days is None or planned_days >= requested_days
                    else "mismatch"
                ),
                "requested_days": requested_days,
                "planned_days": planned_days,
                "reason": (
                    "模型计划覆盖请求周期"
                    if requested_days is None or planned_days >= requested_days
                    else "模型计划未覆盖请求的完整周期"
                ),
            }
            draft_data["plan_horizon_check"] = plan_horizon_check
            execution.result.business_data.update(draft_data)
            execution.result.structured_result["business_data"] = draft_data
            execution.result.structured_result["learning_path_draft"] = draft_data
        execution.result.metrics.model_calls += 1
        for artifact in execution.result.artifacts:
            artifact.content.update(execution.result.structured_result)
            artifact.source_refs = list(citations)
        return execution

    @staticmethod
    def _render_learning_path_draft(draft: LearningPathDraft) -> str:
        """Keep the answer readable while retaining the exact model fields."""

        def display(value: object) -> str:
            if isinstance(value, str):
                return value
            return json.dumps(value, ensure_ascii=False)

        lines = [
            "证据摘要",
            display(draft.evidence_summary),
            "",
            "薄弱知识点",
            *[f"- {display(item)}" for item in draft.weak_knowledge_points],
            "",
            "前置知识路径",
            " → ".join(draft.prerequisite_path),
            "",
            "阶段学习计划",
            *[f"- {display(item)}" for item in draft.staged_plan],
            "",
            "验证任务",
            *[f"- {display(item)}" for item in draft.verification_tasks],
            "",
            "完成证据",
            *[f"- {display(item)}" for item in draft.completion_evidence],
            "",
            "教师介入节点",
            *[f"- {display(item)}" for item in draft.teacher_intervention_points],
        ]
        return "\n".join(lines)

    @staticmethod
    def _model_synthesis_required(
        execution: KnowledgeQAExecution,
        reason: str,
        *,
        learning_path: bool = False,
    ) -> KnowledgeQAExecution:
        """Block showcase publication instead of presenting local text."""

        result = execution.result
        result.provider = "model_unavailable"
        result.answer = ""
        result.citations = []
        result.fallback_used = True
        result.fallback_reason = reason
        warning = (
            "学习路径必须经过大模型整理后才能作为展示结果"
            if learning_path
            else "治理报告必须经过大模型整理后才能发布"
        )
        result.warnings = list(dict.fromkeys([*result.warnings, warning]))
        result.structured_result.update(
            {
                "mode": (
                    "learning_path_model_required"
                    if learning_path
                    else "governance_model_required"
                ),
                "publishable": False,
                "generation_required": True,
                "generation_failure_reason": reason,
                "synthesis_trace": {
                    "status": "blocked",
                    "raw_request_included": True,
                    "evidence_ids": sorted(
                        item.evidence_id for item in execution.context.evidence
                    ),
                    "source_refs": list(
                        dict.fromkeys(
                            item.source_ref for item in execution.context.evidence
                        )
                    ),
                },
            }
        )
        for artifact in result.artifacts:
            artifact.content.update(result.structured_result)
            artifact.source_refs = []
        return execution

    def run(self, agent_id: str, request: AgentRequest) -> KnowledgeQAExecution:
        question = self._question(request)
        retrieval_limit = policy_for(
            request.options, "knowledge_qa"
        ).retrieval_limit
        if self.rag_retrieval is None:
            retrieval = self._local_lexical_search(
                question, request.course_id, top_k=retrieval_limit
            )
        else:
            try:
                retrieval = self.rag_retrieval.search(
                    query_text=question,
                    course_id=request.course_id,
                    intent=request.intent.value,
                    target_agent_id=agent_id,
                    top_k=retrieval_limit,
                )
            except Exception as exc:
                retrieval = self._local_lexical_search(
                    question,
                    request.course_id,
                    warning=f"local_lexical_fallback:{type(exc).__name__}",
                    top_k=retrieval_limit,
                )
            if not retrieval.hits:
                lexical = self._local_lexical_search(
                    question,
                    request.course_id,
                    warning="local_lexical_fallback:no_rag_hits",
                    top_k=retrieval_limit,
                )
                if lexical.hits:
                    retrieval = lexical
        return self.from_retrieval(agent_id, request, retrieval)

    def _local_lexical_search(
        self,
        question: str,
        course_id: str,
        warning: str | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        result = self.knowledge_base.search_result(
            question,
            [course_id],
            top_k or self.knowledge_base.settings.knowledge_default_top_k,
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
        policy = policy_for(request.options, "knowledge_qa")
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
            for hit in context.evidence[: policy.evidence_limit]
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
            # Keep the compact legacy envelope for clients that still render
            # local retrieval hits from ``structured_result.knowledge``.
            "knowledge": {"hits": excerpts},
            "suggested_reading": [hit.document_path for hit in context.evidence],
            "evidence_status": context.evidence_status,
            "retrieval_mode": context.retrieval_mode,
            "retrieved_context": context.to_retrieved_context(),
            "sources": context.source_refs,
            "warnings": [DISCLAIMER, *context.warnings],
            "response_depth": policy.metadata(),
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
        answer = self._build_grounded_answer(question, context, summary, policy)
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
        question: str,
        context: RetrievalContextPacket,
        summary: str,
        policy: ResponseDepthPolicy | None = None,
    ) -> str:
        policy = policy or policy_for({}, "knowledge_qa")
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
        evidence_limit = min(policy.evidence_limit, len(context.evidence))
        for evidence in context.evidence[:evidence_limit]:
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

    @staticmethod
    def _is_governance_request(request: AgentRequest) -> bool:
        scenario_id = str(request.options.get("scenario_id", "")).strip()
        if scenario_id == "department_knowledge_governance_v1":
            return True
        if request.intent.value != "summarize_knowledge":
            return False
        text = KnowledgeQAService._question(request)
        return bool(
            re.search(
                r"知识库|课程资产|版本冲突|审批|发布阻塞|回滚|资产清单|权限治理",
                text,
            )
        )

    @staticmethod
    def _is_learning_path_request(request: AgentRequest) -> bool:
        return str(request.options.get("scenario_id", "")).strip() == (
            "student_learning_path_v1"
        ) or request.scenario_id == "student_learning_path_v1"
