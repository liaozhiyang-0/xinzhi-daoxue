from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings

SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "database_url",
    "password",
    "secret",
    "token",
    "xingchen_api_key",
    "xingchen_api_secret",
}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if key.lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def mask_sensitive_text(value: str) -> str:
    """Keep upstream previews useful without echoing common credential fields."""

    lowered = value.lower()
    if any(key in lowered for key in ("authorization", "api_key", "api_secret")):
        return "***"
    return value


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
