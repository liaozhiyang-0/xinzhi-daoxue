import pytest
from app.contracts import AgentRequest
from app.core.config import Settings
from app.core.errors import NotPublishedError
from app.providers.xingchen import XingchenCloudProvider


@pytest.mark.asyncio
async def test_xingchen_provider_never_calls_http(monkeypatch) -> None:
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("HTTP must not be constructed")

    monkeypatch.setattr("httpx.AsyncClient", forbidden)
    provider = XingchenCloudProvider(Settings(app_env="test"))
    with pytest.raises(NotPublishedError, match="尚未发布外部 API"):
        await provider.run(
            "SOLVER_CT_V1",
            AgentRequest(session_id="session", user_id="user"),
        )
    assert called is False
