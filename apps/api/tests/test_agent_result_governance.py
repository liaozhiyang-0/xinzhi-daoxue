from app.agents import AgentRegistry
from app.contracts import AgentRequest, AgentResult
from app.services.agent_result_governance import (
    AgentResultValidatorRegistry,
    BusinessResultRendererRegistry,
)


def request(**options: object) -> AgentRequest:
    return AgentRequest(
        session_id="session-governance",
        user_id="user-governance",
        course_id="CT",
        intent="assignment_review",
        canonical_input={"text": "请处理"},
        options=dict(options),
    )


def test_assignment_without_rubric_removes_deterministic_score() -> None:
    definition = AgentRegistry().get("TEACH_02_ASSIGNMENT_REVIEW_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="mock",
        answer="建议得分8分",
        business_data={"score_suggestion": 8},
    )

    validation = AgentResultValidatorRegistry().validate(
        definition,
        result,
        request(_material_extraction={"materials": {"student_answer": "答案"}}),
        None,
    )

    assert validation.result_status == "accepted_with_warnings"
    assert "score_suggestion" not in result.business_data
    assert validation.corrected_fields == ["business_data.score_suggestion"]


def test_data_analysis_without_results_is_forced_to_plan() -> None:
    definition = AgentRegistry().get("RESEARCH_03_DATA_ANALYSIS_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="mock",
        answer="建议先完成数据清洗。",
        business_data={"analysis_status": "completed"},
    )
    req = request(_material_extraction={"materials": {}}).model_copy(
        update={"intent": "data_analysis"}
    )

    validation = AgentResultValidatorRegistry().validate(definition, result, req, None)
    view = BusinessResultRendererRegistry().render(definition, result, validation)

    assert result.business_data["analysis_status"] == "plan"
    assert view["banner"] == "当前为分析方案，未实际运行计算"


def test_academic_writing_rejects_new_doi() -> None:
    definition = AgentRegistry().get("RESEARCH_02_ACADEMIC_WRITING_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="mock",
        answer="参考文献 DOI: 10.1234/invented.1",
    )
    req = request().model_copy(update={"intent": "academic_writing"})

    validation = AgentResultValidatorRegistry().validate(definition, result, req, None)

    assert validation.response_usable is False
    assert any("DOI" in issue for issue in validation.validation_issues)


def test_six_business_agents_have_specific_validator_and_renderer() -> None:
    registry = AgentRegistry()
    agent_ids = {
        "LEARN_01_KNOWLEDGE_QA_V1",
        "SOLVER_CT_V1",
        "TEACH_01_LESSON_PREP_V1",
        "TEACH_02_ASSIGNMENT_REVIEW_V1",
        "RESEARCH_02_ACADEMIC_WRITING_V1",
        "RESEARCH_03_DATA_ANALYSIS_V1",
    }

    for agent_id in agent_ids:
        definition = registry.get(agent_id)
        assert definition.validator_type != "generic"
        assert definition.renderer_type != "generic"
