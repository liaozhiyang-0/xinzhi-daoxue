from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"
os.environ["DEFAULT_AGENT_PROVIDER"] = "mock"
os.environ["ALLOW_MOCK_FALLBACK"] = "true"
os.environ["XINGCHEN_ENABLED"] = "false"

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


class ApiHelper:
    def __init__(self, client: TestClient) -> None:
        self.client = client

    def create_session(self, *, user_id: str = "user-test") -> dict[str, Any]:
        response = self.client.post(
            "/api/v1/sessions",
            json={"user_id": user_id, "course_id": "CT", "title": "测试会话"},
        )
        assert response.status_code == 201
        return response.json()

    def task_payload(
        self,
        session_id: str,
        *,
        task_id: str | None = None,
        options: dict[str, Any] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "session_id": session_id,
            "user_id": "user-test",
            "user_role": "student",
            "scene": "solving",
            "course_id": "CT",
            "intent": "solve_problem",
            "canonical_input": {"text": "求电阻两端电压"},
            "attachments": attachments or [],
            "context_refs": [],
            "options": options or {},
        }
        if task_id:
            payload["task_id"] = task_id
        return payload

    def create_task(
        self,
        session_id: str,
        *,
        task_id: str | None = None,
        options: dict[str, Any] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        response = self.client.post(
            "/api/v1/tasks",
            json=self.task_payload(
                session_id,
                task_id=task_id,
                options=options,
                attachments=attachments,
            ),
        )
        assert response.status_code == 202, response.text
        return response.json()

    def wait_for_task(
        self,
        task_id: str,
        *,
        statuses: set[str] | None = None,
        timeout: float = 5,
    ) -> dict[str, Any]:
        terminal = statuses or {"completed", "failed", "cancelled"}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = self.client.get(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 200
            task = response.json()
            if task["status"] in terminal:
                return task
            time.sleep(0.02)
        raise AssertionError(f"task did not reach {terminal}: {task_id}")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'dev.db'}",
        test_database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        redis_url="redis://127.0.0.1:1/0",
        minio_endpoint="127.0.0.1:1",
        default_agent_provider="mock",
        allow_mock_fallback=True,
        local_storage_path=tmp_path / "storage",
        sse_heartbeat_seconds=0.02,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def api(client: TestClient) -> ApiHelper:
    return ApiHelper(client)
