from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from app.contracts import AgentRequest, AgentResult, RuntimeInputSubmission
from app.core.config import Settings
from app.core.errors import ConflictError
from app.database.base import Base
from app.models import SessionModel, TaskModel, TaskStatus
from app.providers.mock import MockAgentProvider
from app.repositories import AgentRunRepository, TaskRepository
from app.runtime import (
    AgentRun,
    RuntimeRunStatus,
    RuntimeRunSuspended,
)
from app.services.knowledge_qa_runtime import KnowledgeQARuntimeService
from app.services.runtime_run_lifecycle import RuntimeRunLifecycleService
from app.services.task_control_service import TaskControlService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class SequencedKnowledgeQA:
    """Deterministic local execution fake; it never reaches a Provider."""

    def __init__(self, *evidence_statuses: str) -> None:
        self.evidence_statuses = list(evidence_statuses)
        self.calls = 0
        self.requests: list[AgentRequest] = []

    async def run_with_generation(
        self, _agent_id: str, request: AgentRequest
    ) -> SimpleNamespace:
        self.calls += 1
        self.requests.append(request)
        evidence_status = self.evidence_statuses.pop(0)
        result = AgentResult(
            agent_id=KnowledgeQARuntimeService.agent_id,
            provider="local_test",
            answer="基于本地证据的回答" if evidence_status == "sufficient" else "",
            structured_result={"mode": "retrieval_only"},
            citations=["kb://CT/chapter.md"]
            if evidence_status == "sufficient"
            else [],
            evidence_status=evidence_status,
        )
        return SimpleNamespace(
            result=result,
            context=SimpleNamespace(
                evidence_status=evidence_status,
                evidence=["S1"] if evidence_status == "sufficient" else [],
            ),
        )


def _request(task_id: str, *, replan: bool) -> AgentRequest:
    return AgentRequest(
        task_id=task_id,
        session_id=f"{task_id}-session",
        user_id=f"{task_id}-user",
        course_id="CT",
        canonical_input={"text": "原始问题"},
        options={
            "knowledge_qa_runtime": {
                "execute": True,
                "replan_on_verification_failure": replan,
            }
        },
    )


async def _open_database(
    tmp_path: Any,
) -> tuple[Any, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'knowledge-runtime-recovery.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _create_persisted_run(
    session_factory: async_sessionmaker[AsyncSession],
    request: AgentRequest,
    service: KnowledgeQARuntimeService,
) -> str:
    async with session_factory() as db:
        db.add(
            SessionModel(
                id=request.session_id,
                user_id=request.user_id,
                course_id=request.course_id,
            )
        )
        db.add(
            TaskModel(
                id=request.task_id,
                session_id=request.session_id,
                user_id=request.user_id,
                course_id=request.course_id,
                intent="general_qa",
                agent_id=service.agent_id,
                status=TaskStatus.RUNNING,
                input_content=request.model_dump(mode="json"),
            )
        )
        lifecycle = RuntimeRunLifecycleService(enabled=True)
        run = await lifecycle.start(
            db,
            task_id=request.task_id,
            agent_id=service.agent_id,
            provider="local_test",
            goal=service.build_plan(request).goal,
            runtime_plan=service.build_plan(request),
            request_snapshot=request.model_dump(mode="json"),
        )
        assert run is not None
        await db.commit()
        return run.run_id


def _checkpoint_hook(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[AgentRun], Any]:
    async def checkpoint(run: AgentRun) -> None:
        async with session_factory() as db:
            task = await TaskRepository(db).get(run.task_id, for_update=True)
            if task is not None:
                if run.status == RuntimeRunStatus.WAITING_INPUT:
                    task.status = TaskStatus.WAITING_USER
                elif run.status == RuntimeRunStatus.COMPLETED:
                    task.status = TaskStatus.COMPLETED
                elif run.status == RuntimeRunStatus.FAILED:
                    task.status = TaskStatus.FAILED
            await AgentRunRepository(db).save_checkpoint(run)
            await db.commit()

    return checkpoint


@pytest.mark.asyncio
async def test_opt_in_replan_survives_persisted_waiting_input_and_resume(
    tmp_path: Any,
) -> None:
    engine, session_factory = await _open_database(tmp_path)
    fake = SequencedKnowledgeQA("insufficient", "sufficient")
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _request("knowledge-persisted-replan", replan=True)
    run_id = await _create_persisted_run(session_factory, request, service)
    checkpoint = _checkpoint_hook(session_factory)

    try:
        async with session_factory() as db:
            run = await AgentRunRepository(db).restore(run_id)
            assert run is not None
            with pytest.raises(RuntimeRunSuspended) as suspended:
                await service.run(request, run, checkpoint_hook=checkpoint)
            assert suspended.value.status == RuntimeRunStatus.WAITING_INPUT

        async with session_factory() as db:
            runtime = await AgentRunRepository(db).get(run_id)
            task = await TaskRepository(db).get(request.task_id)
            assert runtime is not None
            assert task is not None
            assert runtime.status == RuntimeRunStatus.WAITING_INPUT.value
            assert task.status == TaskStatus.WAITING_USER
            suspended_version = runtime.state_version
            assert runtime.control_data["request"]["canonical_input"]["text"] == (
                "原始问题"
            )
            checkpoints = await AgentRunRepository(db).list_checkpoints(run_id)
            assert checkpoints[-1].status == RuntimeRunStatus.WAITING_INPUT.value
            assert checkpoints[-1].state_version == suspended_version

        settings = Settings(  # type: ignore[call-arg]
            app_env="test", _env_file=None
        )
        async with session_factory() as db:
            controls = TaskControlService(db, MockAgentProvider(), settings)
            submitted = await controls.submit_input(
                request.task_id,
                RuntimeInputSubmission(
                    data={"query": "补充更具体的检索问题"},
                    expected_state_version=suspended_version,
                ),
            )
            assert submitted.status == TaskStatus.QUEUED

        async with session_factory() as db:
            runtime = await AgentRunRepository(db).get(run_id)
            task = await TaskRepository(db).get(request.task_id)
            assert runtime is not None
            assert task is not None
            assert runtime.status == RuntimeRunStatus.WAITING_INPUT.value
            assert runtime.state_version == suspended_version
            assert runtime.control_data["user_input"] == {
                "query": "补充更具体的检索问题"
            }

        async with session_factory() as db:
            restored = await RuntimeRunLifecycleService(enabled=True).start(
                db,
                task_id=request.task_id,
                agent_id=service.agent_id,
                provider="local_test",
                goal=service.build_plan(request).goal,
                runtime_plan=service.build_plan(request),
            )
            assert restored is not None
            assert restored.run_id == run_id
            assert restored.status == RuntimeRunStatus.WAITING_INPUT
            assert restored.state_version == suspended_version
            await service.run(request, restored, checkpoint_hook=checkpoint)

        assert fake.calls == 2
        assert fake.requests[1].canonical_input["text"] == "补充更具体的检索问题"
        assert fake.requests[1].canonical_input["query"] == "补充更具体的检索问题"

        async with session_factory() as db:
            runtime = await AgentRunRepository(db).get(run_id)
            task = await TaskRepository(db).get(request.task_id)
            checkpoints = await AgentRunRepository(db).list_checkpoints(run_id)
            assert runtime is not None
            assert task is not None
            assert runtime.status == RuntimeRunStatus.COMPLETED.value
            assert runtime.iteration == 1
            assert runtime.state_version > suspended_version
            assert task.status == TaskStatus.COMPLETED
            assert any(
                checkpoint.status == RuntimeRunStatus.WAITING_INPUT.value
                for checkpoint in checkpoints
            )
            assert checkpoints[-1].status == RuntimeRunStatus.COMPLETED.value
            assert [
                checkpoint.state_version for checkpoint in checkpoints
            ] == sorted(
                checkpoint.state_version for checkpoint in checkpoints
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_submit_input_rejects_stale_state_version_without_mutating_control_data(
    tmp_path: Any,
) -> None:
    engine, session_factory = await _open_database(tmp_path)
    fake = SequencedKnowledgeQA("insufficient")
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _request("knowledge-persisted-cas", replan=True)
    run_id = await _create_persisted_run(session_factory, request, service)
    checkpoint = _checkpoint_hook(session_factory)

    try:
        async with session_factory() as db:
            run = await AgentRunRepository(db).restore(run_id)
            assert run is not None
            with pytest.raises(RuntimeRunSuspended):
                await service.run(request, run, checkpoint_hook=checkpoint)

        async with session_factory() as db:
            runtime = await AgentRunRepository(db).get(run_id)
            assert runtime is not None
            persisted_version = runtime.state_version
            stale_version = persisted_version - 1
            before_data = dict(runtime.control_data)
            controls = TaskControlService(
                db,
                MockAgentProvider(),
                Settings(  # type: ignore[call-arg]
                    app_env="test", _env_file=None
                ),
            )
            with pytest.raises(ConflictError):
                await controls.submit_input(
                    request.task_id,
                    RuntimeInputSubmission(
                        data={"query": "不应写入"},
                        expected_state_version=stale_version,
                    ),
                )
            await db.rollback()

        async with session_factory() as db:
            runtime = await AgentRunRepository(db).get(run_id)
            assert runtime is not None
            assert runtime.state_version == persisted_version
            assert runtime.control_data == before_data
            assert "user_input" not in runtime.control_data
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_default_knowledge_qa_path_remains_persisted_fail_closed(
    tmp_path: Any,
) -> None:
    engine, session_factory = await _open_database(tmp_path)
    fake = SequencedKnowledgeQA("insufficient")
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _request("knowledge-persisted-default", replan=False)
    run_id = await _create_persisted_run(session_factory, request, service)
    checkpoint = _checkpoint_hook(session_factory)

    try:
        async with session_factory() as db:
            run = await AgentRunRepository(db).restore(run_id)
            assert run is not None
            result = await service.run(request, run, checkpoint_hook=checkpoint)
            assert result.status.value == "completed"
            assert run.status == RuntimeRunStatus.FAILED
            assert run.iteration == 0
            assert run.last_decision is not None
            assert run.last_decision.reason_codes == [
                "knowledge_verification_failed"
            ]

        async with session_factory() as db:
            runtime = await AgentRunRepository(db).get(run_id)
            task = await TaskRepository(db).get(request.task_id)
            checkpoints = await AgentRunRepository(db).list_checkpoints(run_id)
            assert runtime is not None
            assert task is not None
            assert runtime.status == RuntimeRunStatus.FAILED.value
            assert task.status == TaskStatus.FAILED
            assert runtime.iteration == 0
            assert checkpoints[-1].status == RuntimeRunStatus.FAILED.value
    finally:
        await engine.dispose()
