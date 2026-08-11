from __future__ import annotations

import re

from app.agents import AgentDefinition
from app.contracts import (
    AgentResult,
    EvidenceViewItem,
    KnowledgeHit,
    RAGInteractionMode,
    TaskExecutionSummary,
    TaskPresentation,
    WorkflowContextBundle,
)
from app.knowledge_catalog import KNOWLEDGE_COURSE_NAMES
from app.services.math_formatting_service import MathFormattingService

COURSE_LABELS = KNOWLEDGE_COURSE_NAMES
MATH_FORMATTER = MathFormattingService()


def _is_orphan_formula_line(line: str) -> bool:
    value = line.strip()
    if not value:
        return True
    if re.fullmatch(r"(?:-{2,3}|[}\]]|\\(?:\]|\)|right|end\{[^}]+\}))+", value):
        return True
    if re.search(r"[\u4e00-\u9fff]", value):
        return False
    return (
        value.count("}") > value.count("{")
        or value.count("]") > value.count("[")
        or ("\\right" in value and "\\left" not in value)
        or ("\\]" in value and "\\[" not in value)
    )


def _clean_evidence_excerpt(value: str) -> str:
    """Keep clipped retrieval excerpts readable without fabricating missing math."""

    raw = str(value or "").strip()
    if not raw:
        return ""
    lines = raw.splitlines()
    while lines and _is_orphan_formula_line(lines[0]):
        lines.pop(0)
    lines = [line for line in lines if line.strip() not in {"--", "---", "\\]", "\\)"}]
    cleaned = "\n".join(lines).strip()
    return cleaned or "该资料片段的公式未完整落在检索片段内，请打开原文查看。"


TASK_LABELS = {
    "GENERAL_QUESTION_V1": "通用问题解答",
    "LEARN_01_KNOWLEDGE_QA_V1": "知识问答",
    "LEARN_01_LOCAL_RETRIEVAL_V1": "知识问答",
    "SOLVER_CT_V1": "电路解题",
    "TEACH_01_LESSON_PREP_V1": "教案设计",
    "TEACH_02_ASSIGNMENT_REVIEW_V1": "作业批改",
    "RESEARCH_01_ACADEMIC_SEARCH_V1": "科研前沿检索与证据简报",
    "RESEARCH_02_ACADEMIC_WRITING_V1": "学术写作",
    "RESEARCH_03_DATA_ANALYSIS_V1": "数据分析",
}


def build_task_views(
    *,
    definition: AgentDefinition,
    result: AgentResult,
    bundle: WorkflowContextBundle | None,
    routing: dict[str, object],
    timings: dict[str, int],
) -> tuple[TaskPresentation, TaskExecutionSummary, list[EvidenceViewItem]]:
    rag_mode = RAGInteractionMode(definition.retrieval_policy.interaction_mode)
    validation = result.structured_result.get("citation_validation", {})
    validation = validation if isinstance(validation, dict) else {}
    external_validation = result.structured_result.get(
        "external_citation_validation", {}
    )
    external_validation = (
        external_validation if isinstance(external_validation, dict) else {}
    )
    used_ids = {
        str(item) for item in validation.get("valid_ids", []) if isinstance(item, str)
    }
    if bundle is not None and result.provider in {"local", "local_agent"}:
        sources = set(result.citations)
        used_ids.update(
            item.evidence_id
            for item in bundle.evidence_items
            if item.source_ref in sources
        )
    verified_ids = result.structured_result.get("verified_evidence_ids", [])
    if isinstance(verified_ids, list):
        used_ids.update(str(item) for item in verified_ids if isinstance(item, str))
    runtime_evidence = _runtime_knowledge_hits(result)
    evidence_items = (
        list(bundle.evidence_items)
        if bundle is not None and bundle.evidence_items
        else runtime_evidence
    )
    if bundle is None and result.provider in {"local", "local_agent"}:
        sources = set(result.citations)
        used_ids.update(
            item.evidence_id
            for item in evidence_items
            if item.source_ref in sources
        )
    entered_ids = (
        set(bundle.workflow_evidence_ids)
        if bundle is not None
        else {item.evidence_id for item in runtime_evidence}
    )
    if bundle is not None:
        bundle.used_evidence_ids = sorted(used_ids)
    evidence_view = _evidence_view(evidence_items, entered_ids, used_ids, rag_mode)
    external_retrieval = result.structured_result.get("external_retrieval", {})
    external_retrieval = (
        external_retrieval if isinstance(external_retrieval, dict) else {}
    )
    external_count = len(external_retrieval.get("items", []))
    external_attempted = bool(
        external_retrieval.get("status")
        or external_retrieval.get("provider_status")
        or external_retrieval.get("warnings")
        or external_retrieval.get("search_queries")
    )
    course_label = COURSE_LABELS.get(result.course_id, result.course_id or "课程")
    is_solver = rag_mode == RAGInteractionMode.METHOD_REFERENCE
    is_general = definition.agent_id == "GENERAL_QUESTION_V1"
    is_local_research = definition.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    is_local_knowledge_fallback = (
        result.structured_result.get("answer_mode") == "local_knowledge_fallback"
    )
    is_no_verified_evidence = (
        result.structured_result.get("answer_mode") == "no_verified_evidence"
    )
    is_external_search_result = bool(
        result.structured_result.get("external_search", False)
    )
    task_label = (
        "学术论文检索"
        if is_external_search_result
        else TASK_LABELS.get(definition.agent_id, definition.display_name)
    )
    fallback = bool(result.fallback_used or routing.get("fallback_used", False))
    mock = bool(result.mock_used or result.provider == "mock")
    citation_status = str(
        validation.get(
            "status",
            external_validation.get("status", "not_run"),
        )
    )
    used_count = len(used_ids)
    evidence_count = len(evidence_items)
    workflow_count = len(entered_ids)
    external_items = external_retrieval.get("items", [])
    academic_external_count = sum(
        1
        for item in external_items
        if isinstance(item, dict) and item.get("source_type") == "academic_paper"
    )
    conference_external_count = sum(
        1
        for item in external_items
        if isinstance(item, dict)
        and isinstance(item.get("metadata"), dict)
        and item["metadata"].get("category") == "conference"
    )
    web_external_count = max(
        0, external_count - academic_external_count - conference_external_count
    )
    if external_count:
        source_parts = []
        if academic_external_count:
            source_parts.append(f"论文 {academic_external_count}")
        if web_external_count:
            source_parts.append(f"报道 {web_external_count}")
        if conference_external_count:
            source_parts.append(f"会议 {conference_external_count}")
        source_summary = "外部证据 · " + " / ".join(source_parts)
        evidence_message = "已完成多源网络检索；右侧可查看来源摘要、检索时间和原文链接"
    elif is_local_research and is_no_verified_evidence:
        source_summary = "当前主题暂无可核验证据"
        evidence_message = ""
    elif is_local_research and is_local_knowledge_fallback:
        source_summary = "本地知识初步回答"
        evidence_message = (
            "已按多个科研子问题组织回答；当前内容未绑定外部论文，具体文献和定量数据需后续核验"
        )
    elif is_local_research and external_attempted:
        source_summary = "外部检索未形成可展示证据"
        evidence_message = (
            "已执行论文、报道等外部检索，但候选结果未通过摘要完整性或相关性审核；"
            "当前回答不把未通过审核的候选当作依据。"
        )
    elif is_local_research:
        source_summary = "本地模型知识"
        evidence_message = "本次未触发外部论文检索；具体文献需人工核验"
    elif is_solver:
        source_summary = (
            f"方法参考 {evidence_count} 条" if evidence_count else "暂无方法参考"
        )
        evidence_message = "检索资料仅作方法参考，未声明为云端解答依据"
    elif used_count:
        source_summary = f"使用 {used_count} 条课程资料"
        evidence_message = "本回答有直接课程资料支持"
    elif fallback and evidence_count:
        source_summary = f"已检索 {evidence_count} 条课程资料"
        evidence_message = "资料检索已完成，但后备结果未将其声明为直接生成依据"
    elif result.evidence_status == "partial":
        source_summary = f"补充资料 {evidence_count} 条"
        evidence_message = "当前证据仅覆盖部分回答内容"
    elif evidence_count:
        source_summary = f"已检索 {evidence_count} 条课程资料"
        evidence_message = "资料已进入任务上下文；请在右侧核对具体依据"
    elif rag_mode == RAGInteractionMode.NO_RAG:
        source_summary = "未使用外部材料"
        evidence_message = "本任务未调用课程知识库"
    elif rag_mode in {
        RAGInteractionMode.USER_SOURCES_ONLY,
        RAGInteractionMode.DATA_CONTEXT_ONLY,
    }:
        source_summary = "使用用户提供材料" if result.answer else "未使用外部材料"
        evidence_message = "本任务未调用课程知识库"
    else:
        source_summary = "未使用课程资料"
        evidence_message = "当前资料中未找到直接证据"
    provider_label = (
        "开发态 Mock"
        if mock
        else "本地安全后备"
        if fallback
        else "本地知识增强"
        if result.provider == "local"
        else "内部 Agent 协作"
        if result.provider == "local_agent"
        else "外部学术检索"
        if result.provider == "external_retrieval"
        else "智能协作"
    )
    result_status = str(result.structured_result.get("result_status", "accepted"))
    model_execution = result.structured_result.get("model_execution", {})
    generation_incomplete = bool(
        isinstance(model_execution, dict)
        and model_execution.get("output_status") == "partial"
    )
    generation_failed = bool(
        isinstance(model_execution, dict)
        and model_execution.get("status") == "failed"
    )
    quality_gate = result.structured_result.get("quality_gate", {})
    quality_gate_status = (
        str(quality_gate.get("status", "not_checked"))
        if isinstance(quality_gate, dict)
        else "not_checked"
    )
    if result.provider == "external_retrieval" and external_count:
        answer_quality_status = "checked"
        answer_quality_message = (
            "检索结果已完成来源、时间和链接字段整理；摘要内容仍建议打开原文核对。"
        )
    elif is_local_research and is_no_verified_evidence:
        answer_quality_status = "insufficient"
        answer_quality_message = ""
    elif is_local_research and is_local_knowledge_fallback:
        answer_quality_status = "provisional"
        answer_quality_message = (
            "回答已生成，但当前基于本地知识框架，未使用外部文献作为直接依据"
        )
    elif (
        (is_general or is_local_research)
        and isinstance(model_execution, dict)
        and model_execution.get("status") == "success"
    ):
        answer_quality_status = "generated"
        answer_quality_message = ""
    elif generation_failed:
        answer_quality_status = "generation_failed"
        answer_quality_message = "专业模型未形成完整答案，当前内容不能视为已核对结论。"
    elif generation_incomplete:
        answer_quality_status = "incomplete"
        answer_quality_message = (
            "模型输出未完整覆盖全部小问；已保留可用内容，但需要继续生成或复核。"
        )
    elif quality_gate_status == "fail":
        answer_quality_status = "needs_review"
        answer_quality_message = "结果检查发现阻断项，请先复核后再使用最终结论。"
    elif quality_gate_status == "partial":
        answer_quality_status = "needs_review"
        answer_quality_message = (
            "结构检查已完成，但关键结论尚未获得充分的确定性验证。"
        )
    elif fallback:
        answer_quality_status = "fallback_complete"
        answer_quality_message = (
            "主模型未完成，本答案由后备模型生成；运行成功不等于答案质量已验证。"
        )
    elif quality_gate_status == "pass":
        answer_quality_status = "checked"
        answer_quality_message = "当前结构与可执行检查均已通过。"
    else:
        answer_quality_status = "not_checked"
        answer_quality_message = "本答案尚无独立答案质量判定。"
    requires_review = answer_quality_status in {
        "generation_failed",
        "incomplete",
        "needs_review",
        "fallback_complete",
        "not_checked",
    }
    status_label = (
        "开发演示"
        if mock
        else "生成失败"
        if generation_failed
        else "回答未完整"
        if generation_incomplete
        else "建议复核"
        if answer_quality_status == "needs_review"
        else "后备模型完成"
        if fallback
        else "带提示完成"
        if result_status == "accepted_with_warnings"
        else "已完成"
    )
    fallback_messages = {
        "cloud_opt_out": "已按本地优先策略处理，本次未调用星辰工作流。",
        "xingchen_response_parse_error": (
            "云端结果格式校验未通过，本次已切换到本地安全后备结果。"
        ),
        "provider_timeout": "云端响应超时，本次已切换到本地安全后备结果。",
        "xingchen_timeout": "云端响应超时，本次已切换到本地安全后备结果。",
        "not_configured": "该云端能力尚未配置，本次已切换到本地安全后备结果。",
        "general_model_unavailable": (
            "通用回答模型暂不可用，本次未调用星辰工作流。"
        ),
        "academic_generation_direct_model": (
            "专业求解链路未形成完整回答，已由通用模型直接完成本次回答。"
        ),
        "direct_general_model_unavailable": (
            "专业与通用回答模型当前均不可用，请稍后重试。"
        ),
    }
    generation_failure_messages = {
        "model_timeout": "回答模型响应超时，请稍后重试。",
        "model_provider_unavailable": "回答模型暂时不可用，请稍后重试。",
        "general_model_unexpected_error": "回答模型暂时不可用，请稍后重试。",
        "general_model_empty_response": "回答模型返回空内容，请稍后重试。",
    }
    generation_error = (
        str(model_execution.get("error_type", ""))
        if isinstance(model_execution, dict)
        else ""
    )
    fallback_message = generation_failure_messages.get(
        generation_error,
        "回答模型本次未完成，请稍后重试。",
    ) if generation_failed else (
        fallback_messages.get(
            result.fallback_reason,
            "云端主能力本次未完成，已切换到本地安全后备结果。",
        )
        if fallback
        else ""
    )
    steps = _execution_steps(result, bundle, citation_status)
    title = (
        task_label
        if definition.scene == "research" or is_general
        else f"{task_label} · {course_label}"
    )
    presentation = TaskPresentation(
        title=title,
        status_label=status_label,
        source_summary=source_summary,
        provider_label=provider_label,
        fallback_message=fallback_message,
        evidence_message=evidence_message,
        answer_quality_status=answer_quality_status,
        answer_quality_message=answer_quality_message,
        requires_review=requires_review,
        generation_complete=not generation_failed and not generation_incomplete,
        execution_steps=steps,
    )
    summary = TaskExecutionSummary(
        route={
            "source": str(routing.get("route_source", "local_fast")),
            "confidence": routing.get("route_confidence", 1.0),
            "course_id": result.course_id,
            "intent": result.intent,
        },
        agent_id=result.agent_id,
        agent_label=task_label,
        rag_mode=rag_mode,
        retrieval_policy=definition.retrieval_policy.policy_name,
        evidence_count=evidence_count,
        workflow_evidence_count=workflow_count,
        used_evidence_count=used_count,
        provider=result.provider,
        cloud_status=result.cloud_status,
        citation_status=citation_status,
        fallback=fallback,
        fallback_reason=result.fallback_reason,
        mock=mock,
        timings=timings,
    )
    return presentation, summary, evidence_view


def _evidence_view(
    evidence_items: list[KnowledgeHit],
    entered_ids: set[str],
    used_ids: set[str],
    rag_mode: RAGInteractionMode,
) -> list[EvidenceViewItem]:
    items: list[EvidenceViewItem] = []
    for hit in evidence_items:
        used = hit.evidence_id in used_ids
        role = (
            "method_reference"
            if rag_mode == RAGInteractionMode.METHOD_REFERENCE
            else "cited"
            if used
            else "supplementary"
        )
        items.append(
            EvidenceViewItem(
                evidence_id=hit.evidence_id,
                title=hit.title or hit.chapter or "课程资料",
                course_id=str(hit.course_id),
                course_name=hit.course_name,
                chapter=hit.chapter,
                section=hit.section,
                content_type=hit.content_type,
                summary=MATH_FORMATTER.process_markdown(
                    _clean_evidence_excerpt(hit.content[:320])
                ).markdown,
                source_ref=hit.source_ref,
                related_images=hit.related_images,
                entered_workflow=hit.evidence_id in entered_ids,
                used_by_answer=used,
                role=role,
            )
        )
    return items


def _runtime_knowledge_hits(result: AgentResult) -> list[KnowledgeHit]:
    """Recover evidence cards from a Runtime result without trusting free text."""

    knowledge = result.structured_result.get("knowledge", {})
    raw_hits = knowledge.get("hits", []) if isinstance(knowledge, dict) else []
    if not isinstance(raw_hits, list) or not raw_hits:
        raw_hits = result.structured_result.get("core_retrieval_summary", [])
    if not isinstance(raw_hits, list) or not raw_hits:
        evidence_packet = result.structured_result.get("evidence_packet", {})
        raw_hits = (
            evidence_packet.get("sources", [])
            if isinstance(evidence_packet, dict)
            else []
        )
    hits: list[KnowledgeHit] = []
    seen_ids: set[str] = set()
    for index, raw_hit in enumerate(raw_hits, start=1):
        if not isinstance(raw_hit, dict):
            continue
        source_ref = str(raw_hit.get("source_ref", ""))
        evidence_id = str(
            raw_hit.get("evidence_id")
            or raw_hit.get("source_id")
            or f"S{index}"
        )
        course_id = str(raw_hit.get("course_id") or result.course_id or "CT")
        content = str(
            raw_hit.get("content")
            or raw_hit.get("excerpt")
            or raw_hit.get("content_excerpt")
            or ""
        )
        raw_score = raw_hit.get("score")
        try:
            score = max(float(raw_score or 0), 0)
        except (TypeError, ValueError):
            score = 0.0
        payload = {
            "chunk_id": str(raw_hit.get("chunk_id") or ""),
            "evidence_id": evidence_id,
            "document_id": str(raw_hit.get("document_id") or ""),
            "course_id": course_id,
            "course_name": str(
                raw_hit.get("course_name") or COURSE_LABELS.get(course_id, course_id)
            ),
            "chapter": str(raw_hit.get("chapter") or ""),
            "section": str(raw_hit.get("section") or ""),
            "document_path": str(
                raw_hit.get("document_path") or source_ref or evidence_id
            ),
            "title": str(raw_hit.get("title") or raw_hit.get("chapter") or evidence_id),
            "content_type": str(raw_hit.get("content_type") or "unknown"),
            "content": content,
            "score": score,
            "source_ref": source_ref,
        }
        try:
            hit = KnowledgeHit.model_validate(payload)
        except (TypeError, ValueError):
            continue
        if hit.evidence_id and hit.evidence_id not in seen_ids:
            hits.append(hit)
            seen_ids.add(hit.evidence_id)
    return hits


def _execution_steps(
    result: AgentResult,
    bundle: WorkflowContextBundle | None,
    citation_status: str,
) -> list[dict[str, str]]:
    steps = [
        {"key": "understand", "label": "需求识别", "status": "completed"},
        {"key": "route", "label": "能力编排", "status": "completed"},
        {
            "key": "retrieval",
            "label": "资料准备",
            "status": "completed" if bundle else "skipped",
        },
    ]
    external = result.structured_result.get("external_retrieval", {})
    if isinstance(external, dict):
        external_status = str(external.get("status", "skipped"))
        steps.append(
            {
                "key": "external_retrieval",
                "label": "外部学术检索",
                "status": (
                    "completed"
                    if external_status in {"completed", "partial"}
                    else "failed"
                    if external_status == "failed"
                    else "skipped"
                ),
            }
        )
    pipeline = result.structured_result.get("pipeline_stages", [])
    if isinstance(pipeline, list) and len(pipeline) == 2:
        steps.extend(
            [
                {
                    "key": "pipeline_analysis",
                    "label": "数据分析",
                    "status": "completed",
                },
                {"key": "pipeline_writing", "label": "学术写作", "status": "completed"},
            ]
        )
    else:
        steps.append(
            {
                "key": "provider",
                "label": "内部协作",
                "status": "fallback" if result.fallback_used else "completed",
            }
        )
    model_execution = result.structured_result.get("model_execution", {})
    generation_failed = bool(
        isinstance(model_execution, dict)
        and model_execution.get("status") == "failed"
    )
    generation_incomplete = bool(
        isinstance(model_execution, dict)
        and model_execution.get("output_status") == "partial"
    )
    quality_gate = result.structured_result.get("quality_gate", {})
    quality_status = (
        str(quality_gate.get("status", "not_checked"))
        if isinstance(quality_gate, dict)
        else "not_checked"
    )
    steps.extend(
        [
            {
                "key": "validation",
                "label": "结果检查",
                "status": (
                    "failed"
                    if generation_failed or quality_status == "fail"
                    else "partial"
                    if generation_incomplete or quality_status == "partial"
                    else str(
                        result.structured_result.get("validation", {}).get(
                            "validation_status",
                            (
                                citation_status
                                if citation_status != "not_run"
                                else "passed"
                            ),
                        )
                    )
                ),
            },
            {
                "key": "result",
                "label": "回答生成",
                "status": (
                    "failed"
                    if generation_failed
                    else "partial"
                    if generation_incomplete
                    else "completed"
                ),
            },
        ]
    )
    return steps
