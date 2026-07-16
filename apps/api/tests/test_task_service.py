from pathlib import Path

import pytest
from app.contracts import AgentRequest
from app.contracts.api import SessionCreate
from app.core.errors import ProviderError
from app.database.base import Base
from app.providers.base import AgentProvider
from app.providers.mock import MockAgentProvider
from app.services.session_service import SessionService
from app.services.task_service import TaskService
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class FailingProvider(AgentProvider):
    async def run(self, agent_id, request, stream=True):
        raise ProviderError("expected failure")

    async def cancel(self, run_id):
        return None

    async def get_status(self, run_id):
        return {"status": "failed"}


@pytest.fixture
async def db(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'service.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_task_service_creates_artifact(db) -> None:
    session = await SessionService(db).create(
        SessionCreate(user_id="user-1", course_id="CT")
    )
    request = AgentRequest(
        session_id=session.id,
        user_id="user-1",
        canonical_input={"text": "test"},
    )

    task = await TaskService(db, MockAgentProvider()).create_and_run(request)

    assert task.status.value == "completed"
    assert task.provider == "mock"
    assert len(task.artifacts) == 1


@pytest.mark.asyncio
async def test_provider_failure_marks_task_failed(db) -> None:
    session = await SessionService(db).create(
        SessionCreate(user_id="user-1", course_id="CT")
    )
    request = AgentRequest(session_id=session.id, user_id="user-1")

    task = await TaskService(db, FailingProvider()).create_and_run(request)

    assert task.status.value == "failed"
    assert task.error_message == "expected failure"
