from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.providers.vision import VisionProvider


class ImageItemResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_file: str
    page_number: int | None = None
    image_index: int = Field(ge=1)
    recognized_text: str = ""
    diagram_description: str = ""
    confidence: float = Field(default=0, ge=0, le=1)
    conflicts: list[str] = Field(default_factory=list)
    uncertain_info: list[str] = Field(default_factory=list)
    status: str = "success"


class ImageBatchProcessor:
    def __init__(
        self,
        provider: VisionProvider,
        *,
        max_concurrency: int = 2,
        max_images: int = 8,
    ) -> None:
        self.provider = provider
        self.max_concurrency = max_concurrency
        self.max_images = max_images

    async def process(
        self, images: list[Path], *, prompt: str
    ) -> list[ImageItemResult]:
        if len(images) > self.max_images:
            raise ValueError(f"图片数量超过限制: {len(images)}>{self.max_images}")
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def one(index: int, image: Path) -> ImageItemResult:
            async with semaphore:
                try:
                    result = await self.provider.analyze_image(image, prompt=prompt)
                except Exception as exc:
                    return ImageItemResult(
                        source_file=image.name,
                        image_index=index,
                        status="failed",
                        uncertain_info=[f"{type(exc).__name__}: 图像未完成识别"],
                    )
                return ImageItemResult(
                    source_file=image.name,
                    image_index=index,
                    recognized_text=result.recognized_text,
                    diagram_description=result.diagram_description,
                    confidence=result.confidence,
                    conflicts=result.conflicts,
                    uncertain_info=result.uncertain_info,
                )

        # Each call receives exactly one image; order is restored by gather.
        return await asyncio.gather(
            *(one(index, image) for index, image in enumerate(images, start=1))
        )
