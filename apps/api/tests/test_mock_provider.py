import logging

import pytest
from app.contracts import AgentRequest
from app.core.config import Settings
from app.core.errors import NotConfiguredError
from app.providers.factory import get_agent_provider
from app.providers.mock import MockAgentProvider
from app.providers.xingchen import XingchenCloudProvider


@pytest.mark.asyncio
async def test_mock_provider_returns_explicit_mock_result() -> None:
    provider = MockAgentProvider()
    request = AgentRequest(
        session_id="session-1",
        user_id="user-1",
        canonical_input={"text": "test"},
    )

    result = await provider.run("SOLVER_CT_V1", request)

    assert result.provider == "mock"
    assert result.structured_result["provider"] == "mock"
    assert result.artifacts[0].content["provider"] == "mock"


def test_unconfigured_xingchen_falls_back_to_mock() -> None:
    settings = Settings(
        default_agent_provider="xingchen",
        xingchen_enabled=False,
        xingchen_api_key="",
    )
    assert isinstance(get_agent_provider(settings), MockAgentProvider)


@pytest.mark.asyncio
async def test_api_key_is_not_logged(caplog) -> None:
    secret = "never-log-this-secret"
    settings = Settings(
        default_agent_provider="xingchen",
        xingchen_enabled=True,
        xingchen_base_url="https://example.invalid",
        xingchen_api_key=secret,
        xingchen_solver_ct_workflow_id="workflow-id",
    )
    provider = XingchenCloudProvider(settings)
    request = AgentRequest(session_id="s", user_id="u")

    with caplog.at_level(logging.DEBUG), pytest.raises(NotConfiguredError):
        await provider.run("SOLVER_CT_V1", request)

    assert secret not in caplog.text
