from app.core.config import Settings
from app.providers.factory import get_agent_provider, get_provider_availability


def test_local_runtime_is_the_default_provider() -> None:
    provider = get_agent_provider(
        Settings(app_env="test", default_agent_provider="local", _env_file=None)
    )

    assert provider.provider_name == "local"
    availability = get_provider_availability(
        Settings(app_env="test", default_agent_provider="local", _env_file=None),
        provider,
    )
    assert availability.available is True
    assert availability.publication_status == "local_only"


def test_mock_provider_is_explicit_and_local_only() -> None:
    provider = get_agent_provider(
        Settings(app_env="test", default_agent_provider="mock", _env_file=None)
    )

    assert provider.provider_name == "mock"
