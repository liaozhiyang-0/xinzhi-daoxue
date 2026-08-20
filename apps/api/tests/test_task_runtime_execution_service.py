from __future__ import annotations

from time import perf_counter
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from app.contracts import AgentRequest
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeNode,
    RuntimeNodeError,
    RuntimeNodeState,
    RuntimeNodeStatus,
    RuntimeRunStatus,
)
from app.services.runtime_launch_policy import (
    RuntimeLaunchDecision,
    RuntimeLaunchMode,
)
from app.services.task_runtime_execution import TaskRuntimeExecutionService
from app.services.task_runtime_preparation import PreparedRuntimeTask


def _prepared_run(status: RuntimeRunStatus) -> AgentRun:
    plan = AgentRunPlan(
        plan_id="plan.test",
        goal="complete the task",
        nodes=[RuntimeNode(node_id="answer", node_type="agent", handler_id="answer")],
    )
    run = AgentRun(
        run_id="run.test",
        task_id="task.test",
        goal=plan.goal,
        status=status,
        plan=plan,
        nodes={"answer": RuntimeNodeState(node_id="answer")},
    )
    return run


def _prepared_task(run: AgentRun) -> PreparedRuntimeTask:
    return PreparedRuntimeTask(
        request=AgentRequest(session_id="session.test", user_id="user.test"),
        runtime_run=run,
        runtime_plan=run.plan,
        launch_decision=RuntimeLaunchDecision(
            agent_id="agent.test",
            mode=RuntimeLaunchMode.DEFAULT,
            source="test",
            reason="test",
        ),
        agent_id="agent.test",
        agent_definition=cast(Any, object()),
        execution_plan=cast(Any, object()),
        intent_plan=None,
        conversation_bundle=None,
        route_latency_ms=0,
        route_metadata={},
    )


def _service(boundary: Mock) -> TaskRuntimeExecutionService:
    return TaskRuntimeExecutionService(
        runtime_boundary=boundary,
        runtime_hooks=cast(Any, Mock()),
        result_pipeline=cast(Any, Mock()),
        progress=cast(Any, Mock()),
        post_processing=cast(Any, Mock()),
        plan_proposals_enabled=False,
    )


@pytest.mark.asyncio
async def test_failed_runtime_preserves_node_error_code() -> None:
    run = _prepared_run(RuntimeRunStatus.FAILED)
    run.nodes["answer"].status = RuntimeNodeStatus.FAILED
    run.nodes["answer"].error_code = "provider_timeout"
    boundary = Mock()
    boundary.execute = AsyncMock(return_value=None)

    with pytest.raises(RuntimeNodeError) as exc_info:
        await _service(boundary).execute(
            _prepared_task(run),
            runner_started=perf_counter(),
        )

    assert exc_info.value.error_code == "provider_timeout"


@pytest.mark.asyncio
async def test_completed_runtime_without_result_uses_result_missing_code() -> None:
    run = _prepared_run(RuntimeRunStatus.COMPLETED)
    boundary = Mock()
    boundary.execute = AsyncMock(return_value=None)

    with pytest.raises(RuntimeNodeError) as exc_info:
        await _service(boundary).execute(
            _prepared_task(run),
            runner_started=perf_counter(),
        )

    assert exc_info.value.error_code == "provider_runtime_result_missing"
