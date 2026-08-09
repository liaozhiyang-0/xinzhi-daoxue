"""Runtime adapter for the academic-writing business Agent."""

from __future__ import annotations

from app.contracts import AgentResult
from app.services.general_question_runtime import GeneralQuestionRuntimeService


class AcademicWritingRuntimeService(GeneralQuestionRuntimeService):
    """Run academic writing assistance through the shared Runtime DAG."""

    agent_id = "RESEARCH_02_ACADEMIC_WRITING_V1"
    observe_node_id = "writing.observe"
    retrieve_node_id = "writing.retrieve"
    tool_node_id = "writing.tool"
    execute_node_id = "writing.execute"
    verify_node_id = "writing.verify"
    runtime_option_key = "academic_writing_runtime"
    runtime_plan_prefix = "academic-writing-runtime"
    runtime_plan_version = "academic-writing-v1"
    runtime_name = "academic_writing"
    observe_handler_id = "academic.writing.observe"
    retrieve_handler_id = "academic.writing.retrieve"
    tool_handler_prefix = "academic.writing.tool"
    execute_handler_id = "academic.writing.execute"
    verify_handler_id = "academic.writing.verify"

    def _is_valid_result(self, result: AgentResult) -> bool:
        if not super()._is_valid_result(result):
            return False
        required_fields = {
            "revised_text",
            "revision_notes",
            "unsupported_claims",
            "citation_check",
        }
        return required_fields <= set(result.business_data)
