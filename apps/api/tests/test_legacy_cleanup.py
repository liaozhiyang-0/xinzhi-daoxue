from app.agents import AgentRegistry
from app.core.config import PROJECT_ROOT, Settings

REMOVED_AGENT_IDS = {
    "CHECK_01_ANSWER_REVIEW_V1",
    "TEACH_03_LEARNING_ANALYSIS_V1",
    "TEACH_04_CLASS_ANALYSIS_V1",
    "RESEARCH_01_LITERATURE_TRACKING_V1",
}

ACTIVE_BUSINESS_WORKFLOWS = {
    "GENERAL_QUESTION_V1",
    "ROUTER_01_FALLBACK_V1",
    "SOLVER_CT_V1",
    "ACADEMIC_PROBLEM_SOLVER",
    "LEARN_01_KNOWLEDGE_QA_V1",
    "TEACH_01_LESSON_PREP_V1",
    "TEACH_02_ASSIGNMENT_REVIEW_V1",
    "RESEARCH_01_ACADEMIC_SEARCH_V1",
    "RESEARCH_02_ACADEMIC_WRITING_V1",
    "RESEARCH_03_DATA_ANALYSIS_V1",
}


def test_active_registry_excludes_unpublished_legacy_agents() -> None:
    agent_ids = {item.agent_id for item in AgentRegistry().list_agents()}

    assert REMOVED_AGENT_IDS.isdisjoint(agent_ids)
    assert ACTIVE_BUSINESS_WORKFLOWS <= agent_ids
    assert len(agent_ids) == 12


def test_removed_flow_settings_are_not_part_of_active_configuration() -> None:
    field_names = set(Settings.model_fields)

    assert "xingchen_answer_review_flow_id" not in field_names
    assert "xingchen_learning_analysis_flow_id" not in field_names
    assert "xingchen_class_analysis_flow_id" not in field_names
    assert "xingchen_literature_tracking_flow_id" not in field_names


def test_historical_stage_documents_are_isolated() -> None:
    current_path = PROJECT_ROOT / "docs" / "architecture" / "00_stage_0_1_scope.md"
    archive_path = (
        PROJECT_ROOT
        / "archive_legacy"
        / "docs"
        / "architecture"
        / "00_stage_0_1_scope.md"
    )

    assert not current_path.exists()
    assert archive_path.is_file()
    assert (PROJECT_ROOT / "archive_legacy" / "README.md").is_file()


def test_unreferenced_task_service_facade_is_isolated() -> None:
    current_path = (
        PROJECT_ROOT / "apps" / "api" / "app" / "services" / "task_service.py"
    )
    archive_path = (
        PROJECT_ROOT
        / "archive_legacy"
        / "apps"
        / "api"
        / "app"
        / "services"
        / "task_service.py"
    )

    assert not current_path.exists()
    assert archive_path.is_file()
