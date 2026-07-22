from pathlib import Path

import pytest
from app.multimodal import ImageBatchProcessor, merge_multimodal_results
from app.providers.vision import VisionProvider, VisionResult


class FakeVision(VisionProvider):
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls: list[str] = []

    @property
    def available(self) -> bool:
        return True

    async def analyze_image(self, image: Path, *, prompt: str) -> VisionResult:
        self.calls.append(image.name)
        return VisionResult(
            recognized_text=f"{prompt}:{image.stem}",
            diagram_description=image.name,
            confidence=0.8,
            provider=self.provider_name,
        )


@pytest.mark.asyncio
async def test_multi_image_calls_single_image_provider_in_order(tmp_path: Path) -> None:
    provider = FakeVision()
    images = [tmp_path / "2.png", tmp_path / "1.png"]
    for image in images:
        image.write_bytes(b"image")
    processor = ImageBatchProcessor(provider, max_concurrency=2, max_images=8)

    results = await processor.process(images, prompt="识别")
    merged = merge_multimodal_results(results)

    assert provider.calls == ["2.png", "1.png"]
    assert [item.image_index for item in results] == [1, 2]
    assert merged["failed_count"] == 0
    assert merged["confidence"] == pytest.approx(0.8)
