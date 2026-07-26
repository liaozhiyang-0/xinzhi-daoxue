from app.agents import AgentRegistry
from app.contracts import ProviderAvailability
from app.core.config import Settings
from app.providers.base import AgentProvider
from app.providers.mock import MockAgentProvider
from app.providers.xingchen import XingchenCloudProvider


def get_agent_provider(
    settings: Settings, registry: AgentRegistry | None = None
) -> AgentProvider:
    if not settings.xingchen_enabled:
        return MockAgentProvider()
    return XingchenCloudProvider(settings, registry=registry)


def get_provider_availability(
    settings: Settings, provider: AgentProvider
) -> ProviderAvailability:
    if provider.provider_name == "mock":
        reason = (
            "XINGCHEN_ENABLED=false，SOLVER_CT 当前使用本地 Mock"
            if not settings.xingchen_enabled
            else None
        )
        return ProviderAvailability(
            provider_name="mock",
            available=True,
            reason=reason,
            publication_status="local_only",
        )
    available = (
        any(
            provider.registry.is_runtime_available(agent.agent_id, settings)
            for agent in provider.registry.list_agents()
            if agent.provider == "xingchen"
        )
        if isinstance(provider, XingchenCloudProvider)
        else settings.xingchen_runtime_available
    )
    return ProviderAvailability(
        provider_name="xingchen",
        available=available,
        reason=None if available else "没有已配置且已发布的星辰 Agent",
        publication_status=settings.xingchen_publication_status,
    )
