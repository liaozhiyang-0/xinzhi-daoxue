from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from app.contracts import ImageInput
from app.core.config import Settings
from app.core.errors import ImageProcessingError


@dataclass(frozen=True)
class SourceImage:
    filename: str
    mime_type: str
    data: bytes


@dataclass(frozen=True)
class PreparedImageBatch:
    strategy: Literal["single", "ordered_multi_image", "stitched", "per_image"]
    images: tuple[ImageInput, ...]
    source_count: int
    fallback_reason: str = ""
    composite_width: int | None = None
    composite_height: int | None = None


class MultiImageComposer:
    """Normalize images and stitch simple batches without losing source order."""

    def __init__(self, settings: Settings) -> None:
        self.max_stitch_images = settings.multi_image_stitch_max_images
        self.max_total_pixels = settings.multi_image_stitch_max_total_pixels
        self.max_canvas_edge = settings.multi_image_stitch_max_canvas_edge
        self.max_aspect_ratio = settings.multi_image_stitch_max_aspect_ratio
        self.preserve_originals = settings.multi_image_preserve_originals
        self.max_output_bytes = settings.upload_max_image_size_mb * 1024 * 1024
        self.max_single_edge = settings.image_max_long_edge
        self.auto_rotate = settings.image_auto_rotate

    def prepare(self, sources: list[SourceImage]) -> PreparedImageBatch:
        if not sources:
            raise ImageProcessingError("没有可处理的图片")
        opened = [self._open(item) for item in sources]
        normalized = [self._normalize(image) for image in opened]
        individual = tuple(
            self._image_input(image, source.filename, source.mime_type)
            for image, source in zip(normalized, sources, strict=True)
        )
        if len(sources) == 1:
            return PreparedImageBatch(
                strategy="single",
                images=individual,
                source_count=1,
            )

        if self.preserve_originals:
            return PreparedImageBatch(
                strategy="ordered_multi_image",
                images=individual,
                source_count=len(sources),
            )

        fallback_reason = self._fallback_reason(normalized)
        if fallback_reason:
            return PreparedImageBatch(
                strategy="per_image",
                images=individual,
                source_count=len(sources),
                fallback_reason=fallback_reason,
            )

        composite = self._stitch(normalized)
        try:
            encoded = self._image_input(
                composite,
                "xzd-multi-image-composite.jpg",
                "image/jpeg",
            )
        except ImageProcessingError:
            return PreparedImageBatch(
                strategy="per_image",
                images=individual,
                source_count=len(sources),
                fallback_reason="composite_output_exceeds_limit",
            )
        return PreparedImageBatch(
            strategy="stitched",
            images=(encoded,),
            source_count=len(sources),
            composite_width=composite.width,
            composite_height=composite.height,
        )

    def _open(self, source: SourceImage) -> Image.Image:
        try:
            with Image.open(BytesIO(source.data)) as opened:
                opened.load()
                image = opened.copy()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ImageProcessingError(
                f"图片无法解析或像素尺寸不安全: {source.filename}"
            ) from exc
        return ImageOps.exif_transpose(image) if self.auto_rotate else image

    def _normalize(self, image: Image.Image) -> Image.Image:
        if image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        ):
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
        if max(image.size) > self.max_single_edge:
            image.thumbnail(
                (self.max_single_edge, self.max_single_edge),
                Image.Resampling.LANCZOS,
            )
        return image

    def _fallback_reason(self, images: list[Image.Image]) -> str:
        if len(images) > self.max_stitch_images:
            return "image_count_exceeds_stitch_limit"
        total_pixels = sum(image.width * image.height for image in images)
        if total_pixels > self.max_total_pixels:
            return "total_pixels_exceed_stitch_limit"
        if any(
            max(image.width / image.height, image.height / image.width)
            > self.max_aspect_ratio
            for image in images
        ):
            return "extreme_aspect_ratio"
        return ""

    def _stitch(self, images: list[Image.Image]) -> Image.Image:
        count = len(images)
        columns = 2 if count > 1 else 1
        rows = math.ceil(count / columns)
        margin = 24
        label_height = 38
        cell_width_limit = max(
            64,
            (self.max_canvas_edge - margin * (columns + 1)) // columns,
        )
        cell_height_limit = max(
            64,
            (
                self.max_canvas_edge
                - margin * (rows + 1)
                - label_height * rows
            )
            // rows,
        )
        thumbnails: list[Image.Image] = []
        for image in images:
            item = image.copy()
            item.thumbnail(
                (cell_width_limit, cell_height_limit),
                Image.Resampling.LANCZOS,
            )
            thumbnails.append(item)
        cell_width = max(item.width for item in thumbnails)
        cell_height = max(item.height for item in thumbnails)
        width = margin * (columns + 1) + cell_width * columns
        height = margin * (rows + 1) + (cell_height + label_height) * rows
        canvas = Image.new("RGB", (width, height), "#f4f6f8")
        draw = ImageDraw.Draw(canvas)
        for index, item in enumerate(thumbnails):
            row, column = divmod(index, columns)
            cell_x = margin + column * (cell_width + margin)
            cell_y = margin + row * (cell_height + label_height + margin)
            draw.rounded_rectangle(
                (
                    cell_x,
                    cell_y,
                    cell_x + cell_width,
                    cell_y + cell_height + label_height,
                ),
                radius=10,
                fill="white",
                outline="#aebdca",
                width=2,
            )
            draw.text(
                (cell_x + 12, cell_y + 11),
                f"Image {index + 1}",
                fill="#1d2a35",
            )
            image_x = cell_x + (cell_width - item.width) // 2
            image_y = cell_y + label_height + (cell_height - item.height) // 2
            canvas.paste(item, (image_x, image_y))
        return canvas

    def _image_input(
        self,
        image: Image.Image,
        filename: str,
        preferred_mime_type: str = "image/jpeg",
    ) -> ImageInput:
        mime_type = "image/jpeg"
        encoded: bytes
        if preferred_mime_type.casefold() == "image/png":
            png = self._encode_png(image)
            if len(png) <= self.max_output_bytes:
                encoded = png
                mime_type = "image/png"
            else:
                encoded = self._encode_jpeg(image)
        else:
            encoded = self._encode_jpeg(image)
        return ImageInput(
            source_type="base64",
            value=(
                f"data:{mime_type};base64,"
                f"{base64.b64encode(encoded).decode('ascii')}"
            ),
            mime_type=mime_type,
            filename=filename,
        )

    @staticmethod
    def _encode_png(image: Image.Image) -> bytes:
        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()

    def _encode_jpeg(self, image: Image.Image) -> bytes:
        for quality in (90, 82, 74, 66):
            output = BytesIO()
            image.save(output, format="JPEG", quality=quality, optimize=True)
            data = output.getvalue()
            if len(data) <= self.max_output_bytes:
                return data
        raise ImageProcessingError("拼接图片压缩后仍超过单图大小限制")
