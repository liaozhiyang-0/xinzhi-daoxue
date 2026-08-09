from __future__ import annotations

import asyncio

from app.contracts import RuntimeInputSubmission, RuntimeReconciliationSubmission
from app.core.config import Settings
from app.database.base import Base
from app.models import SessionModel, TaskModel, TaskStatus
from app.providers.mock import MockAgentProvider
from app.repositories import AgentRunRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeEffectStatus,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeRunStatus,
)
from app.services.runtime_run_lifecycle import RuntimeRunLifecycleService
from app.services.task_control_service import TaskControlService
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def test_pause_resume_and_approval_are_durable_controls(tmp_path) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'runtime-controls.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(app_env="test", _env_file=None)

        async with session_factory() as session:
            session.add(
                SessionModel(
                    id="session-controls",
                    user_id="user-controls",
                    course_id="CT",
                )
            )
            session.add(
                TaskModel(
                    id="task-controls",
                    session_id="session-controls",
                    user_id="user-controls",
                    course_id="CT",
                    intent="research",
                    agent_id="RESEARCH_TEST",
                    status=TaskStatus.RUNNING,
                    input_content={"canonical_input": {"text": "control"}},
                )
            )
            await session.flush()
            lifecycle = RuntimeRunLifecycleService(enabled=True)
            run = await lifecycle.start(
                session,
                task_id="task-controls",
                agent_id="RESEARCH_TEST",
                provider="mock",
                goal="control runtime",
            )
            assert run is not None
            await session.commit()

            controls = TaskControlService(
                session,
                MockAgentProvider(),
                settings,
            )
            paused_task = await controls.pause("task-controls")
            assert paused_task.status == TaskStatus.RUNNING
            runtime_repository = AgentRunRepository(session)
            runtime_model = await runtime_repository.get(run.run_id)
            assert runtime_model is not None
            assert runtime_model.control_request == "pause"

            runtime_model.status = RuntimeRunStatus.PAUSED.value
            runtime_model.control_request = ""
            paused_task.status = TaskStatus.WAITING_USER
            await session.commit()

            resumed_task = await controls.resume("task-controls")
            assert resumed_task.status == TaskStatus.QUEUED
            runtime_model = await runtime_repository.get(run.run_id)
            assert runtime_model is not None
            assert runtime_model.control_request == ""

            runtime_model.status = RuntimeRunStatus.WAITING_APPROVAL.value
            resumed_task.status = TaskStatus.WAITING_REVIEW
            await session.commit()
            approved_task = await controls.approve("task-controls")
            assert approved_task.status == TaskStatus.QUEUED

            runtime_model.status = "waiting_input"
            await session.commit()
            submitted_task = await controls.submit_input(
                "task-controls",
                RuntimeInputSubmission(
                    data={"scope": "2026-Q1", "confirmed": True},
                    expected_state_version=runtime_model.state_version,
                ),
            )
            assert submitted_task.status == TaskStatus.QUEUED
            runtime_model = await runtime_repository.get(run.run_id)
            assert runtime_model is not None
            assert runtime_model.control_data["user_input"] == {
                "scope": "2026-Q1",
                "confirmed": True,
            }

            # Simulate a worker restart after a non-replay-safe node was left
            # in-flight. The control API must require an explicit outcome.
            restored = await runtime_repository.restore(run.run_id)
            assert restored is not None
            node = restored.nodes["legacy.execution"]
            node.error_code = "in_flight_execution_requires_reconciliation"
            restored.status = RuntimeRunStatus.PAUSED
            restored.control_request = ""
            restored.control_data = {}
            await runtime_repository.save_checkpoint(restored)
            runtime_model = await runtime_repository.get(run.run_id)
            assert runtime_model is not None
            reconciled_task = await controls.reconcile(
                "task-controls",
                RuntimeReconciliationSubmission(
                    node_id="legacy.execution",
                    reconciliation_id=restored.nodes[
                        "legacy.execution"
                    ].reconciliation_id,
                    outcome="succeeded",
                    facts={"external_status": "confirmed"},
                    expected_state_version=runtime_model.state_version,
                ),
            )
            assert reconciled_task.status == TaskStatus.QUEUED
            reconciled = await runtime_repository.restore(run.run_id)
            assert reconciled is not None
            assert reconciled.status == RuntimeRunStatus.PAUSED
            assert reconciled.nodes["legacy.execution"].status == (
                RuntimeNodeStatus.SUCCEEDED
            )
            assert reconciled.nodes["legacy.execution"].effect_status == (
                RuntimeEffectStatus.COMPLETED
            )
            assert reconciled.nodes["legacy.execution"].reconciliation_id == (
                "runtime:" + run.run_id + ":legacy.execution"
            )

        await engine.dispose()

    asyncio.run(scenario())


def test_task_controls_can_target_a_child_run(tmp_path) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'runtime-child-controls.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(app_env="test", _env_file=None)

        async with session_factory() as session:
            session.add(
                SessionModel(
                    id="session-child-controls",
                    user_id="user-child-controls",
                    course_id="CT",
                )
            )
            session.add(
                TaskModel(
                    id="task-child-controls",
                    session_id="session-child-controls",
                    user_id="user-child-controls",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="GENERAL_QUESTION_V1",
                    status=TaskStatus.WAITING_USER,
                    input_content={"canonical_input": {"text": "child"}},
                )
            )
            await session.flush()
            parent = AgentRun(
                run_id="parent-control",
                task_id="task-child-controls",
                goal="parent",
                plan=AgentRunPlan(
                    plan_id="parent-control-plan",
                    goal="parent",
                    nodes=[
                        RuntimeNode(
                            node_id="parent.execute",
                            node_type="subagent",
                            handler_id="subagent.TEST_AGENT",
                        )
                    ],
                ),
            )
            child = AgentRun(
                run_id="child-control",
                task_id="task-child-controls",
                run_kind="subagent",
                parent_run_id=parent.run_id,
                parent_node_id="parent.execute",
                goal="child",
                plan=AgentRunPlan(
                    plan_id="child-control-plan",
                    goal="child",
                    nodes=[
                        RuntimeNode(
                            node_id="subagent.execute",
                            node_type="provider",
                            handler_id="subagent.child.invoke",
                        )
                    ],
                ),
            )
            repository = AgentRunRepository(session)
            await repository.create(
                parent,
                agent_id="GENERAL_QUESTION_V1",
                provider="mock",
            )
            await repository.create(
                child,
                agent_id="GENERAL_QUESTION_V1",
                provider="internal",
                run_kind="subagent",
                parent_run_id=parent.run_id,
                parent_node_id="parent.execute",
            )
            parent_model = await repository.get(parent.run_id)
            child_model = await repository.get(child.run_id)
            assert parent_model is not None
            assert child_model is not None
            parent_model.status = RuntimeRunStatus.PAUSED.value
            parent_model.control_data = {
                "suspended_child_run_id": child.run_id
            }
            child_model.status = RuntimeRunStatus.PAUSED.value
            await session.commit()

            controls = TaskControlService(
                session,
                MockAgentProvider(),
                settings,
            )
            resumed = await controls.resume(
                "task-child-controls",
                runtime_run_id=child.run_id,
            )
            assert resumed.status == TaskStatus.QUEUED
            child_model = await repository.get(child.run_id)
            parent_model = await repository.get(parent.run_id)
            assert child_model is not None
            assert parent_model is not None
            assert child_model.control_request == ""
            assert parent_model.control_data == {}

            child_model.status = RuntimeRunStatus.WAITING_APPROVAL.value
            resumed.status = TaskStatus.WAITING_REVIEW
            await session.commit()
            approved = await controls.approve(
                "task-child-controls",
                runtime_run_id=child.run_id,
            )
            assert approved.status == TaskStatus.QUEUED
            child_model = await repository.get(child.run_id)
            assert child_model is not None
            assert child_model.control_data == {"approved": True}

        await engine.dispose()

    asyncio.run(scenario())
