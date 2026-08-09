from __future__ import annotations

import pytest
from app.contracts import AgentRequest, AgentResult, AgentResultStatus
from app.core.errors import NotConfiguredError
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeCompatibilitySnapshot,
    RuntimeLaunchSnapshot,
    RuntimeNode,
    RuntimeRunStatus,
)
from app.services.research_analysis_runtime import ResearchAnalysisRuntimeService
from app.services.runtime_execution_boundary import (
    RuntimeExecutionBoundary,
    RuntimeResumeInvariantError,
    RuntimeTaskHandoff,
)
from app.services.runtime_launch_policy import (
    RuntimeLaunchDecision,
    RuntimeLaunchMode,
)
from app.services.runtime_run_lifecycle import RuntimeRunLifecycleService


class FakeInternalAgents:
    async def run(
        self, agent_id: str, request: AgentRequest, context: object = None
    ) -> None:
        del agent_id, request, context
        return None


def make_request() -> AgentRequest:
    return AgentRequest(
        task_id="task-boundary",
        session_id="session-boundary",
        user_id="user-boundary",
        options={
            "research_analysis_v2": {
                "request": {
                    "research_question": "Does the intervention change the outcome?",
                    "analysis_goal": "compare",
                    "design": "experimental_comparison",
                }
            }
        },
    )


def make_handoff_run(status: RuntimeRunStatus) -> AgentRun:
    return AgentRun(
        run_id="handoff-run",
        task_id="handoff-task",
        goal="handoff test",
        status=status,
        plan=AgentRunPlan(
            plan_id="handoff-plan",
            version="1",
            goal="handoff test",
            nodes=[
                RuntimeNode(
                    node_id="execute",
                    node_type="workflow",
                    handler_id="test.execute",
                )
            ],
        ),
    )


def test_runtime_boundary_selects_business_runtime_and_resume_states() -> None:
    boundary = RuntimeExecutionBoundary(
        RuntimeRunLifecycleService(enabled=True),
        ResearchAnalysisRuntimeService(FakeInternalAgents(), enabled=True),  # type: ignore[arg-type]
    )

    assert boundary.is_resumable(RuntimeRunStatus.PAUSED.value)
    assert boundary.is_resumable(RuntimeRunStatus.WAITING_INPUT.value)
    assert boundary.is_resumable(RuntimeRunStatus.RUNNING.value)
    assert not boundary.is_resumable(RuntimeRunStatus.CREATED.value)

    plan = boundary.build_plan(
        ResearchAnalysisRuntimeService.agent_id,
        make_request(),
    )
    assert plan is not None
    assert [node.node_id for node in plan.nodes] == [
        "analysis.execute",
        "analysis.verify",
    ]
    assert boundary.build_plan("OTHER_AGENT", make_request()) is None


def test_resume_keeps_checkpoint_request_without_default_launch_preparation() -> None:
    boundary = RuntimeExecutionBoundary(
        RuntimeRunLifecycleService(enabled=True),
        None,
        business_services=[],
    )
    request = make_request()

    resumed = boundary.prepare_request_for_launch(
        "GENERAL_QUESTION_V1",
        request,
        RuntimeLaunchMode.DEFAULT,
        runtime_resume=True,
    )

    assert resumed == request


def test_new_default_launch_still_prepares_runtime_request() -> None:
    class FakeRuntimeService:
        agent_id = "GENERAL_QUESTION_V1"
        runtime_option_key = "general_question_runtime"

        def supports(self, agent_id: str, _request: AgentRequest) -> bool:
            return agent_id == self.agent_id

        def build_plan(self, _request: AgentRequest) -> AgentRunPlan:
            return AgentRunPlan(
                plan_id="fake-plan",
                version="1",
                goal="fake",
                nodes=[
                    RuntimeNode(
                        node_id="execute",
                        node_type="workflow",
                        handler_id="fake.execute",
                    )
                ],
            )

        async def run(self, *_args: object, **_kwargs: object) -> None:
            return None

    boundary = RuntimeExecutionBoundary(
        RuntimeRunLifecycleService(enabled=True),
        None,
        business_services=[FakeRuntimeService()],  # type: ignore[arg-type]
    )
    request = make_request()

    prepared = boundary.prepare_request_for_launch(
        "GENERAL_QUESTION_V1",
        request,
        RuntimeLaunchMode.DEFAULT,
    )

    assert prepared.options["general_question_runtime"] == {"execute": True}


def test_runtime_boundary_rejects_checkpoint_route_drift() -> None:
    plan = AgentRunPlan(
        plan_id="compatibility-plan",
        version="1",
        goal="resume safely",
        nodes=[
            RuntimeNode(
                node_id="execute",
                node_type="workflow",
                handler_id="test.execute",
            )
        ],
    )
    run = AgentRun(
        run_id="compatibility-run",
        task_id="compatibility-task",
        goal="resume safely",
        plan=plan,
        launch_decision=RuntimeLaunchSnapshot(
            agent_id="GENERAL_QUESTION_V1",
            mode="canary",
            source="configured_launch_mode",
            reason="test",
        ),
        compatibility_snapshot=RuntimeCompatibilitySnapshot(
            preparation_status="prepared",
            agent_id="GENERAL_QUESTION_V1",
            route_revision=2,
            execution_plan_agent_id="GENERAL_QUESTION_V1",
        ),
    )
    request = AgentRequest(
        task_id="compatibility-task",
        session_id="compatibility-session",
        user_id="compatibility-user",
        options={
            "_routing": {
                "agent_id": "GENERAL_QUESTION_V1",
                "route_revision": 1,
            }
        },
    )

    with pytest.raises(RuntimeResumeInvariantError, match="route revision"):
        RuntimeExecutionBoundary.validate_resume_invariants(
            run,
            task_agent_id="GENERAL_QUESTION_V1",
            request=request,
            execution_plan=None,
        )


def test_runtime_handoff_prevents_legacy_execution_after_runtime_result() -> None:
    decision = RuntimeLaunchDecision(
        agent_id="GENERAL_QUESTION_V1",
        mode=RuntimeLaunchMode.CANARY,
        source="test",
        reason="test",
    )
    result = AgentResult(
        agent_id="GENERAL_QUESTION_V1",
        provider="local_agent",
        answer="runtime result",
    )
    run = make_handoff_run(RuntimeRunStatus.COMPLETED)

    handoff = RuntimeExecutionBoundary.handoff_result(
        result,
        decision=decision,
        run=run,
    )

    assert isinstance(handoff, RuntimeTaskHandoff)
    assert handoff.result is result
    assert handoff.bypass_legacy_execution is True


def test_failed_runtime_result_cannot_bypass_legacy_execution() -> None:
    decision = RuntimeLaunchDecision(
        agent_id="GENERAL_QUESTION_V1",
        mode=RuntimeLaunchMode.CANARY,
        source="test",
        reason="test",
    )
    result = AgentResult(
        agent_id="GENERAL_QUESTION_V1",
        provider="local_agent",
        answer="partial answer",
    )
    run = make_handoff_run(RuntimeRunStatus.FAILED)

    handoff = RuntimeExecutionBoundary.handoff_result(
        result,
        decision=decision,
        run=run,
    )

    assert handoff.bypass_legacy_execution is False
    assert handoff.legacy_fallback is True
    assert handoff.runtime_status == RuntimeRunStatus.FAILED.value
    assert handoff.result is not None
    assert handoff.result.status == AgentResultStatus.FAILED
    assert run.control_data["runtime_handoff"]["status"] == "legacy_fallback"


def test_default_failed_runtime_is_fail_closed() -> None:
    decision = RuntimeLaunchDecision(
        agent_id="GENERAL_QUESTION_V1",
        mode=RuntimeLaunchMode.DEFAULT,
        source="test",
        reason="test",
    )
    run = make_handoff_run(RuntimeRunStatus.FAILED)
    result = AgentResult(
        agent_id="GENERAL_QUESTION_V1",
        provider="local_agent",
        answer="incorrectly completed result",
    )

    with pytest.raises(NotConfiguredError, match="status=failed"):
        RuntimeExecutionBoundary.handoff_result(
            result,
            decision=decision,
            run=run,
        )
