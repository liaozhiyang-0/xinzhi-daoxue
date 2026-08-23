from __future__ import annotations

from pathlib import Path

import pytest
from app.contracts.agent import (
    AgentRequest,
    AttachmentRef,
    Intent,
    UserRole,
)
from app.contracts.orchestration import AgentRequestV2, CourseCode, InputType
from app.contracts.routing import RouteDecision, RouteStatus
from app.services.scenario_catalog import ScenarioCatalog, ScenarioCatalogError
from app.services.task_creation_service import TaskCreationService

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_scenario_catalog_has_nine_enabled_cases() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")

    scenarios = catalog.list()

    assert len(scenarios) == 9
    assert all(item.commercialization.buyer for item in scenarios)
    assert all(item.commercialization.expansion_path for item in scenarios)
    assert all(item.evidence_policy.citation_required for item in scenarios)
    assert all(item.evidence_policy.manual_review_required for item in scenarios)
    assert {item.id for item in scenarios} == {
        "faculty_course_copilot_v1",
        "assessment_diagnosis_v1",
        "student_learning_path_v1",
        "research_frontier_radar_v1",
            "academic_visual_problem_solver_v1",
            "academic_visual_spectrum_solver_v1",
        "academic_text_diagnostic_solver_v1",
        "department_knowledge_governance_v1",
        "rubric_generation_v1",
    }


def test_scenario_filters_and_request_enrichment() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")

    teacher_cases = catalog.list(course="CT", role="teacher")
    request = AgentRequestV2(
        message="生成课程设计",
        course_hint=CourseCode.CT,
        input_type=InputType.TEXT,
        scenario_id="faculty_course_copilot_v1",
    )

    enriched = catalog.enrich_request(request)

    assert len(teacher_cases) == 8
    assert enriched.metadata["scenario_id"] == "faculty_course_copilot_v1"
    assert enriched.metadata["scenario_retrieval_profile"] == "teaching_authoritative"
    assert enriched.metadata["scenario_evidence_policy"]["citation_required"] is True


def test_scenario_rejects_unsupported_input_mode() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequestV2(
        message="分析图片",
        input_type=InputType.IMAGE,
        scenario_id="faculty_course_copilot_v1",
    )

    with pytest.raises(ScenarioCatalogError, match="不支持输入类型"):
        catalog.enrich_request(request)


def test_academic_visual_scenario_accepts_mixed_input_and_binds_visual_contract(
) -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-visual",
        user_id="user-visual",
        course_id="SS",
        scenario_id="academic_visual_problem_solver_v1",
        canonical_input={"text": "请根据题图求连续时间信号卷积。"},
        attachments=[
            AttachmentRef(
                file_id="file-visual",
                filename="signal.png",
                content_type="image/png",
                size_bytes=10,
                storage_key="local/file-visual",
            )
        ],
    )

    enriched = catalog.enrich_legacy_request(request)

    assert enriched.options["scenario_contract"]["expected_agent"] == (
        "ACADEMIC_PROBLEM_SOLVER"
    )
    assert enriched.options["visual_acceptance"]["must_capture"] == [
        "x_support:[0,1]",
        "h_support:[0,4]",
    ]


def test_academic_spectrum_scenario_binds_frequency_visual_contract() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-spectrum",
        user_id="user-spectrum",
        course_id="CT",
        scenario_id="academic_visual_spectrum_solver_v1",
        canonical_input={"text": "请根据频谱题图求 Y(jω)。"},
        attachments=[
            AttachmentRef(
                file_id="file-spectrum",
                filename="spectrum.png",
                content_type="image/png",
                size_bytes=10,
                storage_key="local/file-spectrum",
            )
        ],
    )

    enriched = catalog.enrich_legacy_request(request)

    assert enriched.options["scenario_contract"]["expected_agent"] == (
        "ACADEMIC_PROBLEM_SOLVER"
    )
    assert enriched.options["visual_acceptance"]["must_capture"] == [
        "spectrum_support:[-π,π]",
    ]


def test_academic_visual_problem_scenario_selects_explicit_demo_case() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-bandpass",
        user_id="user-bandpass",
        course_id="CT",
        scenario_id="academic_visual_problem_solver_v1",
        canonical_input={"text": "请分析带通采样题图。"},
        attachments=[
            AttachmentRef(
                file_id="file-bandpass",
                filename="bandpass.png",
                content_type="image/png",
                size_bytes=10,
                storage_key="local/file-bandpass",
            )
        ],
        options={"scenario_case_id": "bandpass-sampling"},
    )

    enriched = catalog.enrich_legacy_request(request)

    assert enriched.options["scenario_contract"]["demo_case_id"] == (
        "bandpass-sampling"
    )
    assert enriched.options["visual_acceptance"]["must_capture"] == [
        "positive_band:[8,10]kHz",
        "negative_band:[-10,-8]kHz",
        "frequency_units",
    ]


def test_academic_text_diagnostic_scenario_selects_team_feedback_case() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-g2-16",
        user_id="user-g2-16",
        course_id="AE",
        scenario_id="academic_text_diagnostic_solver_v1",
        canonical_input={"text": "请诊断 NPN 共射电路的顶部削峰。"},
        options={"scenario_case_id": "g2-16-bjt-cutoff"},
    )

    enriched = catalog.enrich_legacy_request(request)

    assert enriched.options["scenario_contract"]["demo_case_id"] == (
        "g2-16-bjt-cutoff"
    )
    assert enriched.options["scenario_contract"]["expected_agent"] == (
        "ACADEMIC_PROBLEM_SOLVER"
    )


def test_assignment_scenario_selects_g2_10_case() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-g2-10",
        user_id="user-g2-10",
        user_role=UserRole.TEACHER,
        course_id="AE",
        intent=Intent.ASSIGNMENT_REVIEW,
        scenario_id="assessment_diagnosis_v1",
        canonical_input={"text": "请定位旁路电容问题的首错。"},
        options={"scenario_case_id": "g2-10-bypass-capacitor"},
    )

    enriched = catalog.enrich_legacy_request(request)

    assert enriched.options["scenario_contract"]["demo_case_id"] == (
        "g2-10-bypass-capacitor"
    )
    assert "concept_correction" in enriched.options["scenario_contract"][
        "expected_output"
    ]


def test_learning_path_scenario_selects_g2_12_case() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-g2-12",
        user_id="user-g2-12",
        course_id="AE",
        intent=Intent.LEARNING_ADVICE,
        scenario_id="student_learning_path_v1",
        canonical_input={"text": "规划四周电源竞赛训练。"},
        options={"scenario_case_id": "g2-12-power-training"},
    )

    enriched = catalog.enrich_legacy_request(request)

    assert enriched.options["scenario_contract"]["demo_case_id"] == (
        "g2-12-power-training"
    )
    assert enriched.options["scenario_contract"]["course"] == "AE"


def test_unbound_reserved_metadata_is_removed() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequestV2(
        message="普通问题",
        metadata={
            "scenario_evidence_policy": {"allow_synthetic": True},
            "_scenario_catalog_bound": True,
        },
    )

    cleaned = catalog.enrich_request(request)

    assert "scenario_evidence_policy" not in cleaned.metadata
    assert "_scenario_catalog_bound" not in cleaned.metadata


def test_legacy_task_request_is_bound_to_scenario_policy() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-test",
        user_id="user-test",
        user_role=UserRole.TEACHER,
        course_id="CT",
        scenario_id="faculty_course_copilot_v1",
        options={"input_type": "text"},
    )

    enriched = catalog.enrich_legacy_request(request)

    assert enriched.options["scenario_id"] == "faculty_course_copilot_v1"
    assert enriched.options["_scenario_catalog_bound"] is True
    assert enriched.options["scenario_evidence_policy"]["citation_required"] is True
    assert enriched.intent.value == "lesson_prep"


def test_legacy_scenario_contract_uses_active_course() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-ae",
        user_id="user-ae",
        user_role=UserRole.STUDENT,
        course_id="AE",
        scenario_id="student_learning_path_v1",
        canonical_input={"text": "规划模拟电子技术学习路径"},
    )

    enriched = catalog.enrich_legacy_request(request)

    assert enriched.options["scenario_contract"]["course"] == "AE"
    resolution = enriched.options["scenario_contract"]["course_resolution"]
    assert resolution["source"] == "explicit_request"
    assert resolution["confirmation_required"] is False


def test_legacy_unknown_course_marks_demo_fallback_for_confirmation() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-unknown-course",
        user_id="user-unknown-course",
        user_role=UserRole.STUDENT,
        course_id="UNKNOWN",
        scenario_id="student_learning_path_v1",
        canonical_input={"text": "帮我规划学习路径"},
    )

    enriched = catalog.enrich_legacy_request(request)
    contract = enriched.options["scenario_contract"]

    assert contract["course"] == "CT"
    assert contract["course_confirmation_required"] is True
    assert contract["course_resolution"]["source"] == "demo_case_fallback"


def test_detected_course_replaces_demo_fallback_before_task_persistence() -> None:
    request = AgentRequest(
        session_id="session-detected-course",
        user_id="user-detected-course",
        user_role=UserRole.STUDENT,
        course_id="UNKNOWN",
        intent=Intent.LESSON_PREP,
        canonical_input={"text": "请设计模拟电子技术放大电路教案"},
        options={
            "scenario_id": "faculty_course_copilot_v1",
            "scenario_contract": {
                "course": "CT",
                "course_confirmation_required": True,
                "course_resolution": {
                    "source": "demo_case_fallback",
                    "resolved": "CT",
                    "confirmation_required": True,
                },
            },
        },
    )
    route = RouteDecision(
        agent_id="TEACH_01_LESSON_PREP_V1",
        scene="teaching",
        course_id="AE",
        intent=Intent.LESSON_PREP.value,
        route_status=RouteStatus.SELECTED,
        reason="detected course",
        reason_codes=["detected_course:AE"],
        retrieval_required=True,
        provider_required=False,
    )

    enriched = TaskCreationService._with_route_context(request, route)
    contract = enriched.options["scenario_contract"]

    assert contract["course"] == "AE"
    assert contract["course_confirmation_required"] is False
    assert contract["course_resolution"]["source"] == "router_detected"


@pytest.mark.parametrize(
    ("availability", "failure"),
    [
        ({"input_mode_supported": False}, "agent_input_not_supported"),
        ({"course_supported": False}, "agent_course_not_supported"),
        ({"intent_supported": False}, "agent_intent_not_supported"),
        (
            {"generation_required": True, "generation_available": False},
            "model_generation_required",
        ),
        (
            {
                "external_retrieval_required": True,
                "external_retrieval_available": False,
            },
            "external_retrieval_unavailable",
        ),
    ],
)
def test_task_creation_classifies_route_capability_failures(
    availability: dict[str, bool], failure: str
) -> None:
    route = RouteDecision(
        agent_id="LEARN_01_KNOWLEDGE_QA_V1",
        scene="learning",
        course_id="CT",
        intent=Intent.EXPLAIN_CONCEPT.value,
        route_status=RouteStatus.SELECTED,
        reason="capability contract",
        retrieval_required=True,
        provider_required=False,
        availability=availability,
    )

    result = TaskCreationService._route_failure(route)

    assert result is not None
    assert result[0] == failure


def test_frozen_research_analysis_scenario_cannot_be_bound() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-research-v2",
        user_id="user-research-v2",
        user_role=UserRole.RESEARCHER,
        course_id="CT",
        intent="data_analysis",
        scenario_id="research_data_workbench_v1",
        canonical_input={"text": "冻结两组比较研究设计"},
        options={
            "research_analysis_v2": {
                "execute": False,
                "request": {"research_question": "两组是否存在差异"},
            }
        },
    )

    with pytest.raises(ScenarioCatalogError, match="场景不存在或未启用"):
        catalog.enrich_legacy_request(request)


@pytest.mark.parametrize(
    "user_role", [UserRole.STUDENT, UserRole.TEACHER, UserRole.RESEARCHER]
)
def test_legacy_task_request_allows_any_member_role_for_a_scenario(
    user_role: UserRole,
) -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-student",
        user_id="user-student",
        user_role=user_role,
        course_id="CT",
        scenario_id="assessment_diagnosis_v1",
        canonical_input={"text": "review the assignment"},
    )

    enriched = catalog.enrich_legacy_request(request)

    assert enriched.options["scenario_id"] == "assessment_diagnosis_v1"
    assert enriched.intent.value == "assignment_review"


def test_guest_task_can_use_a_teacher_example_without_role_switching(api) -> None:
    guest = api.client.post("/api/v1/auth/guest")
    assert guest.status_code == 200
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        intent="lesson_prep",
        user_role="teacher",
    )
    payload.update(
        {
            "scene": "teaching",
            "scenario_id": "faculty_course_copilot_v1",
            "canonical_input": {"text": "prepare a lesson"},
        }
    )

    response = api.client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 202
    assert response.json()["input_content"]["scenario_id"] == (
        "faculty_course_copilot_v1"
    )


def test_legacy_task_request_rejects_unadvertised_attachment_mode() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequest(
        session_id="session-test",
        user_id="user-test",
        scenario_id="faculty_course_copilot_v1",
        attachments=[
            AttachmentRef(
                file_id="file-test",
                filename="diagram.png",
                content_type="image/png",
                size_bytes=10,
                storage_key="local/file-test",
            )
        ],
    )

    with pytest.raises(ScenarioCatalogError, match="不支持输入类型"):
        catalog.enrich_legacy_request(request)
