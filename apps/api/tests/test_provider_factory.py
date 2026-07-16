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


def test_fallback_can_be_disabled_without_enabling_network() -> None:
    provider = get_agent_provider(
        Settings(
            app_env="test",
            default_agent_provider="xingchen",
            allow_mock_fallback=False,
        )
    )
    assert provider.provider_name == "xingchen"
