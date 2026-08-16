from app.agents import AgentRegistry
from app.contracts import ProviderAvailability
from app.core.config import Settings
from app.providers.base import AgentProvider
from app.providers.local import LocalAgentProvider
from app.providers.mock import MockAgentProvider


def get_agent_provider(
    settings: Settings, registry: AgentRegistry | None = None
) -> AgentProvider:
    del registry
    return (
        MockAgentProvider()
        if settings.default_agent_provider == "mock"
        else LocalAgentProvider()
    )


def get_provider_availability(
    settings: Settings, provider: AgentProvider
) -> ProviderAvailability:
    if provider.provider_name == "mock":
        return ProviderAvailability(
            provider_name="mock",
            available=True,
            reason="显式开发 Mock Provider；不代表真实业务执行结果",
            publication_status="local_only",
        )
    return ProviderAvailability(
        provider_name="local",
        available=True,
        reason="业务 Agent 通过本地 Runtime 执行",
        publication_status="local_only",
    )
