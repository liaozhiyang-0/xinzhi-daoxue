from __future__ import annotations

import pytest
from app.contracts import AgentRequest, AgentResult
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


def test_runtime_boundary_selects_business_runtime_and_resume_states() -> None:
    boundary = RuntimeExecutionBoundary(
        RuntimeRunLifecycleService(enabled=True),
        ResearchAnalysisRuntimeService(FakeInternalAgents(), enabled=True),  # type: ignore[arg-type]
    )

    assert boundary.is_resumable(RuntimeRunStatus.PAUSED.value)
    assert boundary.is_resumable(RuntimeRunStatus.WAITING_INPUT.value)
    assert not boundary.is_resumable(RuntimeRunStatus.RUNNING.value)

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

    handoff = RuntimeExecutionBoundary.handoff_result(
        result,
        decision=decision,
    )

    assert isinstance(handoff, RuntimeTaskHandoff)
    assert handoff.result is result
    assert handoff.bypass_legacy_execution is True
