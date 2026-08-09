from __future__ import annotations

import asyncio
from collections.abc import Iterable

import pytest
from app.contracts import AgentRequest, AgentResult, AgentResultStatus, Intent
from app.runtime import (
    AgentRun,
    RuntimeNodeStatus,
    RuntimeRunStatus,
    RuntimeRunSuspended,
)
from app.services.academic_writing_runtime import AcademicWritingRuntimeService


def make_result(
    *,
    citation_check: object = "passed",
    unsupported_claims: list[str] | None = None,
    status: AgentResultStatus = AgentResultStatus.COMPLETED,
) -> AgentResult:
    return AgentResult(
        status=status,
        agent_id="RESEARCH_02_ACADEMIC_WRITING_V1",
        provider="local_agent",
        answer="Academic writing result.",
        business_data={
            "revised_text": "A revised academic paragraph.",
            "revision_notes": ["clarified the method"],
            "unsupported_claims": unsupported_claims or [],
            "citation_check": citation_check,
        },
    )


class FakeWritingAgents:
    def __init__(self, results: Iterable[AgentResult]) -> None:
        self._results = iter(results)
        self.calls = 0

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        del request, context
        self.calls += 1
        result = next(self._results)
        return result.model_copy(update={"agent_id": agent_id})


def make_request() -> AgentRequest:
    return AgentRequest(
        task_id="task-writing-runtime",
        session_id="session-1",
        user_id="user-1",
        intent=Intent.ACADEMIC_WRITING,
        canonical_input={"text": "请润色这段学术文本"},
        options={"academic_writing_runtime": {"execute": True}},
    )


def make_run(service: AcademicWritingRuntimeService, request: AgentRequest) -> AgentRun:
    return AgentRun(
        run_id="run-writing-runtime",
        task_id=request.task_id,
        goal="请润色这段学术文本",
        plan=service.build_plan(request),
    )


def test_academic_writing_result_contract_is_fail_closed() -> None:
    service = AcademicWritingRuntimeService(object(), enabled=True)  # type: ignore[arg-type]

    assert service._is_valid_result(make_result(citation_check="passed"))
    assert not service._is_valid_result(
        make_result(citation_check="需要人工核验引用与事实")
    )
    assert not service._is_valid_result(
        make_result(citation_check="passed", unsupported_claims=["missing source"])
    )
    assert not service._is_valid_result(
        make_result(citation_check="passed").model_copy(
            update={
                "business_data": {
                    "revised_text": "text",
                    "revision_notes": [],
                    "unsupported_claims": [],
                    "citation_check": "passed",
                }
            }
        )
    )


def test_uncertain_citation_waits_for_approval_and_recovery_reuses_checkpoint() -> None:
    fake = FakeWritingAgents([make_result(citation_check="需要人工核验引用与事实")])
    service = AcademicWritingRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = make_run(service, request)
    checkpoints: list[AgentRun] = []

    def checkpoint(current: AgentRun) -> None:
        checkpoints.append(current.model_copy(deep=True))

    with pytest.raises(RuntimeRunSuspended):
        asyncio.run(service.run(request, run, checkpoint_hook=checkpoint))

    assert run.status == RuntimeRunStatus.WAITING_APPROVAL
    assert run.last_decision is not None
    assert run.last_decision.approval_scope == service.approval_scope
    assert run.nodes["writing.verify"].status == RuntimeNodeStatus.PARTIAL
    assert fake.calls == 1
    assert any(
        snapshot.observations
        and any(
            "result_payload" in observation.facts
            for observation in snapshot.observations
        )
        for snapshot in checkpoints
    )

    run.control_data["approved"] = True
    result = asyncio.run(service.run(request, run, checkpoint_hook=checkpoint))

    assert result.status == AgentResultStatus.COMPLETED
    assert result.business_data["citation_check"] == "需要人工核验引用与事实"
    assert fake.calls == 1
    assert run.status.value == RuntimeRunStatus.COMPLETED.value
    assert run.nodes["writing.execute"].status == RuntimeNodeStatus.SUCCEEDED
    assert run.nodes["writing.verify"].status.value == RuntimeNodeStatus.SUCCEEDED.value


def test_unsupported_claims_wait_for_approval_even_when_citation_check_passes() -> None:
    fake = FakeWritingAgents(
        [make_result(citation_check="passed", unsupported_claims=["claim"])]
    )
    service = AcademicWritingRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = make_run(service, request)

    with pytest.raises(RuntimeRunSuspended):
        asyncio.run(service.run(request, run))

    assert run.status == RuntimeRunStatus.WAITING_APPROVAL
    assert fake.calls == 1


def test_failed_answer_replans_within_iteration_budget() -> None:
    fake = FakeWritingAgents(
        [
            make_result(status=AgentResultStatus.FAILED),
            make_result(status=AgentResultStatus.FAILED),
            make_result(status=AgentResultStatus.FAILED),
        ]
    )
    service = AcademicWritingRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = make_run(service, request)
    run.budget.max_iterations = 2

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.FAILED
    assert run.status == RuntimeRunStatus.FAILED
    assert run.iteration == 1
    assert fake.calls == 2
    assert run.nodes["writing.execute.replan.1"].status == RuntimeNodeStatus.PARTIAL
