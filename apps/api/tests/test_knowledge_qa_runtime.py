from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.contracts import AgentRequest, AgentResult
from app.runtime import AgentRun, RuntimeNodeStatus
from app.services.knowledge_qa_runtime import KnowledgeQARuntimeService


class FakeKnowledgeQA:
    def __init__(self) -> None:
        self.calls = 0

    async def run_with_generation(
        self, _agent_id: str, _request: AgentRequest
    ) -> SimpleNamespace:
        self.calls += 1
        result = AgentResult(
            agent_id="LEARN_01_LOCAL_RETRIEVAL_V1",
            provider="local",
            answer="依据本地证据给出的回答 [S1]",
            structured_result={"mode": "retrieval_only"},
            citations=["kb://CT/chapter.md"],
            evidence_status="sufficient",
        )
        return SimpleNamespace(
            result=result,
            context=SimpleNamespace(
                evidence_status="sufficient",
                evidence=["S1"],
            ),
        )


@pytest.mark.asyncio
async def test_knowledge_qa_runtime_executes_and_verifies_once() -> None:
    fake = FakeKnowledgeQA()
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = AgentRequest(
        task_id="knowledge-runtime-task",
        session_id="knowledge-runtime-session",
        user_id="knowledge-runtime-user",
        course_id="CT",
        options={"knowledge_qa_runtime": {"execute": True}},
    )
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="knowledge-runtime-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    result = await service.run(request, run)

    assert fake.calls == 1
    assert result.provider == "local"
    assert run.status.value == "completed"
    assert all(
        node.status == RuntimeNodeStatus.SUCCEEDED for node in run.nodes.values()
    )
    assert run.nodes["knowledge.verify"].observation is not None
    assert run.nodes["knowledge.verify"].observation.facts["passed"] is True
