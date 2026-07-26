from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.config import Settings
from app.core.errors import NotConfiguredError
from app.providers.vision.base import VisionProvider, VisionResult


class IFlytekVisionProvider(VisionProvider):
    """Single-image boundary; protocol transport stays explicit until configured."""

    provider_name = "iflytek_vision"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def available(self) -> bool:
        return bool(self.settings.vision_enabled and self.settings.vision_endpoint)

    async def analyze_image(self, image: Path, *, prompt: str) -> VisionResult:
        del prompt
        if not await asyncio.to_thread(image.is_file):
            raise FileNotFoundError(image)
        if not self.available:
            raise NotConfiguredError(
                "图像理解 Provider 未配置；现有星辰单图链路仍保持可用"
            )
        raise NotConfiguredError(
            "VISION_ENDPOINT 已配置，但专用图像协议尚未完成验证；禁止猜测字段"
        )
