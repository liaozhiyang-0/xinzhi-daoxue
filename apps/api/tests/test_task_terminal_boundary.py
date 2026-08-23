from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import app.services.task_completion as task_completion_module
import app.services.task_failure_service as task_failure_service_module
import app.services.task_result_commit as task_result_commit_module
import pytest
from app.agents import AgentDefinition
from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentResultStatus,
    AgentValidationResult,
)
from app.models import TaskModel, TaskStatus
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeNode,
    RuntimeRunStatus,
)
from app.services.runtime_execution_boundary import RuntimeExecutionBoundary
from app.services.task_completion import TaskCompletionService
from app.services.task_failure_service import TaskFailureService
from app.services.task_result_commit import (
    TaskResultCommitService,
    TaskTerminalCommitError,
)
from app.services.task_result_presentation import TaskResultPresentationService
from app.services.task_session_commit import TaskSessionCommitService
from sqlalchemy.ext.asyncio import AsyncSession


def make_result(
    status: AgentResultStatus = AgentResultStatus.COMPLETED,
) -> AgentResult:
    return AgentResult(
        status=status,
        agent_id="agent.test",
        provider="mock",
        answer="answer",
    )


def make_run(status: RuntimeRunStatus) -> AgentRun:
    plan = AgentRunPlan(
        plan_id="plan.test",
        goal="complete the task",
        nodes=[
            RuntimeNode(
                node_id="answer",
                node_type="agent",
                handler_id="handler.test",
            )
        ],
    )
    return AgentRun(
        run_id="run.test",
        task_id="task.test",
        goal=plan.goal,
        status=status,
        plan=plan,
    )


def make_task() -> TaskModel:
    return TaskModel(
        id="task.test",
        session_id="session.test",
        user_id="user.test",
        course_id="CT",
        intent="solve_problem",
        status=TaskStatus.RUNNING,
        provider="mock",
        agent_id="agent.test",
        input_content={},
    )


def make_agent_definition() -> AgentDefinition:
    return cast(
        AgentDefinition,
        type("Definition", (), {"scene": "solving", "mode": "local"})(),
    )


def make_completion_service() -> (
    tuple[TaskCompletionService, Mock, AsyncMock, AsyncMock]
):
    presentation = Mock(spec=TaskResultPresentationService)
    session_commit = Mock(spec=TaskSessionCommitService)
    result_commit = Mock(spec=TaskResultCommitService)
    presentation.apply.side_effect = lambda **kwargs: kwargs["result"]
    session_commit.commit = AsyncMock(return_value={})
    result_commit.commit = AsyncMock()
    service = TaskCompletionService(
        cast(Any, Mock()),
        presentation,
        session_commit,
        result_commit,
        cast(Any, Mock()),
        cast(Any, Mock()),
    )
    return service, presentation, session_commit.commit, result_commit.commit


def boundary_kwargs(
    *, result: AgentResult, runtime_run: AgentRun | None
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "db": cast(AsyncSession, Mock()),
        "task": make_task(),
        "agent_id": "agent.test",
        "agent_definition": make_agent_definition(),
        "request": AgentRequest(session_id="session.test", user_id="user.test"),
        "routing": {},
        "result": result,
        "runtime_run": runtime_run,
        "conversation_bundle": None,
        "workflow_bundle": None,
        "timings": {},
        "validation": cast(AgentValidationResult, object()),
        "started_at": now,
        "completed_at": now,
        "total_latency_ms": 1,
    }


@pytest.mark.asyncio
async def test_successful_runtime_preserves_terminal_success_contract() -> None:
    service, presentation, session_commit, result_commit = make_completion_service()
    kwargs = boundary_kwargs(
        result=make_result(), runtime_run=make_run(RuntimeRunStatus.COMPLETED)
    )
    task = kwargs["task"]
    task.execution_owner = "worker.test"
    task.lease_expires_at = datetime.now(UTC)

    result = await service._commit_terminal(**kwargs)

    assert result.status == AgentResultStatus.COMPLETED
    assert task.status == TaskStatus.COMPLETED
    assert task.execution_owner is None
    assert task.lease_expires_at is None
    assert task.heartbeat_at is not None
    presentation.apply.assert_called_once()
    session_commit.assert_awaited_once()
    result_commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "runtime_status", [RuntimeRunStatus.FAILED, RuntimeRunStatus.CANCELLED]
)
async def test_failed_runtime_is_rejected_before_task_mutation(
    runtime_status: RuntimeRunStatus,
) -> None:
    service, presentation, session_commit, result_commit = make_completion_service()
    kwargs = boundary_kwargs(result=make_result(), runtime_run=make_run(runtime_status))
    task = kwargs["task"]

    with pytest.raises(TaskTerminalCommitError) as exc_info:
        await service._commit_terminal(**kwargs)

    assert exc_info.value.details == {"runtime_status": runtime_status.value}
    assert task.status == TaskStatus.RUNNING
    presentation.apply.assert_not_called()
    session_commit.assert_not_awaited()
    result_commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_agent_result_is_rejected_before_terminal_writes() -> None:
    service, presentation, session_commit, result_commit = make_completion_service()
    kwargs = boundary_kwargs(
        result=make_result(AgentResultStatus.FAILED),
        runtime_run=make_run(RuntimeRunStatus.COMPLETED),
    )
    task = kwargs["task"]

    with pytest.raises(TaskTerminalCommitError) as exc_info:
        await service._commit_terminal(**kwargs)

    assert exc_info.value.details == {"result_status": "failed"}
    assert task.status == TaskStatus.RUNNING
    presentation.apply.assert_not_called()
    session_commit.assert_not_awaited()
    result_commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_completed_result_is_rejected_before_terminal_writes() -> None:
    service, presentation, session_commit, result_commit = make_completion_service()
    kwargs = boundary_kwargs(
        result=AgentResult(
            status=AgentResultStatus.COMPLETED,
            agent_id="agent.test",
            provider="mock",
            answer="   ",
        ),
        runtime_run=make_run(RuntimeRunStatus.COMPLETED),
    )
    task = kwargs["task"]

    with pytest.raises(TaskTerminalCommitError) as exc_info:
        await service._commit_terminal(**kwargs)

    assert exc_info.value.details == {
        "result_status": "completed",
        "reason": "empty_answer",
    }
    assert task.status == TaskStatus.RUNNING
    presentation.apply.assert_not_called()
    session_commit.assert_not_awaited()
    result_commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_result_commit_appends_completion_event_only_for_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    db = cast(AsyncSession, Mock())
    runtime_boundary = Mock(spec=RuntimeExecutionBoundary)
    runtime_boundary.finalize = AsyncMock()
    service = TaskResultCommitService(runtime_boundary)
    task = make_task()

    async def record_event(*args: Any, **kwargs: Any) -> None:
        event_type = args[2]
        events.append(str(getattr(event_type, "value", event_type)))

    monkeypatch.setattr(task_result_commit_module, "append_task_event", record_event)
    await service.commit(
        db,
        task=task,
        agent_id="agent.test",
        agent_definition=make_agent_definition(),
        request=AgentRequest(session_id="session.test", user_id="user.test"),
        routing={},
        result=make_result(),
        runtime_run=make_run(RuntimeRunStatus.COMPLETED),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        total_latency_ms=1,
        context_usage={},
    )

    assert events[-1] == "task.completed"
    runtime_boundary.finalize.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result_status", "runtime_status"),
    [
        (AgentResultStatus.COMPLETED, RuntimeRunStatus.FAILED),
        (AgentResultStatus.COMPLETED, RuntimeRunStatus.CANCELLED),
        (AgentResultStatus.FAILED, RuntimeRunStatus.COMPLETED),
    ],
)
async def test_result_commit_rejects_non_success_before_any_write(
    result_status: AgentResultStatus,
    runtime_status: RuntimeRunStatus,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_mock = Mock()
    db = cast(AsyncSession, db_mock)
    runtime_boundary = Mock(spec=RuntimeExecutionBoundary)
    runtime_boundary.finalize = AsyncMock()
    service = TaskResultCommitService(runtime_boundary)
    task = make_task()
    events: list[str] = []

    async def record_event(*args: Any, **kwargs: Any) -> None:
        events.append(str(args[2]))

    monkeypatch.setattr(task_result_commit_module, "append_task_event", record_event)
    with pytest.raises(TaskTerminalCommitError):
        await service.commit(
            db,
            task=task,
            agent_id="agent.test",
            agent_definition=make_agent_definition(),
            request=AgentRequest(session_id="session.test", user_id="user.test"),
            routing={},
            result=make_result(result_status),
            runtime_run=make_run(runtime_status),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            total_latency_ms=1,
            context_usage={},
        )

    assert task.result_content is None
    assert events == []
    runtime_boundary.finalize.assert_not_awaited()
    db_mock.add.assert_not_called()


@pytest.mark.asyncio
async def test_failure_service_is_idempotent_after_task_is_already_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = make_task()
    task.status = TaskStatus.FAILED
    repository = Mock()
    repository.get = AsyncMock(return_value=task)

    class SessionContext:
        async def __aenter__(self) -> Mock:
            return Mock()

        async def __aexit__(self, *_args: object) -> None:
            return None

    session_factory = Mock(return_value=SessionContext())
    monkeypatch.setattr(
        task_failure_service_module,
        "TaskRepository",
        Mock(return_value=repository),
    )
    service = TaskFailureService(
        session_factory,
        cast(Any, Mock()),
        cast(Any, Mock()),
        provider_name="mock",
    )

    await service.fail("task.test", "duplicate failure", "provider_error")

    repository.get.assert_awaited_once_with("task.test", for_update=True)


@pytest.mark.asyncio
async def test_failure_service_cancel_clears_worker_lease_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = make_task()
    task.execution_owner = "worker.test"
    task.lease_expires_at = datetime.now(UTC)
    task.heartbeat_at = None
    repository = Mock()
    repository.get = AsyncMock(return_value=task)
    db = Mock()
    db.commit = AsyncMock()
    runtime_boundary = Mock()
    runtime_boundary.finalize = AsyncMock(return_value=object())
    message_service = Mock()
    message_service.append_terminal_failure = AsyncMock(return_value=None)

    monkeypatch.setattr(
        task_failure_service_module,
        "TaskRepository",
        Mock(return_value=repository),
    )
    monkeypatch.setattr(
        task_failure_service_module,
        "append_task_event",
        AsyncMock(),
    )
    monkeypatch.setattr(
        task_failure_service_module,
        "ConversationMessageService",
        Mock(return_value=message_service),
    )
    service = TaskFailureService(
        Mock(),
        cast(Any, Mock()),
        runtime_boundary,
        provider_name="mock",
    )
    service.cleanup_evaluation_attachments = AsyncMock()

    await service.mark_cancelled(db, task.id, "provider cancelled")

    assert task.status == TaskStatus.CANCELLED
    assert task.execution_owner is None
    assert task.lease_expires_at is None
    assert task.heartbeat_at is not None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_failure_service_fail_clears_worker_lease_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = make_task()
    task.execution_owner = "worker.test"
    task.lease_expires_at = datetime.now(UTC)
    repository = Mock()
    repository.get = AsyncMock(return_value=task)
    db = Mock()
    db.commit = AsyncMock()
    runtime_boundary = Mock()
    runtime_boundary.finalize = AsyncMock(return_value=object())
    message_service = Mock()
    message_service.append_terminal_failure = AsyncMock(return_value=None)

    class SessionContext:
        async def __aenter__(self) -> Mock:
            return db

        async def __aexit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        task_failure_service_module,
        "TaskRepository",
        Mock(return_value=repository),
    )
    monkeypatch.setattr(
        task_failure_service_module,
        "append_task_event",
        AsyncMock(),
    )
    monkeypatch.setattr(
        task_failure_service_module,
        "ConversationMessageService",
        Mock(return_value=message_service),
    )
    service = TaskFailureService(
        Mock(return_value=SessionContext()),
        cast(Any, Mock()),
        runtime_boundary,
        provider_name="mock",
    )
    service.cleanup_evaluation_attachments = AsyncMock()

    await service.fail(task.id, "provider failed", "provider_error")

    assert task.status == TaskStatus.FAILED
    assert task.execution_owner is None
    assert task.lease_expires_at is None
    assert task.heartbeat_at is not None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "terminal_status",
    [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED],
)
async def test_mark_cancelled_does_not_overwrite_terminal_task(
    terminal_status: TaskStatus,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = make_task()
    task.status = terminal_status
    repository = Mock()
    repository.get = AsyncMock(return_value=task)
    db = cast(AsyncSession, Mock())

    monkeypatch.setattr(
        task_failure_service_module,
        "TaskRepository",
        Mock(return_value=repository),
    )
    runtime_boundary = Mock()
    runtime_boundary.finalize = AsyncMock()
    service = TaskFailureService(
        Mock(),
        cast(Any, Mock()),
        runtime_boundary,
        provider_name="mock",
    )

    await service.mark_cancelled(db, task.id, "late cancellation")

    assert task.status == terminal_status
    runtime_boundary.finalize.assert_not_awaited()
    db.commit.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "terminal_status",
    [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED],
)
async def test_completion_service_does_not_overwrite_terminal_task(
    terminal_status: TaskStatus,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, presentation, session_commit, result_commit = make_completion_service()
    session_factory = Mock()
    db = Mock()

    class SessionContext:
        async def __aenter__(self) -> Mock:
            return db

        async def __aexit__(self, *_args: object) -> None:
            return None

    session_factory.return_value = SessionContext()
    service.session_factory = session_factory

    task = make_task()
    task.status = terminal_status
    repository = Mock()
    repository.get = AsyncMock(return_value=task)

    # Keep the guard test independent from SQLAlchemy while exercising the
    # same locked-repository boundary used in production.
    monkeypatch.setattr(
        task_completion_module,
        "TaskRepository",
        Mock(return_value=repository),
    )
    await service.commit(
        task.id,
        cast(Any, Mock()),
        cast(Any, Mock()),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )

    presentation.apply.assert_not_called()
    session_commit.assert_not_awaited()
    result_commit.assert_not_awaited()
