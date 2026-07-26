from __future__ import annotations

import json

from app.agents import AgentRegistry
from app.contracts import AgentRequest, KnowledgeHit, RetrievalContextPacket
from app.core.config import Settings
from app.providers.xingchen import build_workflow_payload, standardize_answer
from app.services.citation_validator import CitationValidator
from app.services.query_rewrite import rewrite_retrieval_query


def test_learn_registry_is_published_with_complete_io_mapping() -> None:
    learner = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")

    assert learner.enabled
    assert learner.publication_status == "published"
    assert set(learner.input_mapping) == {
        "text",
        "question",
        "course_id",
        "intent",
        "retrieved_context",
        "previous_answer_summary",
        "conversation_summary",
        "response_depth",
        "request_id",
    }
    assert learner.output_mapping["source_references"] == "source_references_json"


def test_learn_payload_uses_strings_and_separate_retrieval_context() -> None:
    settings = Settings(app_env="test", _env_file=None)
    learner = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    request = AgentRequest(
        task_id="req-contract",
        session_id="session",
        user_id="user",
        course_id="AE",
        intent="explain_concept",
        canonical_input={"question": "虚短和虚断是什么？"},
        options={
            "retrieved_context": "[S1]\n来源：kb://AE/chapter.md#chunk-1",
            "conversation_summary": "运算放大器",
            "response_depth": "deep",
        },
    )

    payload = build_workflow_payload(
        settings,
        request,
        definition=learner,
        flow_id="configured-flow",
    )

    assert payload["parameters"]["AGENT_USER_INPUT"] == "虚短和虚断是什么？"
    assert payload["parameters"]["question"] == "虚短和虚断是什么？"
    assert payload["parameters"]["course_id"] == "AE"
    assert payload["parameters"]["retrieved_context"].startswith("[S1]")
    assert payload["parameters"]["request_id"] == "req-contract"
    assert all(isinstance(value, str) for value in payload["parameters"].values())


def test_learn_output_parses_answer_references_and_request_id() -> None:
    learner = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    raw = json.dumps(
        {
            "status": "success",
            "course_id": "DE",
            "intent": "explain_concept",
            "answer": "依据 [S1]，触发器在时钟边沿更新。",
            "key_points_json": '["边沿触发"]',
            "source_references_json": '["S1"]',
            "warnings_json": "[]",
            "confidence": "0.82",
            "parse_status": "ok",
            "request_id": "req-roundtrip",
        },
        ensure_ascii=False,
    )

    result = standardize_answer(
        raw,
        input_type="text",
        output_mapping=learner.output_mapping,
    )

    assert result["answer_text"].startswith("依据 [S1]")
    assert result["source_references"] == ["S1"]
    assert result["request_id"] == "req-roundtrip"
    assert result["confidence"] == 0.82


def test_learn_published_line_protocol_is_parsed() -> None:
    learner = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    raw = "\n".join(
        [
            "success",
            "CT",
            "explain_concept",
            "根据 [S1]，电容电压连续。",
            '["电压连续"]',
            '["S1"]',
            "[]",
            "0.91",
            "direct_json",
            "req-line",
        ]
    )

    result = standardize_answer(
        raw,
        input_type="text",
        output_mapping=learner.output_mapping,
    )

    assert result["status"] == "success"
    assert result["answer_text"] == "根据 [S1]，电容电压连续。"
    assert result["source_references"] == ["S1"]
    assert result["request_id"] == "req-line"


def test_declared_citation_is_validated_even_if_answer_has_no_inline_marker() -> None:
    context_packet = RetrievalContextPacket(
        query="问题",
        course_id="CT",
        intent="explain_concept",
        evidence=[
            KnowledgeHit(
                evidence_id="S1",
                course_id="CT",
                course_name="电路理论",
                document_path="chapter.md",
                title="电容",
                content="电容电压连续",
                score=0.9,
                source_ref="kb://CT/chapter.md#chunk-1",
            )
        ],
        source_refs=["kb://CT/chapter.md#chunk-1"],
        evidence_status="sufficient",
        max_context_chars=1000,
    )
    validation = CitationValidator().validate(
        "回答正文",
        context_packet,
        declared_references=["S1", "S9"],
    )

    assert validation.valid_ids == ("S1",)
    assert validation.invalid_ids == ("S9",)
    assert not validation.valid


def test_query_rewrite_is_deterministic_and_keeps_user_conditions() -> None:
    rewritten, rules = rewrite_retrieval_query(
        "请问，帮我解释虚短虚断。",
        course_id="AE",
    )

    assert "虚短 和 虚断" in rewritten
    assert rules
