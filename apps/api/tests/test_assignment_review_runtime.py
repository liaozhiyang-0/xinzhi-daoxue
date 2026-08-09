from __future__ import annotations

import asyncio

from app.contracts import AgentRequest, AgentResult, AgentResultStatus, Intent
from app.runtime import AgentRun, RuntimeNodeStatus
from app.services.assignment_review_runtime import AssignmentReviewRuntimeService


class FakeAssignmentAgents:
    def __init__(self) -> None:
        self.calls = 0

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        del request, context
        self.calls += 1
        if self.calls == 1:
            return AgentResult(
                status=AgentResultStatus.FAILED,
                agent_id=agent_id,
                provider="local_agent",
            )
        return AgentResult(
            status=AgentResultStatus.COMPLETED,
            agent_id=agent_id,
            provider="local_agent",
            answer="初审完成",
            business_data={
                "correctness": "mostly_correct",
                "correct_parts": ["步骤一"],
                "errors": ["步骤二需要补充单位"],
                "teacher_feedback": "请补充单位分析。",
                "review_required": True,
            },
        )


def test_assignment_review_runtime_replans_and_verifies_business_contract() -> None:
    fake = FakeAssignmentAgents()
    service = AssignmentReviewRuntimeService(
        fake,  # type: ignore[arg-type]
        enabled=True,
    )
    request = AgentRequest(
        task_id="task-assignment-runtime",
        session_id="session-1",
        user_id="user-1",
        intent=Intent.ASSIGNMENT_REVIEW,
        canonical_input={"text": "请检查这份作业"},
        options={"assignment_review_runtime": {"execute": True}},
    )
    run = AgentRun(
        run_id="run-assignment-runtime",
        task_id=request.task_id,
        goal="请检查这份作业",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert result.business_data["review_required"] is True
    assert fake.calls == 2
    assert run.iteration == 1
    assert run.nodes["assignment.execute.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )
    assert run.nodes["assignment.verify.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )
