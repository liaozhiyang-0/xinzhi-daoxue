from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import monotonic, sleep

import pytest
from app.main import create_app
from app.models import TaskStatus
from app.repositories import TaskRepository
from app.services.task_executor import LocalTaskExecutor, QueueTaskExecutor
from app.services.task_queue import InMemoryTaskQueue
from fastapi.testclient import TestClient


def test_task_creation_idempotency_reuses_same_task(api) -> None:
    session = api.create_session()
    options = {"idempotency_key": "idem-task-0001"}
    first = api.create_task(session["id"], options=options)
    second = api.create_task(session["id"], options=options)
    assert second["id"] == first["id"]
    assert second["idempotency_key"] == "idem-task-0001"


@pytest.mark.asyncio
async def test_local_executor_delegates_without_changing_contract() -> None:
    class Runner:
        def submit(self, task_id: str) -> bool:
            return task_id == "accepted"

    executor = LocalTaskExecutor(Runner())  # type: ignore[arg-type]
    assert await executor.submit("accepted") is True
    assert await executor.submit("duplicate") is False


@pytest.mark.asyncio
async def test_queue_executor_publishes_without_local_fallback() -> None:
    queue = InMemoryTaskQueue()
    executor = QueueTaskExecutor(queue)

    assert await executor.submit("task-1") is True
    assert queue.published == ["task-1"]
    assert await queue.receive(timeout_seconds=1) == "task-1"
    await executor.shutdown()
    assert queue.closed is True


def test_retry_respects_max_attempts(api) -> None:
    session = api.create_session()
    task = api.wait_for_task(
        api.create_task(
            session["id"],
            options={
                "debug_agent_id": "SOLVER_CT_V1",
                "mock_force_failure": True,
                "max_attempts": 1,
            },
            user_role="admin",
        )["id"]
    )
    assert task["status"] == "failed"
    response = api.client.post(f"/api/v1/tasks/{task['id']}/retry")
    assert response.status_code == 409


def test_debug_metrics_are_aggregated_without_raw_prompt(api) -> None:
    session = api.create_session()
    api.wait_for_task(api.create_task(session["id"])["id"])
    response = api.client.get("/api/v1/debug/execution/metrics/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 1
    assert payload["slowest_runs"]
    assert "raw_prompt" not in response.text


@pytest.mark.asyncio
async def test_recovery_claims_expired_task_once(client, api, monkeypatch) -> None:
    submitted: list[str] = []
    monkeypatch.setattr(
        client.app.state.task_runner,
        "submit",
        lambda task_id: submitted.append(task_id) or True,
    )
    session = api.create_session()
    task = api.create_task(session["id"])

    async with client.app.state.session_factory() as db:
        model = await TaskRepository(db).get(task["id"])
        assert model is not None
        model.status = TaskStatus.RUNNING
        model.execution_owner = "dead-worker"
        model.heartbeat_at = datetime.now(UTC) - timedelta(minutes=5)
        model.lease_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await db.commit()

    submitted.clear()
    recovered = await client.app.state.task_runner.recover_pending_tasks()
    assert recovered == 1
    assert submitted == [task["id"]]

    async with client.app.state.session_factory() as db:
        model = await TaskRepository(db).get(task["id"])
        assert model is not None
        assert model.status == TaskStatus.QUEUED
        assert model.execution_owner == client.app.state.task_runner.execution_owner
        events = await TaskRepository(db).list_events(task["id"])
        assert events[-1].event_data["data"]["recovered"] is True

    submitted.clear()
    assert await client.app.state.task_runner.recover_pending_tasks() == 0
    assert submitted == []


def test_shutdown_requeues_task_for_next_lifespan(settings) -> None:
    app = create_app(settings)
    with TestClient(app) as first_client:
        session = first_client.post(
            "/api/v1/sessions",
            json={"user_id": "user-test", "course_id": "CT", "title": "shutdown"},
        ).json()
        task = first_client.post(
            "/api/v1/tasks",
            json={
                "session_id": session["id"],
                "user_id": "user-test",
                "user_role": "student",
                "scene": "solving",
                "course_id": "CT",
                "intent": "solve_problem",
                "canonical_input": {"text": "shutdown recovery"},
                "attachments": [],
                "context_refs": [],
                "options": {"mock_delay_seconds": 10.0},
            },
        ).json()
        deadline = monotonic() + 2.0
        while monotonic() < deadline:
            status = first_client.get(f"/api/v1/tasks/{task['id']}").json()["status"]
            if status == TaskStatus.RUNNING.value:
                break
            sleep(0.02)
        assert status == TaskStatus.RUNNING.value

    with TestClient(create_app(settings)) as second_client:
        deadline = monotonic() + 15.0
        while monotonic() < deadline:
            response = second_client.get(f"/api/v1/tasks/{task['id']}")
            assert response.status_code == 200
            recovered = response.json()
            if recovered["status"] in {
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
            }:
                break
            sleep(0.02)
        assert recovered["status"] == TaskStatus.COMPLETED.value
        events_response = second_client.get(f"/api/v1/tasks/{task['id']}/events")
        assert events_response.status_code == 200
        events = events_response.json()
        assert any(
            event["event_data"]["data"].get("reason") == "application_shutdown"
            for event in events
            if event["event_type"] == "task.queued"
        )
        assert not any(event["event_type"] == "task.failed" for event in events)
