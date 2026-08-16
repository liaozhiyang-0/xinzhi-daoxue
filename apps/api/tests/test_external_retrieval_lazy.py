from __future__ import annotations

from app.core.config import Settings
from app.providers.retrieval.factory import create_external_search_service


def test_external_search_factory_defers_clients_until_first_search() -> None:
    settings = Settings(
        app_env="test",
        external_retrieval_enabled=True,
        _env_file=None,
    )

    service = create_external_search_service(settings)

    assert service.providers == ()
    health = service.health()
    assert health["deferred"] is True
    assert health["configured"] is True

