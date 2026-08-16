import pytest
from app.contracts import AgentRequest
from app.providers.mock import MockAgentProvider


@pytest.mark.asyncio
async def test_mock_provider_is_explicit() -> None:
    result = await MockAgentProvider().run(
        "SOLVER_CT_V1",
        AgentRequest(session_id="session-1", user_id="user-1"),
    )
    assert result.provider == "mock"
    assert result.structured_result["mock"] is True
    assert "mock_result" in result.warnings
    assert "不是远程模型真实输出" in result.answer
