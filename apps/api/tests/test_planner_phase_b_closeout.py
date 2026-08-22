from __future__ import annotations

from app.core.config import Settings
from app.services.overall_routing import OverallRoutingService


def test_overall_router_is_disabled_by_default_but_remains_compatibility_api() -> None:
    settings = Settings(_env_file=None)

    assert settings.overall_routing_enabled is False
    assert OverallRoutingService.deprecated is True


def test_overall_router_can_be_explicitly_enabled_for_rollback() -> None:
    settings = Settings(overall_routing_enabled=True, _env_file=None)

    assert settings.overall_routing_enabled is True
