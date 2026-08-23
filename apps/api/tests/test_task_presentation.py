from app.agents import AgentRegistry
from app.contracts import (
    AgentResult,
    KnowledgeCourseId,
    KnowledgeHit,
    RAGInteractionMode,
    RetrievalContextPacket,
    WorkflowContextBundle,
)
from app.services.task_presentation import _clean_evidence_excerpt, build_task_views


def hit(evidence_id: str = "S1") -> KnowledgeHit:
    return KnowledgeHit(
        evidence_id=evidence_id,
        course_id=KnowledgeCourseId.CIRCUIT_THEORY,
        course_name="电路理论",
        chapter="动态电路",
        document_path="CT/chapter.md",
        title="电容电压连续性",
        content_type="concept",
        content="电容电压在有限电流条件下不能突变。",
        score=0.9,
        source_ref="kb://CT/chapter.md#chunk-1",
    )


def test_evidence_excerpt_removes_orphaned_formula_tail_and_dividers() -> None:
    excerpt = (
        "Cu} = \\varepsilon \\left( t\\right) }\\right)\n\\]\n---\n"
        "⑤ 工程上认为电容的电压总是连续变化的。"
    )

    cleaned = _clean_evidence_excerpt(excerpt)

    assert "Cu}" not in cleaned
    assert r"\]" not in cleaned
    assert "---" not in cleaned
    assert "工程上认为电容的电压总是连续变化的" in cleaned


def test_evidence_excerpt_removes_embedded_images_and_clipped_closers() -> None:
    excerpt = (
        r"\] \[P = UI = I^2R\]"
        "\n![figure-1.png](images/figure-1.png)"
        r"\n0 \) , indicating conservation of power."
    )

    cleaned = _clean_evidence_excerpt(excerpt)

    assert "![" not in cleaned
    assert "figure-1.png" in cleaned
    assert not cleaned.startswith(r"\]")
    assert r"0 \)" not in cleaned


def test_shared_evidence_excerpt_removes_clipped_prefix_and_ocr_marker() -> None:
    from app.services.evidence_excerpt import clean_evidence_excerpt

    excerpt = (
        r"t\right) \mathrm{C}\;\left( {\text{ 或 }q = {Cu} = "
        r"\varepsilon \left( t\right) }\right) \] ---"
        " ⑤ 工程上认为电容的电压总是连续变化的。因为实际电路中不可能出现无穷大的电流。"
    )
    cleaned = clean_evidence_excerpt(excerpt)
    assert cleaned.startswith("工程上认为电容的电压总是连续变化的")
    assert r"\right" not in cleaned
    assert "---" not in cleaned
    assert r"\mat" not in clean_evidence_excerpt(excerpt, max_chars=120)


def test_display_evidence_excerpt_preserves_formula_and_markdown_source() -> None:
    from app.services.evidence_excerpt import display_evidence_excerpt

    excerpt = (
        r"\left( {u}_{0} \right) = \frac{1}{C}"
        "\n![figure-1](images/figure-1.png)\n---\n"
        "特殊字符：αβ ≤ ≥"
    )

    assert display_evidence_excerpt(excerpt) == excerpt


def test_display_evidence_excerpt_does_not_cut_formula_fragments() -> None:
    from app.services.evidence_excerpt import display_evidence_excerpt

    excerpt = "前置说明 " + ("背景文本 " * 80) + r"\[V = \frac{1}{C} q\] 后续原文"

    assert len(excerpt) > 360
    assert display_evidence_excerpt(excerpt, max_chars=360) == excerpt


def test_display_evidence_excerpt_still_bounds_plain_text() -> None:
    from app.services.evidence_excerpt import display_evidence_excerpt

    excerpt = "普通资料 " * 200

    result = display_evidence_excerpt(excerpt, max_chars=360)

    assert len(result) <= 361
    assert result.endswith("…")
def bundle(mode: RAGInteractionMode) -> WorkflowContextBundle:
    packet = RetrievalContextPacket(
        query="为什么电容电压不能突变",
        course_id="CT",
        intent="explain_concept",
        evidence=[hit()],
        source_refs=["kb://CT/chapter.md#chunk-1"],
        evidence_status="sufficient",
        max_context_chars=6000,
        rag_status="ready",
        index_version="test-index",
        retrieval_trace_id="trace-test",
    )
    return WorkflowContextBundle.from_packet(
        packet,
        request_id="request-test",
        task_id="task-test",
        agent_id="LEARN_01_KNOWLEDGE_QA_V1",
        retrieval_policy="learn_knowledge_qa",
        rag_mode=mode,
    )


def test_workflow_context_bundle_keeps_one_context_and_evidence_view() -> None:
    context = bundle(RAGInteractionMode.GROUNDED_GENERATION)
    assert context.retrieved_context.startswith("evidence_status: sufficient")
    assert context.workflow_evidence_ids == ["S1"]
    assert context.evidence_items[0].source_ref.startswith("kb://CT/")


def test_agent_rag_modes_preserve_learn_and_solver_boundaries() -> None:
    registry = AgentRegistry()
    assert (
        registry.get("LEARN_01_KNOWLEDGE_QA_V1").retrieval_policy.interaction_mode
        == "grounded_generation"
    )
    assert (
        registry.get("SOLVER_CT_V1").retrieval_policy.interaction_mode
        == "method_reference"
    )


def test_presentation_prefers_capability_profile_over_agent_id() -> None:
    definition = AgentRegistry().get("GENERAL_QUESTION_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        course_id="CT",
        intent="lesson_prep",
        answer="教案草稿",
        structured_result={
            "presentation_profile": {
                "capability_id": "teaching.lesson_design"
            }
        },
    )

    presentation, summary, _ = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={},
        timings={},
    )

    assert presentation.title == "教案设计"
    assert summary.agent_label == "教案设计"


def test_learn_presentation_uses_only_validated_evidence() -> None:
    definition = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        course_id="CT",
        intent="explain_concept",
        answer="因为电荷变化需要有限时间。[S1]",
        cloud_status="not_required",
        evidence_status="sufficient",
        structured_result={
            "citation_validation": {
                "status": "passed",
                "valid_ids": ["S1"],
                "invalid_ids": [],
            }
        },
    )
    context = bundle(RAGInteractionMode.GROUNDED_GENERATION)
    presentation, summary, evidence = build_task_views(
        definition=definition,
        result=result,
        bundle=context,
        routing={"route_source": "local_fast", "route_confidence": 0.98},
        timings={"total_ms": 120},
    )
    assert presentation.source_summary == "使用 1 条课程资料"
    assert summary.used_evidence_count == 1
    assert evidence[0].used_by_answer is True
    assert evidence[0].role == "cited"


def test_runtime_knowledge_result_populates_evidence_view_without_bundle() -> None:
    definition = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    runtime_hit = hit()
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local_agent",
        course_id="CT",
        intent="explain_concept",
        answer="电容电压不能突变。[S1]",
        citations=[runtime_hit.source_ref],
        evidence_status="sufficient",
        structured_result={
            "knowledge": {"hits": [runtime_hit.model_dump(mode="json")]},
            "verified_evidence_ids": ["S1"],
        },
    )

    presentation, summary, evidence = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={"route_source": "runtime"},
        timings={"total_ms": 120},
    )

    assert summary.evidence_count == 1
    assert summary.workflow_evidence_count == 1
    assert summary.used_evidence_count == 1
    assert presentation.source_summary == "使用 1 条课程资料"
    assert evidence[0].evidence_id == "S1"
    assert evidence[0].used_by_answer is True
    assert evidence[0].entered_workflow is True
    assert presentation.execution_steps[2]["status"] == "completed"


def test_runtime_knowledge_result_does_not_render_rejected_candidate_hits() -> None:
    definition = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    rejected_hit = hit()
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        course_id="CT",
        intent="explain_concept",
        answer="当前问题没有足够的相关课程依据。",
        evidence_status="insufficient",
        structured_result={
            "knowledge": {
                "hits": [],
                "candidate_hits": [rejected_hit.model_dump(mode="json")],
            },
            "warnings": ["检索片段与问题主题不一致"],
        },
    )

    presentation, summary, evidence = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={"route_source": "runtime"},
        timings={"total_ms": 120},
    )

    assert evidence == []
    assert summary.evidence_count == 0
    assert "课程资料" in presentation.source_summary


def test_knowledge_without_evidence_does_not_claim_model_generation() -> None:
    definition = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        course_id="CT",
        intent="explain_concept",
        answer="当前课程资料不足。",
        evidence_status="insufficient",
        structured_result={"mode": "retrieval_only"},
    )

    presentation, _, _ = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={"route_source": "runtime"},
        timings={"total_ms": 120},
    )

    assert presentation.status_label == "资料不足，待补充"
    assert presentation.answer_quality_status == "needs_review"
    assert presentation.generation_complete is False
    assert presentation.execution_steps[-1]["status"] == "partial"


def test_runtime_generation_provenance_overrides_evidence_skip_message() -> None:
    definition = AgentRegistry().get("TEACH_01_LESSON_PREP_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local_agent",
        course_id="CT",
        intent="lesson_prep",
        answer="已生成教案草稿，但课程证据仍需教师确认。",
        evidence_status="insufficient",
        structured_result={
            "generation_provider": "dashscope",
            "generation_model": "qwen3.5-flash",
            "quality_gate": {"status": "partial"},
        },
    )

    presentation, _, _ = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={"route_source": "runtime"},
        timings={"total_ms": 120},
    )

    assert presentation.generation_complete is True
    assert "未生成模型答案" not in presentation.answer_quality_message
    assert presentation.execution_steps[-1]["status"] == "completed"


def test_runtime_core_retrieval_summary_populates_evidence_view() -> None:
    definition = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="iflytek_spark",
        course_id="CT",
        intent="explain_concept",
        answer="电容电压不能突变。[S1]",
        citations=["kb://CT/课本/基础篇/第七章.md#chunk-1"],
        evidence_status="sufficient",
        structured_result={
            "core_retrieval_summary": [
                {
                    "evidence_id": "S1",
                    "source_ref": "kb://CT/课本/基础篇/第七章.md#chunk-1",
                    "chapter": "动态电路",
                    "title": "电容电压连续性",
                    "excerpt": "电容两端电压不能发生突变。",
                    "score": "0.91",
                }
            ],
            "verified_evidence_ids": ["S1"],
        },
    )

    presentation, summary, evidence = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={"route_source": "runtime"},
        timings={"total_ms": 120},
    )

    assert summary.evidence_count == 1
    assert summary.workflow_evidence_count == 1
    assert summary.used_evidence_count == 1
    assert presentation.source_summary == "使用 1 条课程资料"
    assert evidence[0].title == "电容电压连续性"
    assert evidence[0].used_by_answer is True
    assert evidence[0].entered_workflow is True


def test_solver_evidence_is_labeled_method_reference_not_answer_basis() -> None:
    definition = AgentRegistry().get("SOLVER_CT_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        course_id="CT",
        intent="solve_problem",
        answer="回路电流为 2 A。",
        cloud_status="not_required",
    )
    context = bundle(RAGInteractionMode.METHOD_REFERENCE)
    presentation, summary, evidence = build_task_views(
        definition=definition,
        result=result,
        bundle=context,
        routing={},
        timings={"total_ms": 90},
    )
    assert summary.rag_mode == RAGInteractionMode.METHOD_REFERENCE
    assert summary.workflow_evidence_count == 0
    assert "仅作方法参考" in presentation.evidence_message
    assert evidence[0].role == "method_reference"
    assert evidence[0].entered_workflow is False


def test_fallback_and_mock_presentation_are_explicit() -> None:
    definition = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="mock",
        course_id="AE",
        intent="general_qa",
        answer="开发态结果",
        fallback_used=True,
        fallback_reason="provider_timeout",
        mock_used=True,
    )
    presentation, summary, _ = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={},
        timings={},
    )
    assert presentation.status_label == "开发演示"
    assert presentation.provider_label == "开发态 Mock"
    assert presentation.fallback_message == (
        "本地 Runtime 响应超时，已保留安全后备结果。"
    )
    assert "provider_timeout" not in presentation.fallback_message
    assert summary.mock is True


def test_incomplete_model_generation_is_not_labeled_completed() -> None:
    definition = AgentRegistry().get("ACADEMIC_PROBLEM_SOLVER")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local_graph",
        course_id="CT",
        intent="solve_problem",
        answer="已返回可用的前半部分。",
        structured_result={
            "model_execution": {
                "status": "partial",
                "output_status": "partial",
            }
        },
    )

    presentation, _, _ = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={},
        timings={},
    )

    assert presentation.status_label == "回答未完整"
    assert presentation.answer_quality_status == "incomplete"
    assert presentation.requires_review is True
    assert presentation.generation_complete is False
    assert presentation.execution_steps[-1]["status"] == "partial"


def test_failed_model_generation_is_not_labeled_completed() -> None:
    definition = AgentRegistry().get("ACADEMIC_PROBLEM_SOLVER")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local_graph",
        course_id="CT",
        intent="solve_problem",
        answer="当前仅保留确定性求解图的占位结果。",
        structured_result={
            "model_execution": {
                "status": "failed",
                "error_type": "model_timeout",
            }
        },
    )

    presentation, _, _ = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={},
        timings={},
    )

    assert presentation.status_label == "生成失败"
    assert presentation.answer_quality_status == "generation_failed"
    assert presentation.requires_review is True
    assert "模型响应超时" in presentation.fallback_message
    assert "确定性占位结果" not in presentation.fallback_message


def test_quality_gate_and_fallback_are_visible_to_workspace() -> None:
    definition = AgentRegistry().get("ACADEMIC_PROBLEM_SOLVER")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local_graph",
        course_id="SS",
        intent="solve_problem",
        answer="已生成答案。",
        fallback_used=True,
        fallback_reason="model_provider_unavailable",
        structured_result={
            "model_execution": {
                "status": "completed",
                "output_status": "complete",
            },
            "quality_gate": {"status": "partial"},
        },
    )

    presentation, _, _ = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={},
        timings={},
    )

    assert presentation.status_label == "建议复核"
    assert presentation.answer_quality_status == "needs_review"
    assert presentation.requires_review is True
    assert "确定性验证" in presentation.answer_quality_message
    assert presentation.execution_steps[-2]["status"] == "partial"


def test_governance_validation_issue_is_visible_in_answer_quality() -> None:
    definition = AgentRegistry().get("TEACH_02_ASSIGNMENT_REVIEW_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local_agent",
        course_id="AE",
        intent="assignment_review",
        answer="需要教师复核。",
        structured_result={
            "validation": {
                "validation_status": "warning",
                "validation_issues": ["semantic_conflict"],
            }
        },
    )

    presentation, _, _ = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={},
        timings={},
    )

    assert presentation.answer_quality_status == "needs_review"
    assert presentation.requires_review is True
    assert "semantic_conflict" in presentation.answer_quality_message


def test_lesson_fallback_keeps_retrieved_materials_visible_but_not_cited() -> None:
    definition = AgentRegistry().get("TEACH_01_LESSON_PREP_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        course_id="CT",
        intent="lesson_prep",
        answer="本地可编辑教案框架",
        fallback_used=True,
        fallback_reason="provider_response_parse_error",
        evidence_status="sufficient",
    )
    context = bundle(RAGInteractionMode.GROUNDED_GENERATION)

    presentation, summary, evidence = build_task_views(
        definition=definition,
        result=result,
        bundle=context,
        routing={},
        timings={},
    )

    assert presentation.source_summary == "已检索 1 条课程资料"
    assert "后备模型生成" in presentation.evidence_message
    assert "格式校验未通过" in presentation.fallback_message
    assert presentation.provider_label == "本地安全后备"
    assert summary.used_evidence_count == 0
    assert evidence[0].used_by_answer is False



def test_research_presentation_distinguishes_failed_external_search() -> None:
    definition = AgentRegistry().get("RESEARCH_01_ACADEMIC_SEARCH_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local_agent",
        course_id="CT",
        intent="general_qa",
        answer="当前没有获得可核验的外部科研证据。",
        structured_result={
            "external_retrieval": {
                "status": "failed",
                "provider_status": {"arxiv": "completed"},
                "warnings": ["paper review timed out"],
            }
        },
    )

    presentation, _, _ = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={},
        timings={},
    )

    assert presentation.source_summary == "外部检索未形成可展示证据"
    assert "已执行论文、报道等外部检索" in presentation.evidence_message


def test_research_presentation_keeps_local_answer_when_external_evidence_is_empty(
) -> None:
    definition = AgentRegistry().get("RESEARCH_01_ACADEMIC_SEARCH_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local_agent",
        course_id="CT",
        intent="general_qa",
        answer="科研前沿本地知识初步回答",
        structured_result={
            "answer_mode": "local_knowledge_fallback",
            "external_retrieval": {
                "status": "failed",
                "warnings": ["provider unavailable"],
            },
            "model_execution": {"status": "fallback", "model_calls": 0},
        },
    )

    presentation, _, _ = build_task_views(
        definition=definition,
        result=result,
        bundle=None,
        routing={},
        timings={},
    )

    assert presentation.source_summary == "本地知识初步回答"
    assert presentation.answer_quality_status == "provisional"
    assert "科研子问题" in presentation.evidence_message
