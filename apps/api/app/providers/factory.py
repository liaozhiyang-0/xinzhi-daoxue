from app.core.config import Settings
from app.providers.base import AgentProvider
from app.providers.mock import MockAgentProvider
from app.providers.xingchen import XingchenCloudProvider


def get_agent_provider(settings: Settings) -> AgentProvider:
    if settings.default_agent_provider.lower() != "xingchen":
        return MockAgentProvider()

    xingchen = XingchenCloudProvider(settings)
    if not xingchen.is_configured:
        return MockAgentProvider()
    return xingchen
