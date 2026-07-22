from __future__ import annotations

import os

import pytest
from app.core.config import Settings
from app.providers.llm import DashScopeQwenProvider, IflytekSparkProvider

pytestmark = [pytest.mark.integration, pytest.mark.requires_api_key]


@pytest.mark.skipif(
    os.getenv("RUN_REAL_MODEL_TESTS") != "1", reason="付费API测试默认禁用"
)
@pytest.mark.asyncio
async def test_real_spark_connectivity() -> None:
    provider = IflytekSparkProvider(Settings())
    try:
        health = await provider.health_check()
        assert health.available
    finally:
        await provider.aclose()


@pytest.mark.skipif(
    os.getenv("RUN_REAL_MODEL_TESTS") != "1", reason="付费API测试默认禁用"
)
@pytest.mark.asyncio
async def test_real_dashscope_connectivity() -> None:
    provider = DashScopeQwenProvider(Settings())
    try:
        health = await provider.health_check()
        assert health.available
    finally:
        await provider.aclose()
