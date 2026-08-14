from __future__ import annotations

import pytest
from app.contracts import AgentRequest, AgentResult
from app.services.scenario_output_contract import ScenarioOutputContractService


def _request(
    scenario_id: str, agent_id: str, expected_output: list[str]
) -> AgentRequest:
    return AgentRequest(
        session_id="session-scenario-contract",
        user_id="user-scenario-contract",
        scenario_id=scenario_id,
        course_id="CT",
        options={
            "scenario_id": scenario_id,
            "scenario_contract": {
                "demo_case_id": "case-1",
                "expected_agent": agent_id,
                "expected_output": expected_output,
                "review_boundary": "需要人工复核，系统不得自动发布。",
                "business_context": "结构化案例验收",
                "acceptance_conditions": ["字段完整"],
            },
        },
    )


def _result(agent_id: str) -> AgentResult:
    return AgentResult(
        agent_id=agent_id,
        provider="local",
        answer="基础回答",
        evidence_status="partial",
        citations=["course://ct/ohm"],
        structured_result={
            "evidence_packet": {
                "sources": [
                    {
                        "title": "欧姆定律",
                        "source_ref": "course://ct/ohm",
                        "content_type": "lesson",
                        "content_excerpt": "课程资料摘要",
                    }
                ]
            }
        },
    )


def test_student_case_exposes_learning_path_contract() -> None:
    agent_id = "LEARN_01_LOCAL_RETRIEVAL_V1"
    expected = [
        "evidence_summary",
        "weak_knowledge_points",
        "prerequisite_path",
        "staged_plan",
        "verification_tasks",
        "evidence",
        "review_boundary",
    ]

    result = ScenarioOutputContractService().enrich(
        _result(agent_id), _request("student_learning_path_v1", agent_id, expected)
    )

    contract = result.structured_result["scenario_contract"]
    assert contract["status"] == "completed_with_gaps"
    assert contract["missing_fields"] == []
    assert len(result.business_data["staged_plan"]) == 7
    assert result.business_data["evidence"]["source_refs"] == ["course://ct/ohm"]
    assert "学生个性化学习路径" in result.answer


def test_governance_case_does_not_turn_unknown_approval_into_success() -> None:
    agent_id = "LEARN_01_KNOWLEDGE_QA_V1"
    expected = [
        "asset_inventory",
        "version_conflicts",
        "source_audit",
        "approval_status",
        "publication_blockers",
        "traceability_links",
        "review_boundary",
    ]

    result = ScenarioOutputContractService().enrich(
        _result(agent_id),
        _request("department_knowledge_governance_v1", agent_id, expected),
    )

    assert result.business_data["approval_status"]["status"] == "not_available"
    assert "缺少可核验的版本清单" in result.business_data["publication_blockers"]
    assert result.structured_result["scenario_contract"]["missing_fields"] == []


def test_generic_fallback_is_not_presented_as_professional_contract() -> None:
    expected = ["evidence_summary", "weak_knowledge_points", "staged_plan"]
    result = _result("GENERAL_MODEL_FALLBACK_V1").model_copy(
        update={"fallback_used": True, "fallback_reason": "route_unavailable"}
    )

    result = ScenarioOutputContractService().enrich(
        result,
        _request("student_learning_path_v1", "LEARN_01_LOCAL_RETRIEVAL_V1", expected),
    )

    contract = result.structured_result["scenario_contract"]
    assert contract["status"] == "not_applied"
    assert contract["missing_fields"] == expected
    assert "场景结构化输出" not in result.answer


@pytest.mark.parametrize(
    ("scenario_id", "agent_id", "expected"),
    [
        (
            "faculty_course_copilot_v1",
            "TEACH_01_LESSON_PREP_V1",
            [
                "learning_objectives",
                "lesson_flow",
                "common_misconceptions",
                "differentiated_practice",
                "evidence",
                "review_boundary",
            ],
        ),
        (
            "assessment_diagnosis_v1",
            "TEACH_02_ASSIGNMENT_REVIEW_V1",
            [
                "first_error",
                "error_cause",
                "preserved_correct_steps",
                "tiered_hints",
                "verification_problem",
                "evidence",
                "review_boundary",
            ],
        ),
        (
            "research_frontier_radar_v1",
            "RESEARCH_01_ACADEMIC_SEARCH_V1",
            [
                "research_scope",
                "evidence_table",
                "doi_or_arxiv",
                "evidence_summary",
                "open_questions",
                "limitations",
                "review_boundary",
            ],
        ),
    ],
)
def test_remaining_enabled_cases_materialize_expected_fields(
    scenario_id: str, agent_id: str, expected: list[str]
) -> None:
    result = ScenarioOutputContractService().enrich(
        _result(agent_id), _request(scenario_id, agent_id, expected)
    )

    contract = result.structured_result["scenario_contract"]
    assert contract["missing_fields"] == []
    assert set(expected) <= set(result.business_data)
