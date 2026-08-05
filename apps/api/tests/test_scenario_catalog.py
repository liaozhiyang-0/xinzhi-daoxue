from __future__ import annotations

from pathlib import Path

import pytest
from app.contracts.agent import AgentRequest, AttachmentRef
from app.contracts.orchestration import AgentRequestV2, CourseCode, InputType
from app.services.scenario_catalog import ScenarioCatalog, ScenarioCatalogError

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_contest_scenario_catalog_has_six_enabled_cases() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")

    scenarios = catalog.list()

    assert len(scenarios) == 6
    assert all(item.commercialization.buyer for item in scenarios)
    assert all(item.commercialization.expansion_path for item in scenarios)
    assert all(item.evidence_policy.citation_required for item in scenarios)
    assert all(item.evidence_policy.manual_review_required for item in scenarios)
    assert {item.id for item in scenarios} == {
        "faculty_course_copilot_v1",
        "assessment_diagnosis_v1",
        "student_learning_path_v1",
        "research_frontier_radar_v1",
        "research_data_workbench_v1",
        "department_knowledge_governance_v1",
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

    assert len(teacher_cases) == 6
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
        course_id="CT",
        scenario_id="faculty_course_copilot_v1",
        options={"input_type": "text"},
    )

    enriched = catalog.enrich_legacy_request(request)

    assert enriched.options["scenario_id"] == "faculty_course_copilot_v1"
    assert enriched.options["_scenario_catalog_bound"] is True
    assert enriched.options["scenario_evidence_policy"]["citation_required"] is True
    assert enriched.intent.value == "lesson_prep"


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

    with pytest.raises(ScenarioCatalogError, match="涓嶆敮鎸佽緭鍏ョ被鍨?"):
        catalog.enrich_legacy_request(request)
