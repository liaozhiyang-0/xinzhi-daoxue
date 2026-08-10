from __future__ import annotations

import asyncio

import pytest
from app.contracts import (
    AgentRequest,
    AgentResult,
    RuntimeReconciliationSubmission,
)
from app.core.config import Settings
from app.database.base import Base
from app.models import SessionModel, TaskModel, TaskStatus
from app.providers.mock import MockAgentProvider
from app.repositories import AgentRunRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeNode,
    RuntimeNodeError,
    RuntimeNodeSuspended,
    RuntimeRunStatus,
    RuntimeSubagentDefinition,
)
from app.services.runtime_child_run import RuntimeChildRunService
from app.services.task_control_service import TaskControlService
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class FakeInternalAgents:
    def __init__(self) -> None:
        self.calls = 0

    async def run(
        self,
        agent_id: str,
        _request: AgentRequest,
        _context: object,
    ) -> AgentResult:
        self.calls += 1
        return AgentResult(agent_id=agent_id, provider="mock", answer="child answer")


class FailOnceInternalAgents(FakeInternalAgents):
    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object,
    ) -> AgentResult:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeNodeError("structured_output_failed")
        return AgentResult(agent_id=agent_id, provider="mock", answer="child answer")


def test_typed_subagent_has_durable_child_run_and_reuses_terminal_result(
    tmp_path,
) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'child-run.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        fake = FakeInternalAgents()
        service = RuntimeChildRunService(session_factory, fake)
        parent = AgentRun(
            run_id="parent-run",
            task_id="task-child",
            goal="run a child agent",
            plan=AgentRunPlan(
                plan_id="parent-plan",
                goal="run a child agent",
                nodes=[
                    RuntimeNode(
                        node_id="parent.execute",
                        node_type="subagent",
                        handler_id="subagent.TEST_AGENT",
                    )
                ],
            ),
        )
        request = AgentRequest(
            task_id="task-child",
            session_id="session-child",
            user_id="user-child",
        )
        async with session_factory() as db:
            db.add(
                SessionModel(
                    id="session-child",
                    user_id="user-child",
                    course_id="CT",
                )
            )
            db.add(
                TaskModel(
                    id="task-child",
                    session_id="session-child",
                    user_id="user-child",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="GENERAL_QUESTION_V1",
                    input_content={"text": "child"},
                )
            )
            await db.flush()
            await AgentRunRepository(db).create(
                parent,
                agent_id="GENERAL_QUESTION_V1",
                provider="mock",
            )
            await db.commit()

        definition = RuntimeSubagentDefinition(
            subagent_id="TEST_AGENT",
            target_agent_id="GENERAL_QUESTION_V1",
        )
        result, child_run_id = await service.execute_with_run(
            parent,
            parent.plan.nodes[0],
            definition,
            request,
        )
        assert result.answer == "child answer"
        assert fake.calls == 1

        async with session_factory() as db:
            repository = AgentRunRepository(db)
            child = await repository.get(child_run_id)
            assert child is not None
            assert child.run_kind == "subagent"
            assert child.parent_run_id == "parent-run"
            assert child.parent_node_id == "parent.execute"
            assert len(await repository.list_checkpoints(child_run_id)) >= 3
            assert parent.budget.model_calls == 1
            assert parent.budget.child_consumption[child_run_id] == {
                "model_calls": 1,
                "tool_calls": 0,
                "subagent_runs": 0,
            }
            restarted_parent = await repository.restore(parent.run_id)
            assert restarted_parent is not None

        repeated, repeated_id = await service.execute_with_run(
            restarted_parent,
            parent.plan.nodes[0],
            definition,
            request,
        )
        assert repeated.answer == "child answer"
        assert repeated_id == child_run_id
        assert fake.calls == 1
        assert restarted_parent.budget.child_consumption[child_run_id][
            "model_calls"
        ] == 1
        await engine.dispose()

    asyncio.run(scenario())


def test_failed_child_without_result_gets_a_fresh_replan_attempt(tmp_path) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'child-replan.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        fake = FailOnceInternalAgents()
        service = RuntimeChildRunService(session_factory, fake)
        parent = AgentRun(
            run_id="parent-replan",
            task_id="task-child-replan",
            goal="retry a failed child agent",
            plan=AgentRunPlan(
                plan_id="parent-replan-plan",
                goal="retry a failed child agent",
                nodes=[
                    RuntimeNode(
                        node_id="parent.execute",
                        node_type="subagent",
                        handler_id="subagent.TEST_AGENT",
                    )
                ],
            ),
        )
        request = AgentRequest(
            task_id="task-child-replan",
            session_id="session-child-replan",
            user_id="user-child-replan",
        )
        async with session_factory() as db:
            db.add(
                SessionModel(
                    id="session-child-replan",
                    user_id="user-child-replan",
                    course_id="CT",
                )
            )
            db.add(
                TaskModel(
                    id="task-child-replan",
                    session_id="session-child-replan",
                    user_id="user-child-replan",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="GENERAL_QUESTION_V1",
                    input_content={"text": "retry"},
                )
            )
            await db.flush()
            await AgentRunRepository(db).create(
                parent,
                agent_id="GENERAL_QUESTION_V1",
                provider="mock",
            )
            await db.commit()

        definition = RuntimeSubagentDefinition(
            subagent_id="TEST_AGENT",
            target_agent_id="GENERAL_QUESTION_V1",
        )
        with pytest.raises(RuntimeNodeError, match="subagent_child_result_missing"):
            await service.execute_with_run(
                parent,
                parent.plan.nodes[0],
                definition,
                request,
            )

        result, replacement_id = await service.execute_with_run(
            parent,
            parent.plan.nodes[0],
            definition,
            request,
        )
        assert result.answer == "child answer"
        assert fake.calls == 2

        async with session_factory() as db:
            children = await AgentRunRepository(db).list_children(parent.run_id)
            assert len(children) == 2
            assert replacement_id == children[-1].id
            assert children[0].status == RuntimeRunStatus.FAILED.value
            assert children[1].status == RuntimeRunStatus.COMPLETED.value
        await engine.dispose()

    asyncio.run(scenario())


def test_parent_pause_propagates_to_child_and_resume_does_not_repeat_call(
    tmp_path,
) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'child-pause.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        fake = FakeInternalAgents()
        service = RuntimeChildRunService(session_factory, fake)
        parent = AgentRun(
            run_id="parent-pause",
            task_id="task-child-pause",
            goal="pause a child agent",
            plan=AgentRunPlan(
                plan_id="parent-pause-plan",
                goal="pause a child agent",
                nodes=[
                    RuntimeNode(
                        node_id="parent.execute",
                        node_type="subagent",
                        handler_id="subagent.TEST_AGENT",
                    )
                ],
            ),
        )
        request = AgentRequest(
            task_id="task-child-pause",
            session_id="session-child-pause",
            user_id="user-child-pause",
        )
        async with session_factory() as db:
            db.add(
                SessionModel(
                    id="session-child-pause",
                    user_id="user-child-pause",
                    course_id="CT",
                )
            )
            db.add(
                TaskModel(
                    id="task-child-pause",
                    session_id="session-child-pause",
                    user_id="user-child-pause",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="GENERAL_QUESTION_V1",
                    input_content={"text": "pause"},
                )
            )
            repository = AgentRunRepository(db)
            await db.flush()
            await repository.create(
                parent,
                agent_id="GENERAL_QUESTION_V1",
                provider="mock",
            )
            await repository.request_control(parent.run_id, "pause")
            await db.commit()

        definition = RuntimeSubagentDefinition(
            subagent_id="TEST_AGENT",
            target_agent_id="GENERAL_QUESTION_V1",
        )
        with pytest.raises(RuntimeNodeSuspended):
            await service.execute_with_run(
                parent,
                parent.plan.nodes[0],
                definition,
                request,
            )
        assert fake.calls == 0

        async with session_factory() as db:
            repository = AgentRunRepository(db)
            child_model = await repository.get_child_for_node(
                parent.run_id,
                "parent.execute",
            )
            assert child_model is not None
            child = await repository.restore(child_model.id)
            assert child is not None
            assert child.status == RuntimeRunStatus.PAUSED
            await repository.clear_control(parent.run_id)
            await db.commit()

        result, child_run_id = await service.execute_with_run(
            parent,
            parent.plan.nodes[0],
            definition,
            request,
        )
        assert result.answer == "child answer"
        assert child_run_id
        assert fake.calls == 1
        assert parent.budget.model_calls == 1
        await engine.dispose()

    asyncio.run(scenario())


def test_child_run_can_wait_for_and_receive_independent_approval(tmp_path) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'child-approval.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        fake = FakeInternalAgents()
        service = RuntimeChildRunService(session_factory, fake)
        parent = AgentRun(
            run_id="parent-approval",
            task_id="task-child-approval",
            goal="approve a child agent",
            plan=AgentRunPlan(
                plan_id="parent-approval-plan",
                goal="approve a child agent",
                nodes=[
                    RuntimeNode(
                        node_id="parent.execute",
                        node_type="subagent",
                        handler_id="subagent.TEST_AGENT",
                    )
                ],
            ),
        )
        request = AgentRequest(
            task_id="task-child-approval",
            session_id="session-child-approval",
            user_id="user-child-approval",
        )
        async with session_factory() as db:
            db.add(
                SessionModel(
                    id="session-child-approval",
                    user_id="user-child-approval",
                    course_id="CT",
                )
            )
            db.add(
                TaskModel(
                    id="task-child-approval",
                    session_id="session-child-approval",
                    user_id="user-child-approval",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="GENERAL_QUESTION_V1",
                    input_content={"text": "approve"},
                )
            )
            repository = AgentRunRepository(db)
            await db.flush()
            await repository.create(
                parent,
                agent_id="GENERAL_QUESTION_V1",
                provider="mock",
            )
            await db.commit()

        definition = RuntimeSubagentDefinition(
            subagent_id="TEST_AGENT",
            target_agent_id="GENERAL_QUESTION_V1",
            requires_approval=True,
        )
        with pytest.raises(RuntimeNodeSuspended):
            await service.execute_with_run(
                parent,
                parent.plan.nodes[0],
                definition,
                request,
            )
        assert fake.calls == 0
        child_run_id = parent.control_data["suspended_child_run_id"]

        async with session_factory() as db:
            repository = AgentRunRepository(db)
            child_model = await repository.get(str(child_run_id))
            assert child_model is not None
            assert child_model.status == RuntimeRunStatus.WAITING_APPROVAL.value
            await repository.request_control(
                child_model.id,
                "",
                control_data={"approved": True},
            )
            await db.commit()

        result, resumed_child_id = await service.execute_with_run(
            parent,
            parent.plan.nodes[0],
            definition,
            request,
        )
        assert result.answer == "child answer"
        assert resumed_child_id == child_run_id
        assert fake.calls == 1
        assert "suspended_child_run_id" not in parent.control_data
        await engine.dispose()

    asyncio.run(scenario())


def test_inflight_side_effect_requires_child_reconciliation_without_replay(
    tmp_path,
) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'child-reconcile.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        fake = FakeInternalAgents()

        def crash_after_provider(_run: AgentRun, _node_ids: object) -> None:
            raise RuntimeError("simulated_process_loss_after_provider")

        service = RuntimeChildRunService(
            session_factory,
            fake,
            after_batch_hook=crash_after_provider,
        )
        parent = AgentRun(
            run_id="parent-reconcile",
            task_id="task-child-reconcile",
            goal="reconcile an uncertain child effect",
            plan=AgentRunPlan(
                plan_id="parent-reconcile-plan",
                goal="reconcile an uncertain child effect",
                nodes=[
                    RuntimeNode(
                        node_id="parent.execute",
                        node_type="subagent",
                        handler_id="subagent.TEST_AGENT",
                    )
                ],
            ),
        )
        request = AgentRequest(
            task_id="task-child-reconcile",
            session_id="session-child-reconcile",
            user_id="user-child-reconcile",
        )
        definition = RuntimeSubagentDefinition(
            subagent_id="TEST_AGENT",
            target_agent_id="GENERAL_QUESTION_V1",
            side_effecting=True,
            replay_safe=False,
        )

        async with session_factory() as db:
            db.add(
                SessionModel(
                    id="session-child-reconcile",
                    user_id="user-child-reconcile",
                    course_id="CT",
                )
            )
            db.add(
                TaskModel(
                    id="task-child-reconcile",
                    session_id="session-child-reconcile",
                    user_id="user-child-reconcile",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="GENERAL_QUESTION_V1",
                    status=TaskStatus.WAITING_USER,
                    input_content={"text": "reconcile"},
                )
            )
            repository = AgentRunRepository(db)
            await db.flush()
            await repository.create(
                parent,
                agent_id="GENERAL_QUESTION_V1",
                provider="mock",
            )
            await db.commit()

        with pytest.raises(RuntimeError, match="simulated_process_loss"):
            await service.execute_with_run(
                parent,
                parent.plan.nodes[0],
                definition,
                request,
            )
        assert fake.calls == 1

        async with session_factory() as db:
            repository = AgentRunRepository(db)
            child_model = await repository.get_child_for_node(
                parent.run_id,
                "parent.execute",
            )
            assert child_model is not None
            child_id = child_model.id
            checkpointed = await repository.restore(child_id)
            assert checkpointed is not None
            assert checkpointed.nodes["subagent.execute"].status.value == "running"
            assert checkpointed.nodes["subagent.execute"].effect_status.value == (
                "in_progress"
            )

        service.after_batch_hook = None
        recovery_events: list[str] = []

        async def record_recovery_event(
            event: str, _run: AgentRun, _node_id: str
        ) -> None:
            recovery_events.append(event)

        with pytest.raises(RuntimeNodeSuspended):
            await service.execute_with_run(
                parent,
                parent.plan.nodes[0],
                definition,
                request,
                event_hook=record_recovery_event,
            )
        assert fake.calls == 1
        assert "node_recovery_required" in recovery_events

        async with session_factory() as db:
            repository = AgentRunRepository(db)
            child_model = await repository.get(child_id)
            assert child_model is not None
            assert child_model.status == RuntimeRunStatus.PAUSED.value
            recovered = await repository.restore(child_id)
            assert recovered is not None
            assert recovered.nodes["subagent.execute"].effect_status.value == (
                "unknown"
            )
            await repository.request_control(
                parent.run_id,
                "",
                control_data={"suspended_child_run_id": child_id},
            )
            await db.commit()

        acknowledged = AgentResult(
            agent_id="GENERAL_QUESTION_V1",
            provider="mock",
            answer="reconciled child answer",
        )
        async with session_factory() as db:
            controls = TaskControlService(
                db,
                MockAgentProvider(),
                Settings(app_env="test", _env_file=None),
            )
            child_model = await AgentRunRepository(db).get(child_id)
            assert child_model is not None
            task = await controls.reconcile(
                "task-child-reconcile",
                RuntimeReconciliationSubmission(
                    runtime_run_id=child_id,
                    node_id="subagent.execute",
                    outcome="succeeded",
                    facts={
                        "result_payload": acknowledged.model_dump(mode="json")
                    },
                    expected_state_version=child_model.state_version,
                ),
            )
            assert task.status == TaskStatus.QUEUED
            parent_model = await AgentRunRepository(db).get(parent.run_id)
            assert parent_model is not None
            assert parent_model.control_data == {}
            await db.commit()

        result, resumed_child_id = await service.execute_with_run(
            parent,
            parent.plan.nodes[0],
            definition,
            request,
        )
        assert result.answer == "reconciled child answer"
        assert resumed_child_id == child_id
        assert fake.calls == 1
        assert parent.budget.child_consumption[child_id]["model_calls"] == 1

        async with session_factory() as db:
            child = await AgentRunRepository(db).restore(child_id)
            assert child is not None
            assert child.status == RuntimeRunStatus.COMPLETED

        await engine.dispose()

    asyncio.run(scenario())
