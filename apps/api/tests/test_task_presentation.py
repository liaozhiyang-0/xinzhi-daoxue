from app.agents import AgentRegistry
from app.contracts import (
    AgentRequest,
    AgentResult,
    Intent,
    KnowledgeCourseId,
    KnowledgeHit,
    RAGInteractionMode,
    RetrievalContextPacket,
    WorkflowContextBundle,
)
from app.services.task_presentation import build_task_views
from app.services.task_runner import TaskRunner


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


def test_learn_presentation_uses_only_validated_evidence() -> None:
    definition = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="xingchen",
        course_id="CT",
        intent="explain_concept",
        answer="因为电荷变化需要有限时间。[S1]",
        cloud_status="cloud_success",
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


def test_solver_evidence_is_labeled_method_reference_not_answer_basis() -> None:
    definition = AgentRegistry().get("SOLVER_CT_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="xingchen",
        course_id="CT",
        intent="solve_problem",
        answer="回路电流为 2 A。",
        cloud_status="cloud_success",
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
        "云端响应超时，本次已切换到本地安全后备结果。"
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


def test_lesson_fallback_keeps_retrieved_materials_visible_but_not_cited() -> None:
    definition = AgentRegistry().get("TEACH_01_LESSON_PREP_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        course_id="CT",
        intent="lesson_prep",
        answer="本地可编辑教案框架",
        fallback_used=True,
        fallback_reason="xingchen_response_parse_error",
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
    assert "未将其声明为直接生成依据" in presentation.evidence_message
    assert "格式校验未通过" in presentation.fallback_message
    assert presentation.provider_label == "本地安全后备"
    assert summary.used_evidence_count == 0
    assert evidence[0].used_by_answer is False


def test_lesson_fallback_returns_an_actual_editable_structure() -> None:
    request = AgentRequest(
        session_id="session-test",
        user_id="teacher-test",
        user_role="teacher",
        scene="teaching",
        course_id="CT",
        intent=Intent.LESSON_PREP,
        canonical_input={"text": "请设计电容电压连续性教案"},
    )

    answer, data = TaskRunner._lesson_prep_fallback_template(request)

    assert "本地教案框架" in answer
    assert "电容电压连续性" in answer
    assert data["learning_objectives"]
    assert data["lesson_flow"]
    assert data["activities"]
    assert data["formative_assessment"]


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
