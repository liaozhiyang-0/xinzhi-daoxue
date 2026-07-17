from app.core.config import Settings
from app.providers.factory import get_agent_provider


def test_unpublished_xingchen_falls_back_to_mock() -> None:
    provider = get_agent_provider(
        Settings(
            app_env="test",
            default_agent_provider="xingchen",
            allow_mock_fallback=True,
        )
    )
    assert provider.provider_name == "mock"


def test_enabled_complete_xingchen_uses_real_provider() -> None:
    provider = get_agent_provider(
        Settings(
            app_env="test",
            xingchen_enabled=True,
            xingchen_api_key="test-key",
            xingchen_api_secret="test-secret",
            xingchen_solver_ct_flow_id="test-flow",
        )
    )
    assert provider.provider_name == "xingchen"
