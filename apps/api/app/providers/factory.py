from app.contracts import ProviderAvailability
from app.core.config import Settings
from app.core.errors import XingchenConfigurationError
from app.providers.base import AgentProvider
from app.providers.mock import MockAgentProvider
from app.providers.xingchen import XingchenCloudProvider


def get_agent_provider(settings: Settings) -> AgentProvider:
    if not settings.xingchen_enabled:
        return MockAgentProvider()
    if not settings.xingchen_runtime_available:
        raise XingchenConfigurationError(
            "XINGCHEN_ENABLED=true，但 Key、Secret 或 Flow ID 配置不完整"
        )
    return XingchenCloudProvider(settings)


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
    return ProviderAvailability(
        provider_name="xingchen",
        available=True,
        reason=None,
        publication_status=settings.xingchen_publication_status,
    )
