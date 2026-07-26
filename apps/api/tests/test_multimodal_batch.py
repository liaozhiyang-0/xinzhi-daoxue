import base64
from io import BytesIO
from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.errors import ImageProcessingError
from app.multimodal import (
    ImageBatchProcessor,
    MultiImageComposer,
    SourceImage,
    merge_multimodal_results,
)
from app.providers.vision import VisionProvider, VisionResult
from PIL import Image


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


def image_bytes(size: tuple[int, int], color: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


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


def test_simple_multi_image_batch_is_stitched_into_one_model_image() -> None:
    composer = MultiImageComposer(
        Settings(
            app_env="test",
            upload_max_image_size_mb=2,
            image_max_long_edge=1024,
            multi_image_stitch_max_canvas_edge=1024,
            _env_file=None,
        )
    )

    prepared = composer.prepare(
        [
            SourceImage("one.png", "image/png", image_bytes((320, 200), "white")),
            SourceImage("two.png", "image/png", image_bytes((240, 300), "gray")),
        ]
    )

    assert prepared.strategy == "stitched"
    assert prepared.source_count == 2
    assert len(prepared.images) == 1
    assert prepared.composite_width is not None
    assert prepared.composite_height is not None
    encoded = prepared.images[0].value.split(",", 1)[1]
    with Image.open(BytesIO(base64.b64decode(encoded))) as composite:
        assert composite.width <= 1024
        assert composite.height <= 1024


def test_complex_multi_image_batch_falls_back_to_ordered_individual_images() -> None:
    composer = MultiImageComposer(
        Settings(
            app_env="test",
            multi_image_stitch_max_images=2,
            _env_file=None,
        )
    )
    sources = [
        SourceImage(
            f"{index}.png",
            "image/png",
            image_bytes((120, 80), color),
        )
        for index, color in enumerate(("red", "green", "blue"), start=1)
    ]

    prepared = composer.prepare(sources)

    assert prepared.strategy == "per_image"
    assert prepared.fallback_reason == "image_count_exceeds_stitch_limit"
    assert [item.filename for item in prepared.images] == [
        "1.png",
        "2.png",
        "3.png",
    ]


def test_composite_encoding_failure_falls_back_to_individual_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composer = MultiImageComposer(Settings(app_env="test", _env_file=None))
    original_image_input = composer._image_input

    def image_input_or_fail(image: Image.Image, filename: str):
        if filename == "xzd-multi-image-composite.jpg":
            raise ImageProcessingError("composite too large")
        return original_image_input(image, filename)

    monkeypatch.setattr(composer, "_image_input", image_input_or_fail)
    prepared = composer.prepare(
        [
            SourceImage("one.png", "image/png", image_bytes((120, 80), "white")),
            SourceImage("two.png", "image/png", image_bytes((120, 80), "gray")),
        ]
    )

    assert prepared.strategy == "per_image"
    assert prepared.fallback_reason == "composite_output_exceeds_limit"
    assert [item.filename for item in prepared.images] == ["one.png", "two.png"]
