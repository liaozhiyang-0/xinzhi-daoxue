from app.agents import AgentRegistry
from app.contracts import (
    AgentRequest,
    AgentResult,
    Artifact,
    Intent,
    KnowledgeCourseId,
    KnowledgeHit,
    RAGInteractionMode,
    RetrievalContextPacket,
    WorkflowContextBundle,
)
from app.services.agent_result_governance import (
    AgentResultValidatorRegistry,
    BusinessResultRendererRegistry,
)
from app.services.math_formatting_service import MathFormattingService
from app.services.task_result_presentation import TaskResultPresentationService


def test_result_presentation_builds_views_and_updates_artifacts() -> None:
    registry = AgentRegistry()
    definition = registry.get("GENERAL_QUESTION_V1")
    request = AgentRequest(
        task_id="task-presentation",
        user_id="user-1",
        session_id="session-1",
        course_id="general",
        intent=Intent.GENERAL_QA,
        canonical_input={"question": "What is an agent?"},
        options={"debug": True},
    )
    result = AgentResult(
        agent_id=definition.agent_id,
        course_id=request.course_id,
        intent=request.intent.value,
        answer="An agent observes and acts.",
        provider="local_agent",
        artifacts=[
            Artifact(
                content={"answer": "An agent observes and acts."},
            )
        ],
    )
    validation = AgentResultValidatorRegistry().validate(
        definition, result, request, None
    )

    presented = TaskResultPresentationService(
        BusinessResultRendererRegistry(), MathFormattingService()
    ).apply(
        definition=definition,
        result=result,
        request=request,
        bundle=None,
        routing={},
        timings={},
        validation=validation,
    )

    assert presented.structured_result["presentation"]
    assert presented.structured_result["execution_summary"]
    assert presented.math_content is not None
    assert presented.artifacts[0].content["answer"] == presented.answer


def test_result_presentation_exposes_model_provider_behind_runtime_adapter() -> None:
    registry = AgentRegistry()
    definition = registry.get("ACADEMIC_PROBLEM_SOLVER")
    request = AgentRequest(
        task_id="task-presentation-generation-provenance",
        user_id="user-1",
        session_id="session-1",
        course_id="SS",
        intent=Intent.SOLVE_PROBLEM,
        canonical_input={"question": "求两个矩形信号的卷积"},
    )
    result = AgentResult(
        agent_id=definition.agent_id,
        course_id="SS",
        intent=request.intent.value,
        answer="y(t)=0",
        provider="local_graph",
        structured_result={
            "vision_execution": {
                "status": "completed",
                "provider": "dashscope",
                "model": "qwen3.8-max",
            },
            "model_execution": {
                "status": "completed",
                "provider": "dashscope",
                "model": "qwen3.8-max",
            },
        },
    )
    validation = AgentResultValidatorRegistry().validate(
        definition, result, request, None
    )

    presented = TaskResultPresentationService(
        BusinessResultRendererRegistry(), MathFormattingService()
    ).apply(
        definition=definition,
        result=result,
        request=request,
        bundle=None,
        routing={},
        timings={},
        validation=validation,
    )

    assert presented.structured_result["generation_provider"] == "dashscope"
    assert presented.structured_result["generation_model"] == "qwen3.8-max"
    assert presented.structured_result["generation_provenance"]["providers"] == [
        "dashscope"
    ]


def test_result_presentation_exposes_internal_agent_model_provenance() -> None:
    registry = AgentRegistry()
    definition = registry.get("TEACH_02_ASSIGNMENT_REVIEW_V1")
    request = AgentRequest(
        task_id="task-presentation-internal-provenance",
        user_id="user-1",
        session_id="session-1",
        course_id="AE",
        intent=Intent.ASSIGNMENT_REVIEW,
        canonical_input={"question": "检查学生作答"},
    )
    result = AgentResult(
        agent_id=definition.agent_id,
        course_id="AE",
        intent=request.intent.value,
        answer="需要教师复核。",
        provider="local_agent",
        structured_result={
            "internal_execution": {
                "provider": "dashscope",
                "model_route": "qwen3.6-flash",
                "status": "completed",
            }
        },
    )
    validation = AgentResultValidatorRegistry().validate(
        definition, result, request, None
    )

    presented = TaskResultPresentationService(
        BusinessResultRendererRegistry(), MathFormattingService()
    ).apply(
        definition=definition,
        result=result,
        request=request,
        bundle=None,
        routing={},
        timings={},
        validation=validation,
    )

    assert presented.structured_result["generation_provider"] == "dashscope"
    assert presented.structured_result["generation_model"] == "qwen3.6-flash"
    assert presented.structured_result["generation_provenance"]["executions"] == [
        {
            "stage": "internal_execution",
            "provider": "dashscope",
            "model": "qwen3.6-flash",
        }
    ]


def test_result_presentation_exposes_provider_and_models_lists() -> None:
    registry = AgentRegistry()
    definition = registry.get("TEACH_02_ASSIGNMENT_REVIEW_V1")
    request = AgentRequest(
        task_id="task-presentation-model-list-provenance",
        user_id="user-1",
        session_id="session-1",
        course_id="AE",
        intent=Intent.ASSIGNMENT_REVIEW,
        canonical_input={"question": "生成评分量规"},
    )
    result = AgentResult(
        agent_id=definition.agent_id,
        course_id="AE",
        intent=request.intent.value,
        answer="评分量规草稿。",
        provider="local_agent",
        structured_result={
            "model_execution": {
                "status": "success",
                "providers": ["dashscope"],
                "models": ["qwen3.5-flash"],
            }
        },
    )
    validation = AgentResultValidatorRegistry().validate(
        definition, result, request, None
    )

    presented = TaskResultPresentationService(
        BusinessResultRendererRegistry(), MathFormattingService()
    ).apply(
        definition=definition,
        result=result,
        request=request,
        bundle=None,
        routing={},
        timings={},
        validation=validation,
    )

    assert presented.structured_result["generation_provider"] == "dashscope"
    assert presented.structured_result["generation_model"] == "qwen3.5-flash"
    assert presented.structured_result["generation_provenance"]["executions"] == [
        {
            "stage": "model_execution",
            "provider": "dashscope",
            "model": "qwen3.5-flash",
        }
    ]


def test_result_presentation_exposes_knowledge_generation_provenance() -> None:
    registry = AgentRegistry()
    definition = registry.get("LEARN_01_LOCAL_RETRIEVAL_V1")
    request = AgentRequest(
        task_id="task-presentation-knowledge-provenance",
        user_id="user-1",
        session_id="session-1",
        course_id="AE",
        intent=Intent.LEARNING_ADVICE,
        canonical_input={"question": "规划电源训练"},
    )
    result = AgentResult(
        agent_id=definition.agent_id,
        course_id="AE",
        intent=request.intent.value,
        answer="学习路径草稿。",
        provider="dashscope",
        structured_result={"generation_model": "qwen3.5-flash"},
    )
    validation = AgentResultValidatorRegistry().validate(
        definition, result, request, None
    )

    presented = TaskResultPresentationService(
        BusinessResultRendererRegistry(), MathFormattingService()
    ).apply(
        definition=definition,
        result=result,
        request=request,
        bundle=None,
        routing={},
        timings={},
        validation=validation,
    )

    assert presented.structured_result["generation_provider"] == "dashscope"
    assert presented.structured_result["generation_model"] == "qwen3.5-flash"


def test_result_presentation_synchronizes_bundle_evidence_metadata() -> None:
    registry = AgentRegistry()
    definition = registry.get("LEARN_01_KNOWLEDGE_QA_V1")
    hit = KnowledgeHit(
        evidence_id="S1",
        course_id=KnowledgeCourseId.CIRCUIT_THEORY,
        course_name="电路理论",
        chapter="第七章",
        document_path="CT/chapter.md",
        title="电容电压连续性",
        content_type="mixed",
        content="u(t)=u(t0)+(1/C)∫i dt",
        score=0.9,
        source_ref="kb://CT/chapter.md#chunk-1",
    )
    packet = RetrievalContextPacket(
        query="解释电容电压连续性",
        course_id="CT",
        intent="explain_concept",
        evidence=[hit],
        source_refs=[hit.source_ref],
        evidence_status="partial",
        max_context_chars=6_000,
        rag_status="ready",
        index_version="test-index",
    )
    bundle = WorkflowContextBundle.from_packet(
        packet,
        request_id="request-presentation-bundle",
        task_id="task-presentation-bundle",
        agent_id=definition.agent_id,
        retrieval_policy="learn_knowledge_qa",
        rag_mode=RAGInteractionMode.GROUNDED_GENERATION,
    )
    request = AgentRequest(
        task_id=bundle.task_id,
        user_id="user-1",
        session_id="session-1",
        course_id="CT",
        intent=Intent.EXPLAIN_CONCEPT,
        canonical_input={"question": "解释电容电压连续性"},
    )
    result = AgentResult(
        agent_id=definition.agent_id,
        course_id="CT",
        intent=request.intent.value,
        answer="电容电压在有限电流条件下连续。",
        provider="local",
        citations=[hit.source_ref],
        evidence_status="partial",
        structured_result={
            "evidence_packet": {
                "version": "v1",
                "retrieval_status": "not_run",
                "evidence_sufficiency": "unavailable",
                "sources": [],
            }
        },
    )
    validation = AgentResultValidatorRegistry().validate(
        definition, result, request, bundle
    )

    presented = TaskResultPresentationService(
        BusinessResultRendererRegistry(), MathFormattingService()
    ).apply(
        definition=definition,
        result=result,
        request=request,
        bundle=bundle,
        routing={},
        timings={},
        validation=validation,
    )

    assert presented.structured_result["knowledge_hit_count"] == 1
    evidence_packet = presented.structured_result["evidence_packet"]
    assert evidence_packet["retrieval_status"] == "ready"
    assert evidence_packet["evidence_sufficiency"] == "partial"
    assert len(evidence_packet["sources"]) == 1


def test_result_presentation_rebuilds_legacy_evidence_packet_from_cards() -> None:
    registry = AgentRegistry()
    definition = registry.get("LEARN_01_KNOWLEDGE_QA_V1")
    hit = KnowledgeHit(
        evidence_id="S1",
        course_id=KnowledgeCourseId.CIRCUIT_THEORY,
        course_name="电路理论",
        chapter="第七章",
        document_path="CT/chapter.md",
        title="电容电压连续性",
        content_type="mixed",
        content="u(t)=u(t0)+(1/C)∫i dt",
        score=0.9,
        source_ref="kb://CT/chapter.md#chunk-1",
    )
    request = AgentRequest(
        task_id="task-presentation-legacy",
        user_id="user-1",
        session_id="session-1",
        course_id="CT",
        intent=Intent.EXPLAIN_CONCEPT,
        canonical_input={"question": "解释电容电压连续性"},
    )
    result = AgentResult(
        agent_id=definition.agent_id,
        course_id="CT",
        intent=request.intent.value,
        answer="电容电压在有限电流条件下连续。",
        provider="local",
        citations=[hit.source_ref],
        rag_status="ready",
        evidence_status="partial",
        structured_result={
            "core_retrieval_summary": [hit.model_dump(mode="json")],
            "evidence_packet": {
                "version": "v1",
                "retrieval_status": "not_run",
                "evidence_sufficiency": "unavailable",
                "sources": [],
            },
        },
    )
    validation = AgentResultValidatorRegistry().validate(
        definition, result, request, None
    )

    presented = TaskResultPresentationService(
        BusinessResultRendererRegistry(), MathFormattingService()
    ).apply(
        definition=definition,
        result=result,
        request=request,
        bundle=None,
        routing={},
        timings={},
        validation=validation,
    )

    assert presented.structured_result["knowledge_hit_count"] == 1
    evidence_packet = presented.structured_result["evidence_packet"]
    assert evidence_packet["retrieval_status"] == "ready"
    assert evidence_packet["evidence_sufficiency"] == "partial"
    assert len(evidence_packet["sources"]) == 1


def test_result_presentation_surfaces_math_formatting_warnings() -> None:
    registry = AgentRegistry()
    definition = registry.get("GENERAL_QUESTION_V1")
    request = AgentRequest(
        task_id="task-presentation-math-warning",
        user_id="user-1",
        session_id="session-1",
        course_id="general",
        intent=Intent.GENERAL_QA,
        canonical_input={"question": "请检查公式"},
    )
    result = AgentResult(
        agent_id=definition.agent_id,
        course_id=request.course_id,
        intent=request.intent.value,
        answer=r"危险公式：$\input{student.tex}$",
        provider="local_agent",
    )
    validation = AgentResultValidatorRegistry().validate(
        definition, result, request, None
    )

    presented = TaskResultPresentationService(
        BusinessResultRendererRegistry(), MathFormattingService()
    ).apply(
        definition=definition,
        result=result,
        request=request,
        bundle=None,
        routing={},
        timings={},
        validation=validation,
    )

    assert any(
        warning.startswith("math_formatting:dangerous_command:input")
        for warning in presented.warnings
    )
    assert presented.structured_result["math_quality"]["status"] == "blocked"
    assert presented.structured_result["math_quality"]["publishable"] is False
    assert presented.structured_result["presentation"]["requires_review"] is True
    assert presented.structured_result["presentation"]["answer_quality_status"] == (
        "needs_review"
    )


def test_math_quality_blocks_scenario_contract_publishability() -> None:
    registry = AgentRegistry()
    definition = registry.get("GENERAL_QUESTION_V1")
    request = AgentRequest(
        task_id="task-presentation-math-contract",
        user_id="user-1",
        session_id="session-1",
        course_id="general",
        intent=Intent.GENERAL_QA,
        canonical_input={"question": "请检查公式"},
    )
    result = AgentResult(
        agent_id=definition.agent_id,
        course_id=request.course_id,
        intent=request.intent.value,
        answer=r"危险公式：$\input{student.tex}$",
        provider="local_agent",
        structured_result={
            "scenario_contract": {
                "status": "completed",
                "quality_gaps": [],
                "model_synthesis": {"status": "completed", "publishable": True},
            }
        },
    )
    validation = AgentResultValidatorRegistry().validate(
        definition, result, request, None
    )

    presented = TaskResultPresentationService(
        BusinessResultRendererRegistry(), MathFormattingService()
    ).apply(
        definition=definition,
        result=result,
        request=request,
        bundle=None,
        routing={},
        timings={},
        validation=validation,
    )

    contract = presented.structured_result["scenario_contract"]
    assert contract["status"] == "completed_with_gaps"
    assert "math_rendering" in contract["quality_gaps"]
    assert contract["model_synthesis"]["publishable"] is False
    assert any(
        risk.startswith("数学输出需要复核") for risk in presented.remaining_risks
    )


def test_formula_output_contract_flows_into_presentation_and_scenario_contract(
) -> None:
    registry = AgentRegistry()
    definition = registry.get("ACADEMIC_PROBLEM_SOLVER")
    request = AgentRequest(
        task_id="task-presentation-formula-contract",
        user_id="user-1",
        session_id="session-1",
        course_id="AE",
        intent=Intent.SOLVE_PROBLEM,
        canonical_input={"question": "分析闭环带宽、相位和幅值"},
        options={
            "formula_output_contract": {
                "minimum_equations": 2,
                "require_step_expressions": True,
                "required_units": ["Hz"],
                "required_markers": ["闭环带宽", "相位", "幅值"],
                "require_math_rendering": True,
            }
        },
    )
    result = AgentResult(
        agent_id=definition.agent_id,
        course_id=request.course_id,
        intent=request.intent.value,
        answer="缺少结构化步骤。",
        provider="local_agent",
        structured_result={
            "scenario_contract": {
                "status": "completed",
                "quality_gaps": [],
                "model_synthesis": {"status": "completed", "publishable": True},
            },
            "key_equations": ["A_f=A/(1+AF)"],
        },
    )
    validation = AgentResultValidatorRegistry().validate(
        definition, result, request, None
    )

    presented = TaskResultPresentationService(
        BusinessResultRendererRegistry(), MathFormattingService()
    ).apply(
        definition=definition,
        result=result,
        request=request,
        bundle=None,
        routing={},
        timings={},
        validation=validation,
    )

    contract = presented.structured_result["scenario_contract"]
    formula_contract = presented.structured_result["formula_output_contract"]
    assert formula_contract["status"] == "blocked"
    assert contract["status"] == "completed_with_gaps"
    assert "formula_output" in contract["quality_gaps"]
    assert contract["model_synthesis"]["publishable"] is False
    assert presented.structured_result["presentation"]["requires_review"] is True
