"""Runtime adapter for the assignment-review business Agent."""

from __future__ import annotations

from app.contracts import AgentResult
from app.services.general_question_runtime import GeneralQuestionRuntimeService


class AssignmentReviewRuntimeService(GeneralQuestionRuntimeService):
    """Run assignment review through the shared observable Runtime DAG."""

    agent_id = "TEACH_02_ASSIGNMENT_REVIEW_V1"
    observe_node_id = "assignment.observe"
    retrieve_node_id = "assignment.retrieve"
    tool_node_id = "assignment.tool"
    execute_node_id = "assignment.execute"
    verify_node_id = "assignment.verify"
    runtime_option_key = "assignment_review_runtime"
    runtime_plan_prefix = "assignment-review-runtime"
    runtime_plan_version = "assignment-review-v1"
    runtime_name = "assignment_review"
    observe_handler_id = "assignment.review.observe"
    retrieve_handler_id = "assignment.review.retrieve"
    tool_handler_prefix = "assignment.review.tool"
    execute_handler_id = "assignment.review.execute"
    verify_handler_id = "assignment.review.verify"

    def _is_valid_result(self, result: AgentResult) -> bool:
        if not super()._is_valid_result(result):
            return False
        required_fields = {
            "correctness",
            "correct_parts",
            "errors",
            "teacher_feedback",
            "review_required",
        }
        return required_fields <= set(result.business_data)
