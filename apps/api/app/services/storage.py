from __future__ import annotations

import asyncio
import io
import re
from pathlib import Path
from uuid import uuid4

from minio import Minio
from minio.error import S3Error
from urllib3 import PoolManager, Timeout
from urllib3.exceptions import HTTPError as Urllib3HTTPError
from urllib3.util.retry import Retry

from app.core.config import Settings
from app.core.errors import StorageError, ValidationAppError

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".md", ".txt"}
ALLOWED_CONTENT_TYPES = {
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".pdf": {"application/pdf"},
    ".md": {"text/markdown", "text/plain"},
    ".txt": {"text/plain"},
}
SAFE_NAME = re.compile(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+")


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    clean = SAFE_NAME.sub("_", name)
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
        if extension not in ALLOWED_EXTENSIONS:
            raise ValidationAppError("不支持的文件类型")
        if content_type and content_type not in ALLOWED_CONTENT_TYPES[extension]:
            raise ValidationAppError("文件扩展名与 Content-Type 不匹配")
        if size > self.settings.max_upload_size_mb * 1024 * 1024:
            raise ValidationAppError("文件超过大小限制")
        return safe

    async def save(self, filename: str, content_type: str, data: bytes) -> str:
        safe = self.validate(filename, len(data), content_type)
        storage_key = f"{uuid4().hex}/{safe}"
        try:
            await asyncio.to_thread(
                self._save_minio, storage_key, content_type, data
            )
            return storage_key
        except (OSError, S3Error, Urllib3HTTPError, ValueError) as exc:
            if not self.settings.local_storage_fallback:
                raise StorageError("MinIO 上传失败") from exc
            target = self.settings.local_storage_path / storage_key
            target.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(target.write_bytes, data)
            return f"local:{storage_key}"

    def _save_minio(self, key: str, content_type: str, data: bytes) -> None:
        client = Minio(
            self.settings.minio_endpoint,
            access_key=self.settings.minio_access_key,
            secret_key=self.settings.minio_secret_key,
            secure=self.settings.minio_secure,
            http_client=PoolManager(
                timeout=Timeout(connect=1.0, read=3.0),
                retries=Retry(total=0),
            ),
        )
        if not client.bucket_exists(self.settings.minio_bucket):
            client.make_bucket(self.settings.minio_bucket)
        client.put_object(
            self.settings.minio_bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
