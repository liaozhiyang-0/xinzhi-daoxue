from __future__ import annotations

from app.core.config import Settings

WORKFLOW_INTERNAL_AGENT_MAP: dict[str, str] = {
    "TEACH_01_LESSON_PREP_V1": "LESSON_PREP_LOCAL_V1",
    "TEACH_02_ASSIGNMENT_REVIEW_V1": "ASSIGNMENT_REVIEW_LOCAL_V1",
    "RESEARCH_02_ACADEMIC_WRITING_V1": "ACADEMIC_WRITING_LOCAL_V1",
    "RESEARCH_03_DATA_ANALYSIS_V1": "DATA_ANALYSIS_LOCAL_V1",
}


def internal_workflow_models_configured(
    settings: Settings, workflow_agent_id: str
) -> bool:
    if workflow_agent_id not in WORKFLOW_INTERNAL_AGENT_MAP:
        return False
    return bool(
        settings.iflytek_spark_api_key.get_secret_value()
        and settings.dashscope_api_key.get_secret_value()
    )
