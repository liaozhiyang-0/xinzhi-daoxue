from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from app.core.errors import ConflictError
from app.database.base import Base
from app.models import SessionModel, TaskEventModel, TaskModel, TaskStatus
from app.repositories import AgentRunRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeNode,
    RuntimeRunStatus,
)
from app.services.learning_loop import LearningLoopService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class _ContinueRuntime:
    run_kind = "teaching_interaction"
    agent_id = "TEACHING_INTERACTION_V1"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def continue_run(
        self,
        _session: AsyncSession,
        _task: TaskModel,
        run: AgentRun,
    ) -> SimpleNamespace:
        self.calls.append(dict(run.control_data))
        run.status = RuntimeRunStatus.COMPLETED
        return SimpleNamespace(response=None)


async def _open_database(
    tmp_path: Any,
) -> tuple[Any, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'learning-runtime-control.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _create_run(
    session: AsyncSession,
    *,
    run_id: str,
    status: RuntimeRunStatus,
) -> None:
    session.add(
        SessionModel(
            id=f"{run_id}-session",
            user_id="learning-user",
            course_id="CT",
        )
    )
    session.add(
        TaskModel(
            id=f"{run_id}-task",
            session_id=f"{run_id}-session",
            user_id="learning-user",
            course_id="CT",
            intent="learning",
            status=TaskStatus.RUNNING,
            agent_id="TEACHING_INTERACTION_V1",
            input_content={"canonical_input": {"text": "control"}},
        )
    )
    plan = AgentRunPlan(
        plan_id=f"learning-control:{run_id}",
        version="learning-control-test-v1",
        goal="exercise LearningLoop durable control",
        nodes=[
            RuntimeNode(
                node_id="learning.control.node",
                node_type="tool",
                handler_id="learning.control.test",
            )
        ],
        success_criteria=["control_checkpoint_persisted"],
    )
    run = AgentRun(
        run_id=run_id,
        task_id=f"{run_id}-task",
        goal=plan.goal,
        plan=plan,
        status=status,
        request_snapshot={
            "learning_action": {
                "source_task_id": f"{run_id}-task",
                "user_id": "learning-user",
                "action": "request_more_hint",
                "idempotency_key": f"action-{run_id}",
                "student_answer": "",
                "payload": {},
            },
            "interaction_id": f"interaction-{run_id}",
        },
    )
    await AgentRunRepository(session).create(
        run,
        agent_id="TEACHING_INTERACTION_V1",
        provider="local",
        workflow_version="learning-control-test-v1",
        run_kind="teaching_interaction",
    )


def _service(runtime: _ContinueRuntime) -> LearningLoopService:
    return LearningLoopService(teaching_interaction_runtime=runtime)


@pytest.mark.asyncio
async def test_learning_control_rejects_stale_state_version_without_checkpoint_mutation(
    tmp_path: Any,
) -> None:
    engine, session_factory = await _open_database(tmp_path)
    runtime = _ContinueRuntime()
    try:
        async with session_factory() as session:
            await _create_run(
                session,
                run_id="learning-cas",
                status=RuntimeRunStatus.RUNNING,
            )
            await session.commit()
            service = _service(runtime)

            with pytest.raises(ConflictError, match="state version"):
                await service.control_runtime_interaction(
                    session,
                    "learning-cas",
                    action="pause",
                    user_id="learning-user",
                    expected_state_version=0,
                    idempotency_key="pause-cas-0001",
                )
            await session.rollback()

        async with session_factory() as session:
            model = await AgentRunRepository(session).get("learning-cas")
            assert model is not None
            assert model.state_version == 1
            assert model.status == RuntimeRunStatus.RUNNING.value
            assert model.control_request == ""
            assert model.control_data == {}
            checkpoints = await AgentRunRepository(session).list_checkpoints(
                "learning-cas"
            )
            assert len(checkpoints) == 1
            assert runtime.calls == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_learning_pause_persists_checkpoint_marker_and_control_event(
    tmp_path: Any,
) -> None:
    engine, session_factory = await _open_database(tmp_path)
    runtime = _ContinueRuntime()
    try:
        async with session_factory() as session:
            await _create_run(
                session,
                run_id="learning-pause",
                status=RuntimeRunStatus.RUNNING,
            )
            await session.commit()
            outcome = await _service(runtime).control_runtime_interaction(
                session,
                "learning-pause",
                action="pause",
                user_id="learning-user",
                expected_state_version=1,
                idempotency_key="pause-learning-0001",
            )
            assert outcome.status == RuntimeRunStatus.PAUSED.value
            assert outcome.state_version == 2
            assert runtime.calls == []

        async with session_factory() as session:
            repository = AgentRunRepository(session)
            model = await repository.get("learning-pause")
            assert model is not None
            assert model.status == RuntimeRunStatus.PAUSED.value
            assert model.control_request == "pause"
            assert model.state_version == 2
            assert model.control_data["learning_runtime_control"] == {
                "action": "pause",
                "idempotency_key": "pause-learning-0001",
                "status": RuntimeRunStatus.RUNNING.value,
                "state_version": 2,
            }
            checkpoints = await repository.list_checkpoints("learning-pause")
            assert checkpoints[-1].status == RuntimeRunStatus.PAUSED.value
            assert checkpoints[-1].state_version == 2
            events = list(
                await session.scalars(
                    select(TaskEventModel).where(
                        TaskEventModel.task_id == "learning-pause-task"
                    )
                )
            )
            assert len(events) == 1
            assert events[0].event_data["data"] == {
                "stage_id": "learning_runtime_control",
                "status": "pause_applied",
                "runtime_run_id": "learning-pause",
                "state_version": 2,
                "input_keys": [],
            }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_learning_resume_consumes_checkpoint_and_replays_same_idempotency_key(
    tmp_path: Any,
) -> None:
    engine, session_factory = await _open_database(tmp_path)
    runtime = _ContinueRuntime()
    try:
        async with session_factory() as session:
            await _create_run(
                session,
                run_id="learning-resume",
                status=RuntimeRunStatus.PAUSED,
            )
            await session.commit()
            service = _service(runtime)
            first = await service.control_runtime_interaction(
                session,
                "learning-resume",
                action="resume",
                user_id="learning-user",
                expected_state_version=1,
                idempotency_key="resume-learning-0001",
            )
            assert first.status == RuntimeRunStatus.COMPLETED.value
            assert first.state_version == 3
            assert len(runtime.calls) == 1
            assert "user_input" not in runtime.calls[0]

            second = await service.control_runtime_interaction(
                session,
                "learning-resume",
                action="resume",
                user_id="learning-user",
                expected_state_version=1,
                idempotency_key="resume-learning-0001",
            )
            assert second.status == RuntimeRunStatus.COMPLETED.value
            assert second.state_version == 3
            assert len(runtime.calls) == 1
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_learning_input_persists_payload_before_continue_and_emits_keys(
    tmp_path: Any,
) -> None:
    engine, session_factory = await _open_database(tmp_path)
    runtime = _ContinueRuntime()
    try:
        async with session_factory() as session:
            await _create_run(
                session,
                run_id="learning-input",
                status=RuntimeRunStatus.WAITING_INPUT,
            )
            await session.commit()
            outcome = await _service(runtime).control_runtime_interaction(
                session,
                "learning-input",
                action="input",
                user_id="learning-user",
                expected_state_version=1,
                data={"clarification": "请确认单位", "confirmed": True},
                idempotency_key="input-learning-0001",
            )
            assert outcome.status == RuntimeRunStatus.COMPLETED.value
            assert outcome.state_version == 3
            assert runtime.calls == [
                {
                    "user_input": {
                        "clarification": "请确认单位",
                        "confirmed": True,
                    },
                    "learning_runtime_control": {
                        "action": "input",
                        "idempotency_key": "input-learning-0001",
                        "status": RuntimeRunStatus.WAITING_INPUT.value,
                        "state_version": 2,
                    },
                }
            ]

            repository = AgentRunRepository(session)
            model = await repository.get("learning-input")
            assert model is not None
            assert model.control_data["user_input"] == {
                "clarification": "请确认单位",
                "confirmed": True,
            }
            events = list(
                await session.scalars(
                    select(TaskEventModel).where(
                        TaskEventModel.task_id == "learning-input-task"
                    )
                )
            )
            assert events[-1].event_data["data"]["status"] == "input_applied"
            assert events[-1].event_data["data"]["input_keys"] == [
                "clarification",
                "confirmed",
            ]
    finally:
        await engine.dispose()
