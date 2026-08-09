from __future__ import annotations

from typing import Any

import pytest
from app.contracts import RuntimeReconciliationSubmission
from app.core.config import Settings
from app.database.base import Base
from app.models import SessionModel, TaskModel, TaskStatus
from app.providers.mock import MockAgentProvider
from app.repositories import AgentRunRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeRunStatus,
    RuntimeStateMachine,
)
from app.services.runtime_child_run import RuntimeChildRunService
from app.services.task_control_service import TaskControlService
from app.services.task_runner import TaskRunner
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _run(
    run_id: str,
    task_id: str,
    *,
    status: RuntimeRunStatus,
    control_data: dict[str, Any],
    node_id: str = "runtime.node",
) -> AgentRun:
    run = AgentRun(
        run_id=run_id,
        task_id=task_id,
        goal="checkpoint control data",
        plan=AgentRunPlan(
            plan_id=f"plan-{run_id}",
            goal="checkpoint control data",
            nodes=[
                RuntimeNode(
                    node_id=node_id,
                    node_type="tool",
                    handler_id="test.runtime.control",
                )
            ],
        ),
        status=status,
        control_data=control_data,
    )
    return run


async def _open_database(
    tmp_path: Any,
    *,
    task_id: str,
    task_status: TaskStatus,
) -> tuple[Any, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / f'{task_id}.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            SessionModel(
                id=f"session-{task_id}",
                user_id="runtime-control-user",
                course_id="CT",
            )
        )
        session.add(
            TaskModel(
                id=task_id,
                session_id=f"session-{task_id}",
                user_id="runtime-control-user",
                course_id="CT",
                intent="general_qa",
                agent_id="RUNTIME_TEST",
                status=task_status,
                input_content={"canonical_input": {"text": "checkpoint"}},
            )
        )
        await session.commit()
    return engine, session_factory


@pytest.mark.asyncio
async def test_pause_checkpoint_preserves_runtime_state_and_consumes_stale_approval(
    tmp_path: Any,
) -> None:
    engine, session_factory = await _open_database(
        tmp_path,
        task_id="runtime-checkpoint-pause",
        task_status=TaskStatus.RUNNING,
    )
    try:
        business_data = {
            "request": {"canonical_input": {"text": "original"}},
            "prepared": {"payload": "prepared-value"},
            "goal_intake": {"objective": "preserve this"},
            "node_inputs": {"runtime.node": {"value": 42}},
        }
        run = _run(
            "runtime-checkpoint-pause-run",
            "runtime-checkpoint-pause",
            status=RuntimeRunStatus.PAUSED,
            control_data={
                **business_data,
                "suspended_child_run_id": "child-pause-run",
            },
        )
        async with session_factory() as session:
            repository = AgentRunRepository(session)
            await repository.create(
                run,
                agent_id="RUNTIME_TEST",
                provider="mock",
            )
            model = await repository.get(run.run_id)
            assert model is not None
            model.control_data = {
                "suspended_child_run_id": "child-pause-run",
                "user_input": {"confirmed": True},
            }
            await session.commit()

        runner = object.__new__(TaskRunner)
        runner.session_factory = session_factory
        await runner._checkpoint_runtime_run(run)

        async with session_factory() as session:
            restored = await AgentRunRepository(session).restore(run.run_id)
            assert restored is not None
            assert restored.control_request == ""
            assert restored.control_data == {
                **business_data,
                "suspended_child_run_id": "child-pause-run",
                "user_input": {"confirmed": True},
            }

            model = await AgentRunRepository(session).get(run.run_id)
            assert model is not None
            assert model.control_data == restored.control_data

            # User input is written to the live control row after the last
            # checkpoint. Resuming must merge that newer control with the
            # checkpoint rather than restoring the older payload over it.
            model.status = RuntimeRunStatus.WAITING_INPUT.value
            model.control_data = {
                **business_data,
                "user_input": {"confirmed": True},
            }
            controls = TaskControlService(
                session,
                MockAgentProvider(),
                Settings(app_env="test", _env_file=None),
            )
            resumed = await controls.resume("runtime-checkpoint-pause")
            assert resumed.status == TaskStatus.QUEUED
            resumed_model = await AgentRunRepository(session).get(run.run_id)
            assert resumed_model is not None
            assert resumed_model.control_data["user_input"] == {
                "confirmed": True
            }

        running = _run(
            "runtime-checkpoint-approval-run",
            "runtime-checkpoint-pause",
            status=RuntimeRunStatus.RUNNING,
            control_data=business_data,
        )
        async with session_factory() as session:
            repository = AgentRunRepository(session)
            await repository.create(
                running,
                agent_id="RUNTIME_TEST",
                provider="mock",
            )
            model = await repository.get(running.run_id)
            assert model is not None
            model.control_data = {
                **business_data,
                "approved": True,
                "approval_scope": "sensitive.scope",
            }
            await session.commit()

        await runner._checkpoint_runtime_run(running)

        async with session_factory() as session:
            restored = await AgentRunRepository(session).restore(running.run_id)
            assert restored is not None
            assert restored.control_data == business_data
            assert "approved" not in restored.control_data
            assert "approval_scope" not in restored.control_data
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reconcile_checkpoint_preserves_runtime_control_data(
    tmp_path: Any,
) -> None:
    engine, session_factory = await _open_database(
        tmp_path,
        task_id="runtime-checkpoint-reconcile",
        task_status=TaskStatus.WAITING_USER,
    )
    try:
        business_data = {
            "request": {"canonical_input": {"text": "reconcile"}},
            "prepared": {"payload": "prepared-value"},
            "goal_intake": {"objective": "preserve this"},
            "node_inputs": {"runtime.node": {"value": 7}},
            "user_input": {"confirmed": True},
        }
        run = _run(
            "runtime-checkpoint-reconcile-run",
            "runtime-checkpoint-reconcile",
            status=RuntimeRunStatus.CREATED,
            control_data=business_data,
        )
        RuntimeStateMachine.mark_ready(run)
        RuntimeStateMachine.start_node(run, "runtime.node")
        run.status = RuntimeRunStatus.PAUSED
        run.nodes["runtime.node"].error_code = (
            "in_flight_execution_requires_reconciliation"
        )
        async with session_factory() as session:
            repository = AgentRunRepository(session)
            await repository.create(
                run,
                agent_id="RUNTIME_TEST",
                provider="mock",
            )
            model = await repository.get(run.run_id)
            assert model is not None
            expected_state_version = model.state_version
            controls = TaskControlService(
                session,
                MockAgentProvider(),
                Settings(app_env="test", _env_file=None),
            )
            task = await controls.reconcile(
                "runtime-checkpoint-reconcile",
                RuntimeReconciliationSubmission(
                    node_id="runtime.node",
                    reconciliation_id=run.nodes["runtime.node"].reconciliation_id,
                    outcome="succeeded",
                    facts={"external_status": "confirmed"},
                    expected_state_version=expected_state_version,
                ),
            )
            assert task.status == TaskStatus.QUEUED

        async with session_factory() as session:
            restored = await AgentRunRepository(session).restore(run.run_id)
            assert restored is not None
            assert restored.status == RuntimeRunStatus.PAUSED
            assert restored.control_request == ""
            assert restored.control_data == business_data
            assert restored.nodes["runtime.node"].status == (
                RuntimeNodeStatus.SUCCEEDED
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_child_pause_keeps_parent_runtime_checkpoint_data(tmp_path: Any) -> None:
    engine, session_factory = await _open_database(
        tmp_path,
        task_id="runtime-checkpoint-child",
        task_status=TaskStatus.WAITING_USER,
    )
    try:
        parent = _run(
            "runtime-checkpoint-parent",
            "runtime-checkpoint-child",
            status=RuntimeRunStatus.PAUSED,
            control_data={
                "request": {"canonical_input": {"text": "parent"}},
                "prepared": {"payload": "parent-prepared"},
                "goal_intake": {"objective": "parent goal"},
                "node_inputs": {"runtime.node": {"value": 11}},
            },
        )
        child = _run(
            "runtime-checkpoint-child-run",
            "runtime-checkpoint-child",
            status=RuntimeRunStatus.PAUSED,
            control_data={"request": {"canonical_input": {"text": "child"}}},
        )
        async with session_factory() as session:
            repository = AgentRunRepository(session)
            await repository.create(
                parent,
                agent_id="RUNTIME_TEST",
                provider="mock",
            )
            await repository.create(
                child,
                agent_id="RUNTIME_TEST",
                provider="mock",
                run_kind="subagent",
                parent_run_id=parent.run_id,
                parent_node_id="runtime.node",
            )
            await session.commit()

        RuntimeChildRunService._mark_parent_suspension(parent, child)
        runner = object.__new__(TaskRunner)
        runner.session_factory = session_factory
        await runner._checkpoint_runtime_run(parent)

        async with session_factory() as session:
            restored = await AgentRunRepository(session).restore(parent.run_id)
            assert restored is not None
            assert restored.control_data == {
                "request": {"canonical_input": {"text": "parent"}},
                "prepared": {"payload": "parent-prepared"},
                "goal_intake": {"objective": "parent goal"},
                "node_inputs": {"runtime.node": {"value": 11}},
                "suspended_child_run_id": child.run_id,
            }
    finally:
        await engine.dispose()
