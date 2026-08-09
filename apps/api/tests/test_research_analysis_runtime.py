from __future__ import annotations

import asyncio

from app.contracts import AgentRequest, AgentResult, AgentResultStatus
from app.contracts.research_analysis import (
    ResearchAnalysisResult,
    ResearchDataQualityReport,
)
from app.runtime import (
    AgentRun,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
    RuntimeRunSuspended,
    RuntimeStateMachine,
)
from app.services.research_analysis_runtime import ResearchAnalysisRuntimeService


def make_request() -> AgentRequest:
    return AgentRequest(
        task_id="task-research-runtime",
        session_id="session-1",
        user_id="user-1",
        options={
            "research_analysis_v2": {
                "execute": True,
                "request": {
                    "research_question": "Does the intervention change the outcome?",
                    "analysis_goal": "compare",
                    "design": "experimental_comparison",
                },
            }
        },
    )


class FakeInternalAgents:
    def __init__(
        self,
        result: AgentResult,
        results: list[AgentResult] | None = None,
    ) -> None:
        self.result = result
        self.results = results or []
        self.calls = 0
        self.last_request: AgentRequest | None = None

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        assert agent_id == ResearchAnalysisRuntimeService.agent_id
        assert request.task_id == "task-research-runtime"
        assert context is None
        self.calls += 1
        self.last_request = request
        if self.results:
            return self.results[min(self.calls - 1, len(self.results) - 1)]
        return self.result


def make_result(status: AgentResultStatus = AgentResultStatus.COMPLETED) -> AgentResult:
    analysis_status = "executed" if status == AgentResultStatus.COMPLETED else "failed"
    analysis_payload = ResearchAnalysisResult(
        status=analysis_status,  # type: ignore[arg-type]
        data_quality=ResearchDataQualityReport(status="passed"),
        design_assessment="provider-free runtime fixture",
    ).model_dump(mode="json")
    return AgentResult(
        status=status,
        agent_id=ResearchAnalysisRuntimeService.agent_id,
        provider="local_analysis_v2",
        answer="analysis complete",
        structured_result={"analysis_v2": True, "business_data": analysis_payload},
        business_data=analysis_payload,
    )


def test_research_analysis_runtime_executes_and_verifies_dag() -> None:
    fake = FakeInternalAgents(make_result())
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = AgentRun(
        run_id="run-research-runtime",
        task_id=request.task_id,
        goal="research analysis",
        plan=service.build_plan(request),
    )
    checkpoints: list[str] = []
    events: list[str] = []

    async def checkpoint(current: AgentRun) -> None:
        checkpoints.append(current.status.value)

    async def event(event_name: str, _current: AgentRun, _node_id: str) -> None:
        events.append(event_name)

    result = asyncio.run(
        service.run(
            request,
            run,
            checkpoint_hook=checkpoint,
            event_hook=event,
        )
    )

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 1
    assert run.status.value == "completed"
    assert run.nodes[service.execute_node_id].status == RuntimeNodeStatus.SUCCEEDED
    assert run.nodes[service.verify_node_id].status == RuntimeNodeStatus.SUCCEEDED
    verification = run.nodes[service.verify_node_id].observation
    assert verification is not None
    assert verification.facts["passed"] is True
    assert "node_started" in events
    assert "node_completed" in events
    assert checkpoints


def test_research_analysis_runtime_passes_resumed_user_input_to_handler() -> None:
    fake = FakeInternalAgents(make_result())
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = AgentRun(
        run_id="run-research-input",
        task_id=request.task_id,
        goal="research analysis",
        plan=service.build_plan(request),
        control_data={"user_input": {"confirmed": True}},
    )

    asyncio.run(service.run(request, run))

    assert fake.last_request is not None
    assert fake.last_request.options["runtime_user_input"] == {"confirmed": True}


def test_research_analysis_runtime_surfaces_failed_execution() -> None:
    fake = FakeInternalAgents(make_result(AgentResultStatus.FAILED))
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = AgentRun(
        run_id="run-research-failed",
        task_id=request.task_id,
        goal="research analysis",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.FAILED
    assert run.status.value == "failed"
    assert fake.calls == 3
    execute_id, verify_id = service._current_node_ids(run)
    assert run.nodes[execute_id].status == RuntimeNodeStatus.SUCCEEDED
    assert run.nodes[verify_id].status == RuntimeNodeStatus.PARTIAL


def test_research_analysis_runtime_replans_after_partial_verification() -> None:
    fake = FakeInternalAgents(
        make_result(AgentResultStatus.FAILED),
        results=[make_result(AgentResultStatus.FAILED), make_result()],
    )
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = AgentRun(
        run_id="run-research-replan",
        task_id=request.task_id,
        goal="research analysis",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 2
    assert run.iteration == 1
    assert run.plan.version == "research-v2"
    assert "replan.1" in run.plan.nodes[0].node_id
    assert run.status.value == "completed"


def test_research_analysis_runtime_suspends_without_marking_task_failed() -> None:
    fake = FakeInternalAgents(make_result())
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = AgentRun(
        run_id="run-research-waiting-input",
        task_id=request.task_id,
        goal="research analysis",
        plan=service.build_plan(request),
    )

    async def request_input(_run: AgentRun):
        from app.runtime import DecisionAction, RuntimeDecision

        return RuntimeDecision(
            action=DecisionAction.ASK_USER,
            user_prompt="Please provide the missing analysis scope.",
        )

    try:
        asyncio.run(
            service.run(
                request,
                run,
                control_provider=request_input,
            )
        )
    except RuntimeRunSuspended as exc:
        assert exc.status == RuntimeRunStatus.WAITING_INPUT
    else:
        raise AssertionError("expected RuntimeRunSuspended")
    assert run.status == RuntimeRunStatus.WAITING_INPUT
    assert fake.calls == 0


def test_research_analysis_runtime_restores_result_from_checkpoint_observation(
) -> None:
    fake = FakeInternalAgents(make_result())
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = AgentRun(
        run_id="run-research-restored-result",
        task_id=request.task_id,
        goal="research analysis",
        plan=service.build_plan(request),
    )
    execute_id, _verify_id = service._current_node_ids(run)
    RuntimeStateMachine.mark_ready(run)
    RuntimeStateMachine.start_node(run, execute_id)
    RuntimeStateMachine.complete_node(
        run,
        execute_id,
        status=RuntimeNodeStatus.SUCCEEDED,
        observation=RuntimeObservation(
            node_id=execute_id,
            facts={"result_payload": make_result().model_dump(mode="json")},
        ),
    )
    RuntimeStateMachine.mark_ready(run)

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 0
    assert run.status == RuntimeRunStatus.COMPLETED
