from __future__ import annotations

import asyncio
import io
import re
from pathlib import Path
from uuid import uuid4

from minio import Minio
from minio.error import S3Error
from PIL import Image, ImageOps, UnidentifiedImageError
from urllib3 import PoolManager, Timeout
from urllib3.exceptions import HTTPError as Urllib3HTTPError
from urllib3.util.retry import Retry

from app.core.config import Settings
from app.core.errors import StorageError, ValidationAppError

ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".pdf",
    ".md",
    ".txt",
    ".csv",
    ".tsv",
    ".json",
    ".xlsx",
    ".parquet",
    ".doc",
    ".docx",
}
ALLOWED_CONTENT_TYPES = {
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
    ".md": {"text/markdown", "text/plain"},
    ".txt": {"text/plain"},
    ".csv": {"text/csv", "text/plain"},
    ".tsv": {"text/tab-separated-values", "text/plain", "application/octet-stream"},
    ".json": {"application/json", "text/plain"},
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    },
    ".parquet": {"application/vnd.apache.parquet", "application/octet-stream"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}
SAFE_NAME = re.compile(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+")


def sanitize_filename(filename: str) -> str:
    raw = filename.strip()
    if "/" in raw or "\\" in raw or raw in {".", ".."}:
        raise ValidationAppError("文件名不得包含路径")
    clean = SAFE_NAME.sub("_", raw)
    if not clean or clean in {".", ".."}:
        raise ValidationAppError("文件名无效")
    return clean[:200]


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate(
        self, filename: str, size: int, content_type: str | None = None
    ) -> str:
        safe = sanitize_filename(filename)
        extension = Path(safe).suffix.lower()
        if size <= 0:
            raise ValidationAppError("不允许上传空文件")
        if extension not in ALLOWED_EXTENSIONS:
            raise ValidationAppError("不支持的文件类型")
        if content_type and content_type not in ALLOWED_CONTENT_TYPES[extension]:
            raise ValidationAppError("文件扩展名与 Content-Type 不匹配")
        if size > self.settings.max_upload_size_mb * 1024 * 1024:
            raise ValidationAppError("文件超过大小限制")
        return safe

    def normalize_student_image(
        self, filename: str, content_type: str, data: bytes
    ) -> tuple[str, str, bytes]:
        safe = sanitize_filename(filename)
        extension = Path(safe).suffix.lower()
        allowed = {
            ".png": ("PNG", "image/png"),
            ".jpg": ("JPEG", "image/jpeg"),
            ".jpeg": ("JPEG", "image/jpeg"),
            ".webp": ("WEBP", "image/webp"),
        }
        if extension not in allowed:
            raise ValidationAppError("学生端仅支持jpg、jpeg、png和webp单图片")
        expected_format, expected_mime = allowed[extension]
        if content_type != expected_mime:
            raise ValidationAppError("图片扩展名与Content-Type不匹配")
        if len(data) <= 0:
            raise ValidationAppError("不允许上传空文件")
        if len(data) > self.settings.student_image_max_size_mb * 1024 * 1024:
            raise ValidationAppError("学生图片超过大小限制")
        try:
            with Image.open(io.BytesIO(data)) as probe:
                detected = str(probe.format or "").upper()
                probe.verify()
            if detected != expected_format:
                raise ValidationAppError("图片文件签名与扩展名不匹配")
            with Image.open(io.BytesIO(data)) as source:
                source.seek(0)
                image = ImageOps.exif_transpose(source)
                if image.width * image.height > 40_000_000:
                    raise ValidationAppError("图片像素尺寸过大")
                if expected_format == "JPEG" and image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")
                output = io.BytesIO()
                save_options: dict[str, int | bool] = {"optimize": True}
                if expected_format in {"JPEG", "WEBP"}:
                    save_options["quality"] = 90
                image.save(output, format=expected_format, **save_options)
        except (Image.DecompressionBombError, OSError, UnidentifiedImageError) as exc:
            raise ValidationAppError("图片内容无效或无法安全解码") from exc
        normalized = output.getvalue()
        if len(normalized) > self.settings.student_image_max_size_mb * 1024 * 1024:
            raise ValidationAppError("规范化后的图片仍超过大小限制")
        return safe, expected_mime, normalized

    async def save(self, filename: str, content_type: str, data: bytes) -> str:
        safe = self.validate(filename, len(data), content_type)
        storage_key = f"{uuid4().hex}/{safe}"
        try:
            await asyncio.to_thread(self._save_minio, storage_key, content_type, data)
            return storage_key
        except (OSError, S3Error, Urllib3HTTPError, ValueError) as exc:
            if not self.settings.local_storage_fallback:
                raise StorageError("MinIO 上传失败") from exc
            target = (self.settings.local_storage_path / storage_key).resolve()
            root = self.settings.local_storage_path.resolve()
            if root not in target.parents:
                raise StorageError("本地存储路径越界") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(target.write_bytes, data)
            return f"local:{storage_key}"

    async def delete(self, storage_key: str) -> None:
        if storage_key.startswith("local:"):
            relative = storage_key.removeprefix("local:")
            target = (self.settings.local_storage_path / relative).resolve()
            root = self.settings.local_storage_path.resolve()
            if root in target.parents and target.exists():
                await asyncio.to_thread(target.unlink)
            return
        try:
            await asyncio.to_thread(self._remove_minio, storage_key)
        except (OSError, S3Error, Urllib3HTTPError, ValueError):
            return

    async def read(self, storage_key: str) -> bytes:
        if storage_key.startswith("local:"):
            relative = storage_key.removeprefix("local:")
            target = (self.settings.local_storage_path / relative).resolve()
            root = self.settings.local_storage_path.resolve()
            if root not in target.parents or not target.is_file():
                raise StorageError("本地附件不存在或路径无效")
            try:
                return await asyncio.to_thread(target.read_bytes)
            except OSError as exc:
                raise StorageError("读取本地附件失败") from exc
        try:
            return await asyncio.to_thread(self._read_minio, storage_key)
        except (OSError, S3Error, Urllib3HTTPError, ValueError) as exc:
            raise StorageError("读取 MinIO 附件失败") from exc

    def _client(self) -> Minio:
        return Minio(
            self.settings.minio_endpoint,
            access_key=self.settings.minio_access_key,
            secret_key=self.settings.minio_secret_key,
            secure=self.settings.minio_secure,
            http_client=PoolManager(
                timeout=Timeout(connect=1.0, read=3.0),
                retries=Retry(total=0),
            ),
        )

    def _save_minio(self, key: str, content_type: str, data: bytes) -> None:
        client = self._client()
        if not client.bucket_exists(self.settings.minio_bucket):
            client.make_bucket(self.settings.minio_bucket)
        client.put_object(
            self.settings.minio_bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def _remove_minio(self, key: str) -> None:
        self._client().remove_object(self.settings.minio_bucket, key)

    def _read_minio(self, key: str) -> bytes:
        response = self._client().get_object(self.settings.minio_bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
