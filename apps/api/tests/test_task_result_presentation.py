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
