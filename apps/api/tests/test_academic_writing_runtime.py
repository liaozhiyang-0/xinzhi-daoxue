from __future__ import annotations

import asyncio

from app.contracts import AgentRequest, AgentResult, AgentResultStatus, Intent
from app.runtime import AgentRun, RuntimeNodeStatus
from app.services.academic_writing_runtime import AcademicWritingRuntimeService


class FakeWritingAgents:
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
            answer="修订稿已生成",
            business_data={
                "revised_text": "A revised academic paragraph.",
                "revision_notes": ["clarified the method"],
                "unsupported_claims": [],
                "citation_check": "需要人工核验引用与事实",
            },
        )


def test_academic_writing_runtime_replans_and_verifies_contract() -> None:
    fake = FakeWritingAgents()
    service = AcademicWritingRuntimeService(
        fake,  # type: ignore[arg-type]
        enabled=True,
    )
    request = AgentRequest(
        task_id="task-writing-runtime",
        session_id="session-1",
        user_id="user-1",
        intent=Intent.ACADEMIC_WRITING,
        canonical_input={"text": "请润色这段学术文本"},
        options={"academic_writing_runtime": {"execute": True}},
    )
    run = AgentRun(
        run_id="run-writing-runtime",
        task_id=request.task_id,
        goal="请润色这段学术文本",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert result.business_data["revised_text"]
    assert fake.calls == 2
    assert run.iteration == 1
    assert run.nodes["writing.execute.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )
    assert run.nodes["writing.verify.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )
