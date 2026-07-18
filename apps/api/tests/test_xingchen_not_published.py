import pytest
from app.contracts import AgentRequest
from app.core.config import Settings
from app.core.errors import AgentConfigurationIncompleteError
from app.providers.xingchen import XingchenCloudProvider


@pytest.mark.asyncio
async def test_incomplete_xingchen_configuration_never_calls_http(monkeypatch) -> None:
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("HTTP must not be constructed")

    monkeypatch.setattr("httpx.AsyncClient", forbidden)
    provider = XingchenCloudProvider(Settings(app_env="test"))
    with pytest.raises(AgentConfigurationIncompleteError, match="配置不完整"):
        await provider.run(
            "SOLVER_CT_V1",
            AgentRequest(session_id="session", user_id="user"),
        )
    assert called is False
