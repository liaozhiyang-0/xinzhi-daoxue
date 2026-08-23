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
                "demo_case_id": (
                    "signal-convolution"
                    if scenario_id == "academic_visual_problem_solver_v1"
                    else "case-1"
                ),
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
    assert set(contract["missing_fields"]) == {
        "evidence_summary",
        "weak_knowledge_points",
        "prerequisite_path",
        "staged_plan",
        "verification_tasks",
    }
    assert result.business_data["staged_plan"]["status"] == "not_available"
    assert result.business_data["evidence"]["source_refs"] == ["course://ct/ohm"]
    assert "学生个性化学习路径" in result.answer
    assert "```json" not in result.answer
    assert "详细字段已同步到结构化结果和结果面板" in result.answer


def test_student_case_blocks_short_plan_against_requested_horizon() -> None:
    agent_id = "LEARN_01_LOCAL_RETRIEVAL_V1"
    result = _result(agent_id).model_copy(
        update={
            "evidence_status": "sufficient",
            "business_data": {
                "staged_plan": [{"day": 1, "goal": "复盘"}],
                "plan_horizon_check": {
                    "status": "mismatch",
                    "requested_days": 14,
                    "planned_days": 1,
                },
            },
        }
    )

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request("student_learning_path_v1", agent_id, ["staged_plan"]),
    )

    contract = enriched.structured_result["scenario_contract"]
    assert contract["status"] == "completed_with_gaps"
    assert "plan_horizon" in contract["quality_gaps"]
    assert contract["model_synthesis"]["publishable"] is False


def test_scenario_policy_manual_review_blocks_publishability() -> None:
    agent_id = "LEARN_01_LOCAL_RETRIEVAL_V1"
    result = _result(agent_id).model_copy(
        update={
            "evidence_status": "sufficient",
            "business_data": {"staged_plan": ["四周计划"]},
        }
    )
    request = _request(
        "student_learning_path_v1", agent_id, ["staged_plan"]
    ).model_copy(
        update={
            "options": {
                **_request(
                    "student_learning_path_v1", agent_id, ["staged_plan"]
                ).options,
                "scenario_evidence_policy": {"manual_review_required": True},
            }
        }
    )

    enriched = ScenarioOutputContractService().enrich(result, request)

    contract = enriched.structured_result["scenario_contract"]
    assert contract["status"] == "completed_with_gaps"
    assert "manual_review_required" in contract["quality_gaps"]
    assert contract["model_synthesis"]["publishable"] is False


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
    assert set(
        result.structured_result["scenario_contract"]["missing_fields"]
    ) == {
        "asset_inventory",
        "version_conflicts",
        "source_audit",
        "approval_status",
        "traceability_links",
    }


def test_governance_case_audits_only_assets_present_in_input() -> None:
    agent_id = "LEARN_01_LOCAL_RETRIEVAL_V1"
    expected = [
        "asset_inventory",
        "version_conflicts",
        "source_audit",
        "approval_status",
        "publication_blockers",
        "traceability_links",
        "publication_checklist_before",
        "publication_checklist_after",
        "rollback_checklist",
        "review_boundary",
    ]
    request = _request(
        "department_knowledge_governance_v1", agent_id, expected
    ).model_copy(
        update={
            "canonical_input": {
                "text": (
                    "请检查 CT 课程知识库：讲义《节点电压法》v3、"
                    "练习题包《直流网络》v2、教师修订说明 v1。"
                )
            }
        }
    )

    result = ScenarioOutputContractService().enrich(_result(agent_id), request)

    inventory = result.business_data["asset_inventory"]
    assert [item["version"] for item in inventory] == ["v3", "v2", "v1"]
    assert result.business_data["approval_status"]["status"] == "unknown"
    assert result.business_data["traceability_links"] == [
        {"asset": item["title"], "link": "未知"} for item in inventory
    ]
    assert len(result.business_data["version_conflicts"]["items"]) == 3


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


def test_text_diagnostic_case_exposes_only_answer_backed_fields() -> None:
    agent_id = "ACADEMIC_PROBLEM_SOLVER"
    expected = [
        "observation_summary",
        "operating_region",
        "candidate_causes",
        "diagnostic_steps",
        "safety_boundary",
        "review_boundary",
    ]
    result = _result(agent_id).model_copy(
        update={
            "answer": (
                "集电极直流电位 VCC 且顶部削峰，工作在截止区。"
                "可能原因有三项；验证步骤包括断电检查。"
            ),
            "evidence_status": "sufficient",
        }
    )

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request("academic_text_diagnostic_solver_v1", agent_id, expected),
    )

    contract = enriched.structured_result["scenario_contract"]
    assert contract["missing_fields"] == []
    assert enriched.business_data["operating_region"]["status"] == "available"


def test_text_diagnostic_recovers_real_model_phrases() -> None:
    agent_id = "ACADEMIC_PROBLEM_SOLVER"
    expected = [
        "diagnostic_steps",
        "compensation_component",
        "review_boundary",
    ]
    result = _result(agent_id).model_copy(
        update={
            "answer": (
                "实验验证方案：测量时间常数。"
                "在反馈电容两端并联一个大阻值电阻 R_f。"
            ),
            "evidence_status": "sufficient",
        }
    )

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request("academic_text_diagnostic_solver_v1", agent_id, expected),
    )

    contract = enriched.structured_result["scenario_contract"]
    assert contract["missing_fields"] == []
    assert enriched.business_data["diagnostic_steps"]["status"] == "available"
    assert enriched.business_data["compensation_component"]["status"] == "available"


def test_text_diagnostic_recovers_integrator_observation_phrase() -> None:
    agent_id = "ACADEMIC_PROBLEM_SOLVER"
    result = _result(agent_id).model_copy(
        update={"answer": "输出电压随时间线性漂移并最终饱和。"}
    )

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request(
            "academic_text_diagnostic_solver_v1",
            agent_id,
            ["observation_summary", "review_boundary"],
        ),
    )

    assert (
        enriched.business_data["observation_summary"]["status"] == "available"
    )


def test_unavailable_envelope_is_not_counted_as_present() -> None:
    agent_id = "TEACH_02_ASSIGNMENT_REVIEW_V1"
    expected = ["first_error", "concept_correction", "review_boundary"]
    result = _result(agent_id).model_copy(
        update={
            "business_data": {
                "first_error": "首个错误在节点方程。",
                "concept_correction": {
                    "status": "not_available",
                    "reason": "模型未提供概念纠正",
                },
            }
        }
    )

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request("assessment_diagnosis_v1", agent_id, expected),
    )

    contract = enriched.structured_result["scenario_contract"]
    assert contract["present_fields"] == ["first_error", "review_boundary"]
    assert contract["missing_fields"] == ["concept_correction"]
    assert contract["status"] == "completed_with_gaps"


def test_assignment_concept_correction_can_be_mapped_from_model_feedback() -> None:
    agent_id = "TEACH_02_ASSIGNMENT_REVIEW_V1"
    expected = ["first_error", "concept_correction", "review_boundary"]
    result = _result(agent_id).model_copy(
        update={
            "business_data": {
                "first_error": "学生把旁路电容作用方向判断反了。",
                "teacher_feedback": "旁路电容降低交流负反馈，需结合频率复核。",
            }
        }
    )

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request("assessment_diagnosis_v1", agent_id, expected),
    )

    contract = enriched.structured_result["scenario_contract"]
    assert contract["missing_fields"] == []
    assert enriched.business_data["concept_correction"] == {
        "status": "available",
        "content": "旁路电容降低交流负反馈，需结合频率复核。",
        "source": "teacher_feedback",
    }


def test_research_evidence_summary_cannot_claim_sufficient_after_filtering() -> None:
    agent_id = "RESEARCH_01_ACADEMIC_SEARCH_V1"
    result = _result(agent_id).model_copy(
        update={
            "evidence_status": "insufficient",
            "structured_result": {"external_retrieval": {"items": []}},
            "business_data": {
                "evidence_summary": {"status": "sufficient", "item_count": 6}
            },
        }
    )

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request(
            "research_frontier_radar_v1",
            agent_id,
            [
                "evidence_table",
                "evidence_summary",
            ],
        ),
    )

    assert enriched.business_data["evidence_summary"] == {
        "status": "insufficient",
        "item_count": 0,
    }


def test_research_contract_preserves_withheld_review_status_when_items_are_empty() -> (
    None
):
    agent_id = "RESEARCH_01_ACADEMIC_SEARCH_V1"
    result = _result(agent_id).model_copy(
        update={
            "evidence_status": "insufficient",
            "structured_result": {
                "external_retrieval": {
                    "status": "partial",
                    "review_status": "not_run",
                    "approved_count": 0,
                    "items": [],
                }
            },
        }
    )

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request(
            "research_frontier_radar_v1",
            agent_id,
            ["evidence_table", "evidence_summary"],
        ),
    )

    contract = enriched.structured_result["scenario_contract"]
    assert contract["evidence_review_status"] == "not_run"
    assert contract["status"] == "completed_with_gaps"
    assert contract["model_synthesis"]["publishable"] is False
    assert "evidence_review" in contract["quality_gaps"]


def test_research_contract_is_not_publishable_before_external_evidence_review() -> None:
    agent_id = "RESEARCH_01_ACADEMIC_SEARCH_V1"
    result = _result(agent_id).model_copy(
        update={
            "evidence_status": "sufficient",
            "structured_result": {
                "external_retrieval": {
                    "review_status": "not_run",
                    "items": [{"evidence_id": "paper-1"}],
                }
            },
        }
    )

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request(
            "research_frontier_radar_v1",
            agent_id,
            ["evidence_table", "evidence_summary"],
        ),
    )

    contract = enriched.structured_result["scenario_contract"]
    assert contract["status"] == "completed_with_gaps"
    assert contract["evidence_review_status"] == "not_run"
    assert contract["model_synthesis"]["publishable"] is False
    assert "evidence_review" in contract["quality_gaps"]


def test_research_contract_rejects_approval_without_complete_accounting() -> None:
    agent_id = "RESEARCH_01_ACADEMIC_SEARCH_V1"
    result = _result(agent_id).model_copy(
        update={
            "evidence_status": "sufficient",
            "structured_result": {
                "external_retrieval": {
                    "review_status": "approved",
                    "items": [{"evidence_id": "paper-1"}],
                }
            },
        }
    )

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request(
            "research_frontier_radar_v1",
            agent_id,
            ["evidence_table", "evidence_summary"],
        ),
    )

    contract = enriched.structured_result["scenario_contract"]
    assert contract["status"] == "completed_with_gaps"
    assert contract["evidence_review_status"] == "incomplete"
    assert contract["model_synthesis"]["publishable"] is False
    assert "evidence_review" in contract["quality_gaps"]
    assert enriched.business_data["evidence_table"][0]["evidence_status"] == (
        "candidate"
    )


def test_lesson_duration_gap_blocks_scenario_contract_publishability() -> None:
    agent_id = "TEACH_01_LESSON_PREP_V1"
    result = _result(agent_id).model_copy(
        update={
            "evidence_status": "sufficient",
            "business_data": {
                "learning_objectives": ["能解释核心概念"],
                "lesson_flow": ["导入", "练习"],
                "activities": ["练习"],
                "formative_assessment": ["出口条"],
                "duration_check": {
                    "status": "mismatch",
                    "requested_minutes": 45,
                    "planned_minutes": 35,
                },
            },
        }
    )

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request(
            "faculty_course_copilot_v1",
            agent_id,
            ["learning_objectives", "lesson_flow"],
        ),
    )

    contract = enriched.structured_result["scenario_contract"]
    assert contract["status"] == "completed_with_gaps"
    assert contract["model_synthesis"]["publishable"] is False
    assert contract["quality_gaps"] == ["duration_constraint"]


def test_unknown_course_keeps_scenario_contract_non_publishable() -> None:
    agent_id = "TEACH_01_LESSON_PREP_V1"
    request = _request(
        "faculty_course_copilot_v1",
        agent_id,
        ["learning_objectives", "lesson_flow"],
    ).model_copy(
        update={
            "options": {
                "scenario_id": "faculty_course_copilot_v1",
                "scenario_contract": {
                    "demo_case_id": "case-1",
                    "expected_agent": agent_id,
                    "expected_output": ["learning_objectives", "lesson_flow"],
                    "course": "CT",
                    "course_confirmation_required": True,
                    "review_boundary": "需要确认课程后才能发布。",
                },
            }
        }
    )
    result = _result(agent_id).model_copy(update={"evidence_status": "sufficient"})

    enriched = ScenarioOutputContractService().enrich(result, request)
    contract = enriched.structured_result["scenario_contract"]

    assert contract["status"] == "completed_with_gaps"
    assert contract["model_synthesis"]["publishable"] is False
    assert "course_confirmation" in contract["quality_gaps"]


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
        (
            "academic_visual_problem_solver_v1",
            "ACADEMIC_PROBLEM_SOLVER",
            [
                "visual_structure",
                "visual_acceptance",
                "piecewise_expression",
                "waveform",
                "breakpoint_explanation",
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
    assert contract["status"] == "completed_with_gaps"
    assert set(contract["missing_fields"]) <= set(expected)
    assert set(expected) <= set(result.business_data)


def test_academic_visual_contract_materializes_real_answer_fields() -> None:
    result = _result("ACADEMIC_PROBLEM_SOLVER").model_copy(
        update={
            "evidence_status": "sufficient",
            "business_data": {
                "vision_execution": {
                    "status": "completed",
                    "visual_structure_status": "complete",
                    "visual_acceptance": {"status": "passed"},
                },
                "final_answer": (
                    "分段表达式 y(t)；波形；t=0、t=1、t=4、t=5 的拐点解释。"
                ),
            },
        }
    )
    expected = [
        "visual_structure",
        "visual_acceptance",
        "piecewise_expression",
        "waveform",
        "breakpoint_explanation",
        "review_boundary",
    ]

    enriched = ScenarioOutputContractService().enrich(
        result,
        _request(
            "academic_visual_problem_solver_v1",
            "ACADEMIC_PROBLEM_SOLVER",
            expected,
        ),
    )

    contract = enriched.structured_result["scenario_contract"]
    assert contract["missing_fields"] == []
    assert contract["quality_gaps"] == []
    assert contract["model_synthesis"]["publishable"] is True


def test_academic_visual_secondary_case_materializes_generic_solution_field() -> None:
    expected = ["visual_structure", "visual_acceptance", "solution", "review_boundary"]
    request = _request(
        "academic_visual_problem_solver_v1",
        "ACADEMIC_PROBLEM_SOLVER",
        expected,
    ).model_copy(
        update={
            "options": {
                "scenario_id": "academic_visual_problem_solver_v1",
                "scenario_contract": {
                    "demo_case_id": "bandpass-sampling",
                    "expected_agent": "ACADEMIC_PROBLEM_SOLVER",
                    "expected_output": expected,
                    "review_boundary": "频带与单位需要人工复核。",
                    "business_context": "频谱采样案例验收",
                    "acceptance_conditions": ["字段完整"],
                },
            }
        }
    )
    result = _result("ACADEMIC_PROBLEM_SOLVER").model_copy(
        update={
            "evidence_status": "sufficient",
            "business_data": {
                "vision_execution": {
                    "status": "completed",
                    "visual_acceptance": {"status": "passed"},
                },
                "final_answer": "已完成带通采样条件与最小采样率推导。",
            },
        }
    )

    enriched = ScenarioOutputContractService().enrich(result, request)

    assert enriched.structured_result["scenario_contract"]["missing_fields"] == []
    assert enriched.business_data["solution"]["status"] == "available"


def test_rubric_contract_tracks_dimensions_levels_and_no_student_score() -> None:
    agent_id = "GENERAL_QUESTION_V1"
    expected = [
        "rubric_dimensions",
        "rubric_levels",
        "student_score_excluded",
        "review_boundary",
    ]
    request = _request("rubric_generation_v1", agent_id, expected)
    contract = dict(request.options["scenario_contract"])
    contract["course_confirmation_required"] = True
    request = request.model_copy(
        update={"options": {**request.options, "scenario_contract": contract}}
    )
    result = _result(agent_id).model_copy(
        update={
            "answer": (
                "代码规范性、资源占用率、功能完整性、防抖动处理；"
                "等级包含优秀、良好、及格、不及格。"
                "本量规不对具体学生给出分数。"
            )
        }
    )

    enriched = ScenarioOutputContractService().enrich(result, request)

    output_contract = enriched.structured_result["scenario_contract"]
    assert output_contract["status"] == "completed_with_gaps"
    assert output_contract["missing_fields"] == []
    assert enriched.business_data["student_score_excluded"]["status"] == "available"
