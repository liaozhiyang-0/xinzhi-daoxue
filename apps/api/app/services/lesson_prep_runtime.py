from __future__ import annotations

from app.contracts import AgentResult
from app.services.general_question_runtime import GeneralQuestionRuntimeService


class LessonPrepRuntimeService(GeneralQuestionRuntimeService):
    """Run lesson preparation through the shared Runtime execute/verify kernel."""

    agent_id = "TEACH_01_LESSON_PREP_V1"
    observe_node_id = "lesson.observe"
    retrieve_node_id = "lesson.retrieve"
    tool_node_id = "lesson.tool"
    execute_node_id = "lesson.execute"
    verify_node_id = "lesson.verify"
    runtime_option_key = "lesson_prep_runtime"
    runtime_plan_prefix = "lesson-prep-runtime"
    runtime_plan_version = "lesson-prep-v1"
    runtime_name = "lesson_prep"
    observe_handler_id = "lesson.prep.observe"
    retrieve_handler_id = "lesson.prep.retrieve"
    tool_handler_prefix = "lesson.prep.tool"
    execute_handler_id = "lesson.prep.execute"
    verify_handler_id = "lesson.prep.verify"

    def _is_valid_result(self, result: AgentResult) -> bool:
        if not super()._is_valid_result(result):
            return False
        required = (
            "learning_objectives",
            "lesson_flow",
            "activities",
            "formative_assessment",
        )
        return all(result.business_data.get(field) for field in required)
