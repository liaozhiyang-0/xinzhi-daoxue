from app.contracts import ProviderAvailability
from app.core.config import Settings
from app.providers.base import AgentProvider
from app.providers.mock import MockAgentProvider
from app.providers.xingchen import XingchenCloudProvider


def get_agent_provider(settings: Settings) -> AgentProvider:
    if settings.default_agent_provider == "mock":
        return MockAgentProvider()
    if settings.allow_mock_fallback:
        return MockAgentProvider()
    return XingchenCloudProvider(settings)


def get_provider_availability(
    settings: Settings, provider: AgentProvider
) -> ProviderAvailability:
    if provider.provider_name == "mock":
        reason = (
            "SOLVER_CT 外部 API 尚未发布，当前仅提供本地 Mock 闭环"
            if settings.default_agent_provider == "xingchen"
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
        available=False,
        reason="SOLVER_CT 外部 API 尚未发布",
        publication_status=settings.xingchen_publication_status,
    )
