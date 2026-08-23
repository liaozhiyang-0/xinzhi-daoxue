from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.api.v1.sessions import _history_item
from app.contracts import AgentResult
from app.models import TaskStatus
from app.services.conversation_message_service import ConversationMessageService


def _task_with_quality_result() -> SimpleNamespace:
    return SimpleNamespace(
        id="task-history-quality",
        course_id="AE",
        intent="solve_problem",
        status=TaskStatus.COMPLETED,
        provider="local_agent",
        agent_id="ACADEMIC_PROBLEM_SOLVER",
        input_content={
            "canonical_input": {"question": "检查闭环带宽公式"},
        },
        result_content={
            "answer": "需要复核公式。",
            "structured_result": {
                "presentation": {
                    "answer_quality_status": "needs_review",
                    "requires_review": True,
                },
                "math_quality": {"status": "blocked"},
                "formula_output_contract": {"status": "blocked"},
                "scenario_contract": {
                    "model_synthesis": {"publishable": False},
                },
            },
        },
        error_message=None,
        created_at=datetime(2026, 8, 21, tzinfo=UTC),
        completed_at=datetime(2026, 8, 21, tzinfo=UTC),
    )


def test_session_history_keeps_math_and_publication_quality_state() -> None:
    item = _history_item(_task_with_quality_result())

    assert item.answer_quality_status == "needs_review"
    assert item.requires_review is True
    assert item.publishable is False
    assert item.math_quality_status == "blocked"
    assert item.formula_contract_status == "blocked"


def test_assistant_message_projection_keeps_quality_contracts() -> None:
    result = AgentResult(
        agent_id="ACADEMIC_PROBLEM_SOLVER",
        provider="local_agent",
        answer="需要复核公式。",
        warnings=["math_formatting:structured_formula_not_rendered"],
        remaining_risks=["数学输出需要复核"],
        structured_result={
            "math_content": {"markdown": "需要复核公式。"},
            "math_quality": {"status": "blocked", "publishable": False},
            "formula_output_contract": {"status": "blocked"},
            "scenario_contract": {
                "model_synthesis": {"publishable": False},
            },
        },
    )

    projected = ConversationMessageService.assistant_content_data(result)

    assert projected["math_quality"]["publishable"] is False
    assert projected["formula_output_contract"]["status"] == "blocked"
    assert projected["scenario_contract"]["model_synthesis"]["publishable"] is False
    assert projected["warnings"] == result.warnings
    assert projected["remaining_risks"] == result.remaining_risks
