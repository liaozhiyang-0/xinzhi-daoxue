from __future__ import annotations

import pytest
from app.services.task_executor import LocalTaskExecutor, QueueTaskExecutor


def test_task_creation_idempotency_reuses_same_task(api) -> None:
    session = api.create_session()
    options = {"idempotency_key": "idem-task-0001"}
    first = api.create_task(session["id"], options=options)
    second = api.create_task(session["id"], options=options)
    assert second["id"] == first["id"]
    assert second["idempotency_key"] == "idem-task-0001"


def test_local_executor_delegates_without_changing_contract() -> None:
    class Runner:
        def submit(self, task_id: str) -> bool:
            return task_id == "accepted"

    executor = LocalTaskExecutor(Runner())  # type: ignore[arg-type]
    assert executor.submit("accepted") is True
    assert executor.submit("duplicate") is False


def test_queue_executor_fails_explicitly_when_unconfigured() -> None:
    with pytest.raises(RuntimeError, match="尚未配置"):
        QueueTaskExecutor().submit("task-1")


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
