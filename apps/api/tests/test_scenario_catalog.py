from __future__ import annotations

from pathlib import Path

import pytest
from app.contracts.orchestration import AgentRequestV2, CourseCode, InputType
from app.services.scenario_catalog import ScenarioCatalog, ScenarioCatalogError

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_contest_scenario_catalog_has_six_enabled_cases() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")

    scenarios = catalog.list()

    assert len(scenarios) == 6
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

    assert len(teacher_cases) == 5
    assert enriched.metadata["scenario_id"] == "faculty_course_copilot_v1"
    assert enriched.metadata["scenario_retrieval_profile"] == "teaching_authoritative"


def test_scenario_rejects_unsupported_input_mode() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    request = AgentRequestV2(
        message="分析图片",
        input_type=InputType.IMAGE,
        scenario_id="faculty_course_copilot_v1",
    )

    with pytest.raises(ScenarioCatalogError, match="不支持输入类型"):
        catalog.enrich_request(request)
