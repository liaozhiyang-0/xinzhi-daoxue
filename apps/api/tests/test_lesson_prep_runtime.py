from __future__ import annotations

import asyncio

from app.contracts import AgentRequest, AgentResult, AgentResultStatus, Intent
from app.runtime import AgentRun, RuntimeNodeStatus
from app.services.lesson_prep_runtime import LessonPrepRuntimeService


class FakeLessonAgents:
    def __init__(self) -> None:
        self.calls = 0

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        del request, context
        assert agent_id == LessonPrepRuntimeService.agent_id
        self.calls += 1
        failed = self.calls == 1
        return AgentResult(
            status=(
                AgentResultStatus.FAILED
                if failed
                else AgentResultStatus.COMPLETED
            ),
            agent_id=agent_id,
            provider="local_agent",
            answer="" if failed else "## Lesson plan",
            business_data=(
                {}
                if failed
                else {
                    "learning_objectives": ["Explain the concept"],
                    "lesson_flow": ["Introduce", "Practice"],
                    "activities": ["Practice"],
                    "formative_assessment": ["Exit ticket"],
                }
            ),
        )


def test_lesson_prep_runtime_verifies_business_contract_after_replan() -> None:
    fake = FakeLessonAgents()
    service = LessonPrepRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = AgentRequest(
        task_id="task-lesson-runtime",
        session_id="session-1",
        user_id="user-1",
        intent=Intent.LESSON_PREP,
        canonical_input={"text": "Prepare a lesson"},
        options={"lesson_prep_runtime": {"execute": True}},
    )
    run = AgentRun(
        run_id="run-lesson-runtime",
        task_id=request.task_id,
        goal="Prepare a lesson",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 2
    assert run.iteration == 1
    assert run.nodes["lesson.execute.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )
    assert run.nodes["lesson.verify.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )
