from __future__ import annotations

import logging
import re
from contextvars import ContextVar, Token
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
}
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+"),
    re.compile(
        r"(?i)((?:[?&]|\b)(?:api[_-]?key|token|secret|password)\s*[=:]\s*)[^\s,;&]+"
    ),
    re.compile(r"(?i)(://[^:/\s]+:)[^@\s]+(@)"),
)
REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")
_CONFIGURED = False


def set_request_id(value: str) -> Token[str]:
    return REQUEST_ID.set(value)


def reset_request_id(token: Token[str]) -> None:
    REQUEST_ID.reset(token)


def mask_sensitive_text(value: str) -> str:
    masked = value
    for pattern in SENSITIVE_TEXT_PATTERNS:
        if pattern.groups == 2:
            masked = pattern.sub(r"\1***\2", masked)
        else:
            masked = pattern.sub(r"\1***", masked)
    return masked


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if key.lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return mask_sensitive_text(value)
    return value


def configure_logging(settings: Settings) -> None:
    global _CONFIGURED
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format=(
            "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"
        ),
    )
    logging.getLogger().setLevel(getattr(logging, settings.log_level, logging.INFO))
    if _CONFIGURED:
        return
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        record.request_id = REQUEST_ID.get()
        record.msg = redact(record.msg)
        record.args = redact(record.args)
        return record

    logging.setLogRecordFactory(record_factory)
    _CONFIGURED = True
