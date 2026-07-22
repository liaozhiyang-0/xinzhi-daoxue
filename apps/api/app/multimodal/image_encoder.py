from __future__ import annotations

import base64
import binascii
import mimetypes
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageOps, UnidentifiedImageError

from app.contracts import ImageInput
from app.core.config import Settings
from app.core.errors import ImageProcessingError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
}


class ImageEncoder:
    """Convert safe local images to data URLs without retaining EXIF metadata."""

    def __init__(self, settings: Settings) -> None:
        self.max_bytes = settings.upload_max_image_size_mb * 1024 * 1024
        self.max_long_edge = settings.image_max_long_edge
        self.auto_rotate = settings.image_auto_rotate
        self.remove_exif = settings.image_remove_exif

    def encode(self, image: ImageInput) -> str:
        if image.source_type == "url":
            return self._validate_url(image.value)
        if image.source_type == "base64":
            return self._validate_data_url(image.value, image.mime_type)
        path = Path(image.value).expanduser()
        if not path.is_file():
            raise ImageProcessingError(f"图片文件不存在: {path.name}")
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ImageProcessingError("无法读取图片文件信息") from exc
        self._check_size(size)
        mime = image.mime_type or mimetypes.guess_type(path.name)[0]
        if mime not in ALLOWED_MIME_TYPES:
            raise ImageProcessingError(f"不支持的图片类型: {mime or 'unknown'}")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ImageProcessingError("无法读取图片文件") from exc
        return self._normalize(data)

    @staticmethod
    def _validate_url(value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ImageProcessingError("图片 URL 必须使用 http 或 https")
        return value

    def _validate_data_url(self, value: str, mime_hint: str | None) -> str:
        if not value.startswith("data:image/") or ";base64," not in value:
            raise ImageProcessingError("Base64 图片必须是 data:image/...;base64,...")
        header, encoded = value.split(",", 1)
        mime = header[5:].split(";", 1)[0].lower()
        if mime_hint and mime_hint.lower() != mime:
            raise ImageProcessingError("Base64 MIME 与声明类型不一致")
        if mime not in ALLOWED_MIME_TYPES:
            raise ImageProcessingError(f"不支持的图片类型: {mime}")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ImageProcessingError("Base64 图片内容无效") from exc
        self._check_size(len(data))
        return self._normalize(data)

    def _normalize(self, data: bytes) -> str:
        try:
            with Image.open(BytesIO(data)) as opened:
                if opened.format not in ALLOWED_FORMATS:
                    raise ImageProcessingError(
                        f"不支持的图片格式: {opened.format or 'unknown'}"
                    )
                image = opened.copy()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ImageProcessingError("图片无法解析或像素尺寸不安全") from exc
        if self.auto_rotate:
            image = ImageOps.exif_transpose(image)
        if max(image.size) > self.max_long_edge:
            image.thumbnail(
                (self.max_long_edge, self.max_long_edge), Image.Resampling.LANCZOS
            )
        output = BytesIO()
        has_alpha = image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        )
        if has_alpha:
            image.save(output, format="PNG", optimize=True)
            mime = "image/png"
        else:
            if image.mode != "RGB":
                image = image.convert("RGB")
            save_options: dict[str, object] = {"quality": 90, "optimize": True}
            if not self.remove_exif and "exif" in image.info:
                save_options["exif"] = image.info["exif"]
            image.save(output, format="JPEG", **save_options)
            mime = "image/jpeg"
        normalized = output.getvalue()
        self._check_size(len(normalized))
        return f"data:{mime};base64,{base64.b64encode(normalized).decode('ascii')}"

    def _check_size(self, size: int) -> None:
        if size > self.max_bytes:
            raise ImageProcessingError(
                f"图片大小 {size / 1024 / 1024:.2f}MB 超过项目限制 "
                f"{self.max_bytes / 1024 / 1024:.0f}MB"
            )
