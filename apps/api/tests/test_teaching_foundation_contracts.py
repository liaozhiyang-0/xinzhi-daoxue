from __future__ import annotations

import pytest
from app.contracts import (
    EvidencePacketV1,
    EvidenceSourceV1,
    SolutionPacketV1,
    SolutionStepV1,
    StudentAttempt,
    TeachingMode,
    TeachingStateV1,
)
from pydantic import ValidationError


def test_teaching_mode_and_text_attempt_contracts_are_bounded() -> None:
    attempt = StudentAttempt.model_validate(
        {
            "raw_text": "先列 KCL，再求节点电压。",
            "final_answer": "U=2 V",
            "confidence": 0.7,
            "steps": [{"sequence": 1, "content": "列出节点 KCL"}],
        }
    )
    assert TeachingMode("check_my_work") == TeachingMode.CHECK_MY_WORK
    assert attempt.version == "v1"
    assert attempt.steps[0].sequence == 1
    with pytest.raises(ValidationError):
        StudentAttempt.model_validate(
            {"raw_text": "x", "steps": [{"sequence": 0, "content": "invalid"}]}
        )


def test_teaching_state_is_short_lived_and_defaults_to_direct_answer() -> None:
    state = TeachingStateV1(student_attempt_present=True)
    assert state.teaching_mode == TeachingMode.DIRECT_ANSWER
    assert state.current_hint_level is None
    assert state.awaiting_student_response is False


def test_solution_packet_marks_execution_steps_explicitly() -> None:
    packet = SolutionPacketV1(
        course_id="CT",
        problem_type="node_voltage",
        steps=[
            SolutionStepV1(
                step_id="S1",
                title="能力选择",
                content="选择电路分析能力",
                step_source="solver_execution",
            )
        ],
        mapping_status="partial",
    )
    assert packet.steps[0].step_source == "solver_execution"


def test_evidence_packet_does_not_equate_relevance_with_claim_support() -> None:
    packet = EvidencePacketV1(
        query="节点电压法",
        course_id="CT",
        retrieval_status="ready",
        evidence_sufficiency="partial",
        sources=[
            EvidenceSourceV1(
                source_id="S1",
                document_id="doc-1",
                chunk_id="chunk-1",
                course_id="CT",
                content_excerpt="节点电压法相关内容",
                retrieval_score=0.95,
                support_level="potentially_relevant",
            )
        ],
    )
    assert packet.sources[0].support_level == "potentially_relevant"
    assert packet.sources[0].page is None
