from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.contracts import AgentRequest, AgentResult
from app.runtime import (
    AgentRun,
    RuntimeNodeStatus,
    RuntimeRunStatus,
    RuntimeRunSuspended,
)
from app.services.knowledge_qa_runtime import KnowledgeQARuntimeService


class SequencedKnowledgeQA:
    def __init__(self, *evidence_statuses: str) -> None:
        self.evidence_statuses = list(evidence_statuses)
        self.calls = 0
        self.requests: list[AgentRequest] = []

    async def run_with_generation(
        self, _agent_id: str, request: AgentRequest
    ) -> SimpleNamespace:
        self.calls += 1
        self.requests.append(request)
        evidence_status = self.evidence_statuses.pop(0)
        result = AgentResult(
            agent_id=KnowledgeQARuntimeService.agent_id,
            provider="local",
            answer="基于本地证据的回答 [S1]",
            structured_result={"mode": "retrieval_only"},
            citations=["kb://CT/chapter.md"]
            if evidence_status == "sufficient"
            else [],
            evidence_status=evidence_status,
        )
        return SimpleNamespace(
            result=result,
            context=SimpleNamespace(
                evidence_status=evidence_status,
                evidence=["S1"] if evidence_status == "sufficient" else [],
            ),
        )


def _request(task_id: str, *, replan: bool = False) -> AgentRequest:
    return AgentRequest(
        task_id=task_id,
        session_id=f"{task_id}-session",
        user_id=f"{task_id}-user",
        course_id="CT",
        canonical_input={"text": "原始问题"},
        options={
            "knowledge_qa_runtime": {
                "execute": True,
                "replan_on_verification_failure": replan,
            }
        },
    )


def _run_for(
    service: KnowledgeQARuntimeService, request: AgentRequest
) -> AgentRun:
    plan = service.build_plan(request)
    return AgentRun(
        run_id=f"{request.task_id}-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )


@pytest.mark.asyncio
async def test_replan_opt_in_is_required_for_legacy_failure_behavior() -> None:
    fake = SequencedKnowledgeQA("insufficient")
    request = _request("knowledge-replan-default")
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    run = _run_for(service, request)

    result = await service.run(request, run)

    assert result.status.value == "completed"
    assert fake.calls == 1
    assert run.status == RuntimeRunStatus.FAILED
    assert run.last_decision is not None
    assert run.last_decision.reason_codes == ["knowledge_verification_failed"]
    assert run.iteration == 0


@pytest.mark.asyncio
async def test_replan_first_enters_waiting_input() -> None:
    fake = SequencedKnowledgeQA("insufficient")
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _request("knowledge-replan-wait", replan=True)
    run = _run_for(service, request)

    with pytest.raises(RuntimeRunSuspended) as suspended:
        await service.run(request, run)

    assert suspended.value.status == RuntimeRunStatus.WAITING_INPUT
    assert run.status == RuntimeRunStatus.WAITING_INPUT
    assert fake.calls == 1
    assert run.last_decision is not None
    assert run.last_decision.action.value == "ask_user"
    assert run.iteration == 0


@pytest.mark.asyncio
async def test_bounded_user_input_updates_request_and_succeeds_after_replan() -> None:
    fake = SequencedKnowledgeQA("insufficient", "sufficient")
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _request("knowledge-replan-success", replan=True)
    run = _run_for(service, request)

    with pytest.raises(RuntimeRunSuspended):
        await service.run(request, run)
    run.control_data["user_input"] = {"query": "补充更具体的检索问题"}

    result = await service.run(request, run)

    assert result.status.value == "completed"
    assert run.status == RuntimeRunStatus.COMPLETED
    assert run.iteration == 1
    assert fake.calls == 2
    assert [node.node_id for node in run.plan.nodes] == [
        "knowledge.execute.replan.1",
        "knowledge.verify.replan.1",
    ]
    assert fake.requests[1].canonical_input["query"] == "补充更具体的检索问题"
    assert fake.requests[1].canonical_input["text"] == "补充更具体的检索问题"
    assert run.control_data["request"]["canonical_input"]["text"] == (
        "补充更具体的检索问题"
    )
    assert all(
        state.status == RuntimeNodeStatus.SUCCEEDED for state in run.nodes.values()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_input", "max_iterations", "reason_code"),
    [
        (
            {"query": "x" * (KnowledgeQARuntimeService.max_user_input_chars + 1)},
            3,
            "knowledge_user_input_invalid",
        ),
        (
            {"text": "合法的补充问题"},
            1,
            "knowledge_replan_budget_exhausted",
        ),
    ],
)
async def test_replan_input_and_budget_limits_fail_closed(
    user_input: dict[str, str], max_iterations: int, reason_code: str
) -> None:
    fake = SequencedKnowledgeQA("insufficient", "sufficient")
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _request(f"knowledge-replan-rejected-{reason_code}", replan=True)
    run = _run_for(service, request)

    with pytest.raises(RuntimeRunSuspended):
        await service.run(request, run)
    run.control_data["user_input"] = user_input
    run.budget.max_iterations = max_iterations

    result = await service.run(request, run)

    assert result.status.value == "completed"
    assert run.status == RuntimeRunStatus.FAILED
    assert fake.calls == 1
    assert run.iteration == 0
    assert run.last_decision is not None
    assert run.last_decision.reason_codes == [reason_code]
