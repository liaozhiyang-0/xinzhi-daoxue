from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query, Request

from app.contracts import ProviderHealth

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models(request: Request) -> dict[str, Any]:
    registry = request.app.state.model_registry
    providers = request.app.state.model_service.providers
    models = []
    for definition in registry.models.values():
        provider = providers.get(definition.provider)
        models.append(
            {
                "alias": definition.alias,
                "provider": definition.provider,
                "model": definition.model,
                "configured": bool(provider and provider.configured),
                "enabled": registry.enabled(definition),
                "modalities": definition.modalities,
                "supports_streaming": definition.supports_streaming,
                "supports_json": definition.supports_json,
            }
        )
    return {"models": models, "registry_errors": registry.errors}


@router.get("/health")
async def model_health(
    request: Request,
    live: bool = Query(default=False, description="是否发送真实极短模型请求"),
) -> dict[str, Any]:
    providers = request.app.state.model_service.providers
    if live:
        health = await asyncio.gather(
            *(provider.health_check() for provider in providers.values())
        )
    else:
        health = [
            ProviderHealth(
                provider=name,
                configured=provider.configured,
                available=provider.configured,
                model=provider.default_model,
                error_type=None if provider.configured else "unconfigured",
                error_message=(
                    None
                    if provider.configured
                    else (
                        "IFLYTEK_SPARK_API_KEY未配置"
                        if name == "iflytek_spark"
                        else "DASHSCOPE_API_KEY未配置"
                    )
                ),
            )
            for name, provider in providers.items()
        ]
    return {
        "live": live,
        "providers": [item.model_dump(mode="json") for item in health],
        "registry_valid": not request.app.state.model_registry.errors,
        "registry_errors": request.app.state.model_registry.errors,
    }
