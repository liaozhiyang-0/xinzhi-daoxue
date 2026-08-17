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
os.environ["RAG_ENABLED"] = "false"
# Tests must never reach the network for model weights: without this,
# a missing/partial HuggingFace cache triggers 10s connect-timeouts that
# block the app event loop and make unrelated tests flaky. Offline mode
# fails fast and deterministically.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

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
        intent: str = "solve_problem",
        user_role: str = "student",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "session_id": session_id,
            "user_id": "user-test",
            "user_role": user_role,
            "scene": "solving",
            "course_id": "CT",
            "intent": intent,
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
        intent: str = "solve_problem",
        user_role: str = "student",
    ) -> dict[str, Any]:
        response = self.client.post(
            "/api/v1/tasks",
            json=self.task_payload(
                session_id,
                task_id=task_id,
                options=options,
                attachments=attachments,
                intent=intent,
                user_role=user_role,
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
        # Typed Runtime sub-agent tests use the explicit development Mock
        # contract; production remains fail-closed because APP_ENV guards it.
        allow_agent_mocks=True,
        # Runtime integration tests are provider-free execution tests. The
        # release gate itself is covered by explicit launch-policy tests with
        # release_gate_required=True; do not inherit a developer machine's
        # production gate setting into these local fixtures.
        agent_runtime_release_gate_required=False,
        knowledge_ct_path=tmp_path / "knowledge" / "CT",
        knowledge_ae_path=tmp_path / "knowledge" / "AE",
        knowledge_de_path=tmp_path / "knowledge" / "DE",
        knowledge_ss_path=tmp_path / "knowledge" / "SS",
        knowledge_dsp_path=tmp_path / "knowledge" / "DSP",
        knowledge_comm_path=tmp_path / "knowledge" / "COMM",
        local_storage_path=tmp_path / "storage",
        research_analysis_artifact_root=tmp_path / "research-artifacts",
        research_analysis_temp_root=tmp_path / "research-temp",
        research_knowledge_enabled=False,
        # Keep API tests deterministic: live academic providers are covered by
        # provider/service tests with explicit fakes, not by TestClient flows.
        external_retrieval_enabled=False,
        sse_heartbeat_seconds=0.02,
        _env_file=None,
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
