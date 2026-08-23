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


def test_academic_writing_with_unverified_citations_is_not_publishable() -> None:
    definition = AgentRegistry().get("RESEARCH_02_ACADEMIC_WRITING_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="dashscope",
        answer="学术修改稿。",
        business_data={
            "revised_text": "修改后的段落。",
            "revision_notes": ["明确研究边界"],
            "unsupported_claims": [],
            "citation_check": "需要人工核验引用与事实",
            "publishable": True,
        },
    )
    req = request().model_copy(update={"intent": "academic_writing"})

    validation = AgentResultValidatorRegistry().validate(definition, result, req, None)

    assert validation.response_usable is True
    assert validation.validation_status == "warning"
    assert validation.result_status == "accepted_with_warnings"
    assert result.business_data["publishable"] is False
    assert result.business_data["requires_review"] is True
    assert "引用和事实仍需人工核验" in validation.validation_issues


def test_learning_result_rejects_unbound_source_reference() -> None:
    definition = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        answer="课程资料暂定结论。",
        citations=["kb://CT/chapter-1"],
        structured_result={
            "source_references": ["kb://CT/not-in-evidence"],
            "sources": [
                {
                    "evidence_id": "E1",
                    "source_ref": "kb://CT/chapter-1",
                }
            ],
        },
    )

    validation = AgentResultValidatorRegistry().validate(
        definition,
        result,
        request().model_copy(update={"intent": "general_qa"}),
        None,
    )

    assert validation.response_usable is False
    assert "存在不属于当前证据包的引用" in validation.validation_issues


def test_learning_result_with_sufficient_evidence_requires_citations() -> None:
    definition = AgentRegistry().get("LEARN_01_KNOWLEDGE_QA_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        answer="课程资料暂定结论。",
        evidence_status="sufficient",
        structured_result={
            "sources": [
                {
                    "evidence_id": "E1",
                    "source_ref": "kb://CT/chapter-1",
                }
            ]
        },
    )

    validation = AgentResultValidatorRegistry().validate(
        definition,
        result,
        request().model_copy(update={"intent": "general_qa"}),
        None,
    )

    assert validation.response_usable is False
    assert "证据状态为充分但未提供可核验引用" in validation.validation_issues


def test_solver_result_requires_an_independent_final_answer_field() -> None:
    definition = AgentRegistry().get("SOLVER_CT_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        answer="推导过程完成，但最终数值需要补充。",
        structured_result={"steps": ["step-1"]},
    )
    req = request().model_copy(update={"intent": "solver_ct"})

    validation = AgentResultValidatorRegistry().validate(definition, result, req, None)

    assert validation.response_usable is False
    assert "未提供独立的最终答案字段" in validation.validation_issues


def test_lesson_result_rejects_unavailable_required_structures() -> None:
    definition = AgentRegistry().get("TEACH_01_LESSON_PREP_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        answer="课程草案。",
        business_data={
            "learning_objectives": {"status": "not_determinable"},
            "lesson_flow": ["导入"],
            "activities": ["练习"],
            "formative_assessment": ["出口条"],
        },
    )
    req = request().model_copy(update={"intent": "lesson_prep"})

    validation = AgentResultValidatorRegistry().validate(definition, result, req, None)

    assert validation.response_usable is False
    assert "缺少教学目标结构" in validation.validation_issues


def test_lesson_result_surfaces_duration_constraint_gap() -> None:
    definition = AgentRegistry().get("TEACH_01_LESSON_PREP_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local",
        answer="课程草案。",
        business_data={
            "learning_objectives": ["能解释核心概念"],
            "lesson_flow": ["导入"],
            "activities": ["练习"],
            "formative_assessment": ["出口条"],
            "duration_check": {
                "status": "mismatch",
                "requested_minutes": 45,
                "planned_minutes": 35,
            },
        },
    )
    req = request().model_copy(update={"intent": "lesson_prep"})

    validation = AgentResultValidatorRegistry().validate(definition, result, req, None)

    assert validation.response_usable is True
    assert validation.result_status == "accepted_with_warnings"
    assert "课堂流程未满足请求的总时长约束" in validation.validation_issues


def test_assignment_missing_first_error_is_reviewable_only_for_incomplete_evidence(
) -> None:
    definition = AgentRegistry().get("TEACH_02_ASSIGNMENT_REVIEW_V1")
    registry = AgentResultValidatorRegistry()
    base = {
        "errors": ["第二步可能不成立"],
        "teacher_feedback": "需要补充首个错误位置。",
    }

    blocked = registry.validate(
        definition,
        AgentResult(
            agent_id=definition.agent_id,
            provider="local",
            answer="作业存在错误。",
            business_data=dict(base),
        ),
        request(),
        None,
    )
    preliminary = registry.validate(
        definition,
        AgentResult(
            agent_id=definition.agent_id,
            provider="local",
            answer="作业存在错误，但当前只能给出初审意见。",
            business_data={**base, "evidence_status": "partial"},
        ),
        request(),
        None,
    )

    assert blocked.response_usable is False
    assert "缺少首个错误定位" in blocked.validation_issues
    assert blocked.result_status == "insufficient"
    assert preliminary.response_usable is True
    assert preliminary.result_status == "accepted_with_warnings"


def test_assignment_flags_contradictory_bypass_resistance_direction() -> None:
    definition = AgentRegistry().get("TEACH_02_ASSIGNMENT_REVIEW_V1")
    result = AgentResult(
        agent_id=definition.agent_id,
        provider="local_agent",
        answer="初审结果需要教师复核。",
        business_data={
            "errors": ["错误地认为加入旁路电容会使输入电阻降低"],
            "first_error": "增益方向判断错误。",
            "teacher_feedback": "输入电阻确实会降低，但电压增益应提高。",
            "evidence_status": "partial",
        },
    )
    req = request().model_copy(
        update={
            "course_id": "AE",
            "canonical_input": {
                "text": "请判断射极旁路电容对输入电阻和增益的影响。"
            },
        }
    )

    validation = AgentResultValidatorRegistry().validate(
        definition, result, req, None
    )

    assert validation.response_usable is True
    assert validation.result_status == "accepted_with_warnings"
    assert len(validation.validation_issues) == 1
    assert result.business_data["semantic_consistency"]["status"] == "needs_review"


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
