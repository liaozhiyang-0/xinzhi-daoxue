from __future__ import annotations

import asyncio

import pytest
from app.contracts import AgentRequest, AgentResult, AgentResultStatus
from app.contracts.research_analysis import (
    ResearchAnalysisRequest,
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

PREPARE_NODE_ID = "analysis.prepare"


def expected_prepared_control_data(request: AgentRequest) -> dict[str, object]:
    options = request.options["research_analysis_v2"]
    assert isinstance(options, dict)
    payload = ResearchAnalysisRequest.model_validate(
        options["request"]
    ).model_dump(mode="json")
    manifest = payload["data_manifest"]
    assert isinstance(manifest, dict)
    return {
        "research_analysis_prepared": {
            "schema_version": "research-analysis-prepared-v1",
            "payload": payload,
            "execution_mode": "local",
            "execution_options": {"execute": True},
            "authorization_manifest_ref": {
                "present": True,
                "dataset_id": manifest["dataset_id"],
                "version": manifest["version"],
                "format": manifest["format"],
                "checksum_sha256": manifest["checksum_sha256"],
                "authorized": manifest["authorized"],
                "contains_sensitive_data": manifest["contains_sensitive_data"],
            },
        }
    }


def make_request() -> AgentRequest:
    return AgentRequest(
        task_id="task-research-runtime",
        session_id="session-1",
        user_id="user-1",
        options={
            "research_analysis_v2": {
                "execute": True,
                "execution_mode": "local",
                "request": {
                    "research_question": "Does the intervention change the outcome?",
                    "analysis_goal": "compare",
                    "design": "experimental_comparison",
                    "data_manifest": {
                        "dataset_id": "research03-runtime-fixture",
                        "version": "v1",
                        "format": "csv",
                        "checksum_sha256": "b" * 64,
                        "row_count": 2,
                        "column_count": 3,
                        "authorized": True,
                        "source_ref": "attachment:research03-runtime",
                    },
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


def make_result(
    status: AgentResultStatus = AgentResultStatus.COMPLETED,
    *,
    analysis_status: str | None = None,
) -> AgentResult:
    resolved_analysis_status = analysis_status or (
        "executed" if status == AgentResultStatus.COMPLETED else "failed"
    )
    analysis_payload = ResearchAnalysisResult(
        status=resolved_analysis_status,  # type: ignore[arg-type]
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


def expected_control_data(request: AgentRequest) -> dict[str, object]:
    return expected_prepared_control_data(request)


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
    prepare_completed_without_agent_call = False

    async def checkpoint(current: AgentRun) -> None:
        checkpoints.append(current.status.value)

    async def event(event_name: str, _current: AgentRun, node_id: str) -> None:
        nonlocal prepare_completed_without_agent_call
        events.append(event_name)
        if event_name == "node_completed" and node_id == PREPARE_NODE_ID:
            prepare_completed_without_agent_call = True
            assert fake.calls == 0

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
    assert prepare_completed_without_agent_call is True
    assert run.nodes[PREPARE_NODE_ID].status == RuntimeNodeStatus.SUCCEEDED
    assert run.control_data == expected_control_data(request)
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


def test_research_analysis_runtime_execute_reads_normalized_checkpoint_payload(
) -> None:
    checkpoint_request = make_request()
    live_request = checkpoint_request.model_copy(
        update={
            "options": {
                "research_analysis_v2": {
                    "execute": True,
                    "execution_mode": "local",
                    "request": {
                        "research_question": "A different live request must not win",
                        "analysis_goal": "compare",
                        "design": "experimental_comparison",
                    },
                }
            }
        }
    )
    fake = FakeInternalAgents(make_result())
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    run = AgentRun(
        run_id="run-research-checkpoint-payload",
        task_id=checkpoint_request.task_id,
        goal="research analysis",
        plan=service.build_plan(checkpoint_request),
        control_data=expected_control_data(checkpoint_request),
    )

    prepare_id, _execute_id, _verify_id = service._current_node_ids(run)
    assert prepare_id is not None
    RuntimeStateMachine.mark_ready(run)
    RuntimeStateMachine.start_node(run, prepare_id)
    RuntimeStateMachine.complete_node(
        run,
        prepare_id,
        status=RuntimeNodeStatus.SUCCEEDED,
        observation=RuntimeObservation(
            node_id=prepare_id,
            facts={"phase": "prepare", "checkpoint_restored": True},
        ),
    )
    RuntimeStateMachine.mark_ready(run)

    result = asyncio.run(service.run(live_request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.last_request is not None
    stored = fake.last_request.options["research_analysis_v2"]
    assert isinstance(stored, dict)
    stored_payload = stored["request"]
    assert isinstance(stored_payload, dict)
    expected = expected_control_data(checkpoint_request)
    prepared = expected["research_analysis_prepared"]
    assert isinstance(prepared, dict)
    assert stored_payload == prepared["payload"]
    assert stored_payload["research_question"] != (
        "A different live request must not win"
    )
    assert fake.calls == 1


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
    assert run.iteration == run.budget.max_iterations - 1
    assert fake.calls == run.budget.max_iterations
    prepare_id, execute_id, verify_id = service._current_node_ids(run)
    assert prepare_id is not None
    assert run.nodes[prepare_id].status == RuntimeNodeStatus.SUCCEEDED
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
    assert "analysis.prepare.replan.1" in run.nodes
    assert "replan.1" in run.plan.nodes[0].node_id
    assert run.plan.nodes[1].depends_on == [run.plan.nodes[0].node_id]
    assert run.plan.nodes[2].depends_on == [run.plan.nodes[1].node_id]
    assert run.status.value == "completed"


def test_research_analysis_runtime_needs_review_requires_approval() -> None:
    fake = FakeInternalAgents(make_result(analysis_status="needs_review"))
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = AgentRun(
        run_id="run-research-needs-review",
        task_id=request.task_id,
        goal="research analysis",
        plan=service.build_plan(request),
    )

    with pytest.raises(RuntimeRunSuspended) as suspended:
        asyncio.run(service.run(request, run))

    assert suspended.value.status == RuntimeRunStatus.WAITING_APPROVAL
    assert run.status == RuntimeRunStatus.WAITING_APPROVAL
    _prepare_id, _execute_id, verify_id = service._current_node_ids(run)
    verification = run.nodes[verify_id].observation
    assert verification is not None
    assert verification.facts["requires_review"] is True
    assert verification.facts["replan_required"] is False
    assert run.last_decision is not None
    assert run.last_decision.action.value == "request_approval"
    assert run.last_decision.approval_scope == "research_analysis_result_review"
    assert fake.calls == 1


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
    prepare_id, execute_id, _verify_id = service._current_node_ids(run)
    assert prepare_id is not None
    RuntimeStateMachine.mark_ready(run)
    RuntimeStateMachine.start_node(run, prepare_id)
    RuntimeStateMachine.complete_node(
        run,
        prepare_id,
        status=RuntimeNodeStatus.SUCCEEDED,
        observation=RuntimeObservation(
            node_id=prepare_id,
            facts={"phase": "prepare"},
        ),
    )
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
