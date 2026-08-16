from __future__ import annotations

from app.services.general_question_runtime import GeneralQuestionRuntimeService


class GeneralModelFallbackRuntimeService(GeneralQuestionRuntimeService):
    """Runtime plan for the registered generic model fallback Agent."""

    agent_id = "GENERAL_MODEL_FALLBACK_V1"
    observe_node_id = "general_fallback.observe"
    retrieve_node_id = "general_fallback.retrieve"
    tool_node_id = "general_fallback.tool"
    execute_node_id = "general_fallback.execute"
    verify_node_id = "general_fallback.verify"
    runtime_option_key = "general_model_fallback_runtime"
    runtime_plan_prefix = "general-model-fallback-runtime"
    runtime_plan_version = "general-model-fallback-v1"
    runtime_name = "general_model_fallback"
    observe_handler_id = "general.model_fallback.observe"
    retrieve_handler_id = "general.model_fallback.retrieve"
    tool_handler_prefix = "general.model_fallback.tool"
    execute_handler_id = "general.model_fallback.execute"
    verify_handler_id = "general.model_fallback.verify"

