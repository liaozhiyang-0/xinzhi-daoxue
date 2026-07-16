from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402


def safe_status(value: str, *, required: bool) -> str:
    if value:
        return "configured"
    return "missing" if required else "not_required"


def validate(settings: Settings) -> dict[str, object]:
    return {
        "valid": True,
        "app_env": settings.app_env,
        "database": {
            "url": safe_status(settings.active_database_url, required=True),
        },
        "redis": {"url": safe_status(settings.redis_url, required=True)},
        "minio": {
            "endpoint": safe_status(settings.minio_endpoint, required=True),
            "credentials": (
                "configured"
                if settings.minio_access_key and settings.minio_secret_key
                else "missing"
            ),
        },
        "provider": {
            "requested": settings.default_agent_provider,
            "allow_mock_fallback": settings.allow_mock_fallback,
            "publication_status": settings.xingchen_publication_status,
            "runtime_configuration_required": False,
            "xingchen_api_key": "not_required",
            "xingchen_base_url": "not_required",
            "xingchen_workflow_id": "not_required",
        },
        "uploads": {
            "max_size_mb": settings.max_upload_size_mb,
            "local_fallback": settings.local_storage_fallback,
            "local_path": str(settings.local_storage_path),
        },
        "knowledge": {
            "enabled": settings.knowledge_enabled,
            "sources": {
                course_id: "available" if path.is_dir() else "unavailable"
                for course_id, path in settings.knowledge_paths.items()
            },
            "chunk_size_chars": settings.knowledge_chunk_size_chars,
            "chunk_overlap_chars": settings.knowledge_chunk_overlap_chars,
            "default_top_k": settings.knowledge_default_top_k,
        },
    }


def main() -> int:
    if os.getenv("APP_ENV") is None:
        os.environ.setdefault("APP_ENV", "development")
    try:
        result = validate(Settings())
    except Exception as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
