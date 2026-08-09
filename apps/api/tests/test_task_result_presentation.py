from app.agents import AgentRegistry
from app.contracts import AgentRequest, AgentResult, Artifact, Intent
from app.services.agent_result_governance import (
    AgentResultValidatorRegistry,
    BusinessResultRendererRegistry,
)
from app.services.math_formatting_service import MathFormattingService
from app.services.task_result_presentation import TaskResultPresentationService


def test_result_presentation_builds_views_and_updates_artifacts() -> None:
    registry = AgentRegistry()
    definition = registry.get("GENERAL_QUESTION_V1")
    request = AgentRequest(
        task_id="task-presentation",
        user_id="user-1",
        session_id="session-1",
        course_id="general",
        intent=Intent.GENERAL_QA,
        canonical_input={"question": "What is an agent?"},
        options={"debug": True},
    )
    result = AgentResult(
        agent_id=definition.agent_id,
        course_id=request.course_id,
        intent=request.intent.value,
        answer="An agent observes and acts.",
        provider="local_agent",
        artifacts=[
            Artifact(
                content={"answer": "An agent observes and acts."},
            )
        ],
    )
    validation = AgentResultValidatorRegistry().validate(
        definition, result, request, None
    )

    presented = TaskResultPresentationService(
        BusinessResultRendererRegistry(), MathFormattingService()
    ).apply(
        definition=definition,
        result=result,
        request=request,
        bundle=None,
        routing={},
        timings={},
        validation=validation,
    )

    assert presented.structured_result["presentation"]
    assert presented.structured_result["execution_summary"]
    assert presented.math_content is not None
    assert presented.artifacts[0].content["answer"] == presented.answer
