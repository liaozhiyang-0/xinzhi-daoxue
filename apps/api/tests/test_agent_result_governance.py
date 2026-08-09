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


def test_data_analysis_v2_result_is_not_mistaken_for_unverified_model_output() -> None:
    definition = AgentRegistry().get("RESEARCH_03_DATA_ANALYSIS_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local_analysis_v2",
        answer="## 科研数据分析 V2\n差异 = 6; n=2 and n=2",
        structured_result={"analysis_v2": True},
        business_data={
            "status": "executed",
            "human_review_required": True,
            "effect_estimates": ["group_difference=6"],
            "evidence_references": [
                {
                    "evidence_id": "method-001",
                    "role": "method_reference",
                    "source_ref": "https://example.test/method",
                    "cited": True,
                }
            ],
            "provenance": {
                "provenance_schema_version": "1.0",
                "research_question": "declared comparison",
                "analysis_goal": "compare",
                "design": "experimental_comparison",
                "dataset": {
                    "dataset_id": "dataset-001",
                    "version": "1",
                    "format": "csv",
                    "checksum_sha256": "b" * 64,
                    "source_ref_included": False,
                },
                "variables": [],
            },
            "artifacts": [
                {
                    "artifact_id": "artifact_analysis_bundle",
                    "artifact_type": "report",
                    "label": "analysis_bundle.json",
                    "checksum_sha256": "a" * 64,
                    "reproducible": True,
                }
            ],
        },
    )
    req = request().model_copy(update={"intent": "data_analysis"})

    validation = AgentResultValidatorRegistry().validate(definition, result, req, None)
    view = BusinessResultRendererRegistry().render(definition, result, validation)

    assert validation.response_usable is True
    assert validation.validation_issues == []
    section_keys = {section["key"] for section in view["sections"]}
    assert {"evidence_references", "provenance", "artifacts"}.issubset(section_keys)
    assert "本地确定性流程" in view["banner"]


def test_data_analysis_v2_model_assistance_is_visible_in_governance_banner() -> None:
    definition = AgentRegistry().get("RESEARCH_03_DATA_ANALYSIS_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local_analysis_v2+model_assist",
        answer=(
            "## 科研数据分析 V2\n\n"
            "### 面向研究问题的解释\n结果提示 treatment 组更高。"
        ),
        structured_result={
            "analysis_v2": True,
            "model_assistance": {"status": "used"},
        },
        business_data={"status": "executed", "human_review_required": True},
    )
    req = request().model_copy(update={"intent": "data_analysis"})

    validation = AgentResultValidatorRegistry().validate(definition, result, req, None)
    view = BusinessResultRendererRegistry().render(definition, result, validation)

    assert "模型辅助解释" in view["banner"]


def test_data_analysis_v2_direct_model_is_visible_in_governance_banner() -> None:
    definition = AgentRegistry().get("RESEARCH_03_DATA_ANALYSIS_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="model_analysis:dashscope",
        answer="## 科研数据分析 V2\n\n### 先说结论\n模型分析结果。",
        structured_result={
            "analysis_v2": True,
            "analysis_execution_source": "model_direct",
        },
        business_data={"status": "executed", "human_review_required": True},
    )
    req = request().model_copy(update={"intent": "data_analysis"})

    validation = AgentResultValidatorRegistry().validate(definition, result, req, None)
    view = BusinessResultRendererRegistry().render(definition, result, validation)

    assert "Qwen/Spark" in view["banner"]


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
