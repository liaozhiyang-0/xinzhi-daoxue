from __future__ import annotations

import os

import pytest
from app.agents import AgentRegistry
from app.contracts import AgentRequest, Intent, KnowledgeHit, RetrievalContextPacket
from app.core.config import Settings
from app.core.errors import XingchenHttpError
from app.providers.xingchen import XingchenCloudProvider
from app.services.citation_validator import CitationValidator

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_REAL_XINGCHEN_TESTS") != "1",
        reason="set RUN_REAL_XINGCHEN_TESTS=1 to consume real Xingchen quota",
    ),
]


def real_settings() -> Settings:
    # tests/conftest.py forces XINGCHEN_ENABLED=false for the normal suite.
    return Settings(xingchen_enabled=True)


def request_with_evidence(
    course_id: str,
    question: str,
    evidence_text: str,
    *,
    intent: Intent = Intent.EXPLAIN_CONCEPT,
) -> tuple[AgentRequest, RetrievalContextPacket]:
    hit = KnowledgeHit(
        evidence_id="S1",
        course_id=course_id,
        course_name={"CT": "电路理论", "AE": "模拟电子技术", "DE": "数字电子技术"}[
            course_id
        ],
        chapter="真实测试证据",
        document_path="real-test.md",
        title="真实测试证据",
        content_type="concept",
        content=evidence_text,
        score=0.9,
        source_ref=f"kb://{course_id}/real-test.md#chunk-1",
    )
    packet = RetrievalContextPacket(
        query=question,
        course_id=course_id,
        intent=intent.value,
        evidence=[hit],
        source_refs=[hit.source_ref],
        evidence_status="partial",
        max_context_chars=2000,
        rag_status="ready",
    )
    context = packet.to_retrieved_context()
    packet_payload = packet.model_dump(mode="json")
    packet_payload["formatted_context"] = context
    request = AgentRequest(
        task_id=f"real-{course_id.lower()}-{intent.value}",
        session_id="real-xingchen-tests",
        user_id="real-xingchen-tests",
        course_id=course_id,
        intent=intent,
        canonical_input={"question": question},
        options={
            "request_id": f"real-{course_id.lower()}-{intent.value}",
            "retrieved_context": context,
            "retrieval_context_packet": packet_payload,
            "response_depth": "brief",
        },
    )
    return request, packet


@pytest.mark.parametrize(
    ("course_id", "question", "evidence"),
    [
        ("CT", "为什么电容电压不能突变？", "电容电流有限时，电容电压连续。"),
        (
            "AE",
            "为什么负反馈能稳定放大倍数？",
            "深度负反馈时闭环增益主要由反馈网络决定。",
        ),
        ("DE", "锁存器和触发器有什么区别？", "锁存器电平敏感，触发器通常边沿敏感。"),
    ],
)
async def test_real_learn_uses_s1_and_roundtrips_request_id(
    course_id: str,
    question: str,
    evidence: str,
) -> None:
    settings = real_settings()
    request, packet = request_with_evidence(course_id, question, evidence)

    result = await XingchenCloudProvider(settings, registry=AgentRegistry()).run(
        "LEARN_01_KNOWLEDGE_QA_V1", request
    )
    validation = CitationValidator().validate(
        result.answer,
        packet,
        declared_references=result.structured_result.get("source_references", []),
    )

    assert result.provider == "xingchen"
    assert result.structured_result["status"] in {"success", "partial"}
    assert result.structured_result["request_id"] == request.task_id
    assert "S1" in result.structured_result["source_references"]
    assert validation.valid


async def test_real_learn_marks_complete_problem_as_misrouted() -> None:
    request, _packet = request_with_evidence(
        "CT",
        "一个含受控源的一阶电路，请完整列方程并求全响应。",
        "这是完整求解任务，不应由知识问答工作流执行。",
        intent=Intent.SOLVE_PROBLEM,
    )

    result = await XingchenCloudProvider(real_settings(), registry=AgentRegistry()).run(
        "LEARN_01_KNOWLEDGE_QA_V1", request
    )

    assert result.structured_result["status"] == "misrouted"
    assert result.structured_result["intent"] == "solve_problem"


async def test_real_learn_handles_empty_context_without_fake_citation() -> None:
    request = AgentRequest(
        task_id="real-no-evidence",
        session_id="real-xingchen-tests",
        user_id="real-xingchen-tests",
        course_id="CT",
        intent=Intent.GENERAL_QA,
        canonical_input={"question": "请解释一个教材中没有直接证据的新器件。"},
        options={"request_id": "real-no-evidence", "retrieved_context": ""},
    )

    result = await XingchenCloudProvider(real_settings(), registry=AgentRegistry()).run(
        "LEARN_01_KNOWLEDGE_QA_V1", request
    )

    assert result.structured_result["request_id"] == request.task_id
    assert result.structured_result["source_references"] == []


async def test_real_invalid_flow_returns_explicit_error() -> None:
    settings = real_settings().model_copy(
        update={"xingchen_knowledge_qa_flow_id": "invalid-real-test-flow"}
    )
    request, _packet = request_with_evidence(
        "CT", "什么是KCL？", "KCL描述结点电流的代数和为零。"
    )

    with pytest.raises(XingchenHttpError):
        await XingchenCloudProvider(settings, registry=AgentRegistry()).run(
            "LEARN_01_KNOWLEDGE_QA_V1", request
        )
