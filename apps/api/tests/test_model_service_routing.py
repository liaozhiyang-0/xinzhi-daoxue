from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from app.contracts import ModelResponse
from app.core.config import Settings
from app.core.errors import ModelTimeoutError
from app.observability import ModelTracer
from app.services.model_registry import ModelRegistry
from app.services.model_service import ModelService


class TimeoutProvider:
    provider_name = "dashscope"
    configured = True
    default_model = "fast-model"

    def __init__(self) -> None:
        self.calls = 0

    async def generate_text(self, **_: Any) -> ModelResponse:
        self.calls += 1
        raise ModelTimeoutError(
            "simulated timeout",
            provider=self.provider_name,
            model="fast-model",
        )


def _registry(tmp_path: Path) -> ModelRegistry:
    models = tmp_path / "models.yaml"
    routes = tmp_path / "routes.yaml"
    models.write_text(
        """
models:
  fast_model:
    provider: dashscope
    model: fast-model
    enabled_env: DASHSCOPE_ENABLED
    modalities: [text]
    timeout_seconds: 45
  fallback_model:
    provider: dashscope
    model: fallback-model
    enabled_env: DASHSCOPE_ENABLED
    modalities: [text]
    timeout_seconds: 45
""",
        encoding="utf-8",
    )
    routes.write_text(
        """
routes:
  interactive:
    primary: fast_model
    fallback: fallback_model
    max_retries: 0
    fallback_on_timeout: false
    options: {timeout: 20}
""",
        encoding="utf-8",
    )
    settings = Settings(
        app_env="test",
        dashscope_enabled=True,
        dashscope_api_key="test-key",
        _env_file=None,
    )
    return ModelRegistry(settings, models_path=models, routes_path=routes)


@pytest.mark.asyncio
async def test_interactive_route_does_not_retry_or_wait_for_fallback_on_timeout(
    tmp_path: Path,
) -> None:
    settings = Settings(
        app_env="test",
        dashscope_enabled=True,
        dashscope_api_key="test-key",
        model_max_retries=1,
        _env_file=None,
    )
    registry = _registry(tmp_path)
    provider = TimeoutProvider()
    service = ModelService(
        settings,
        registry,
        {"dashscope": provider},
        ModelTracer(),
    )

    with pytest.raises(ModelTimeoutError):
        await service.generate_for_task(
            "interactive",
            messages=[{"role": "user", "content": "test"}],
        )

    # The route-level budget overrides the global retry setting and prevents a
    # second slow provider call after a timeout.
    assert provider.calls == 1
