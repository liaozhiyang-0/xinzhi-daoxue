from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"
os.environ["DEFAULT_AGENT_PROVIDER"] = "mock"
os.environ["XINGCHEN_ENABLED"] = "false"

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'dev.db'}",
        test_database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        redis_url="redis://127.0.0.1:1/0",
        minio_endpoint="127.0.0.1:1",
        default_agent_provider="mock",
        local_storage_path=tmp_path / "storage",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session_payload() -> dict[str, str]:
    return {"user_id": "user-test", "course_id": "CT", "title": "测试会话"}


@pytest.fixture
def agent_request_payload() -> dict[str, object]:
    return {
        "user_id": "user-test",
        "user_role": "student",
        "scene": "solving",
        "course_id": "CT",
        "intent": "solve_problem",
        "canonical_input": {"text": "求电阻两端电压"},
        "attachments": [],
        "context_refs": [],
        "options": {},
    }
