from __future__ import annotations

import re

_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._:+/=-]+")
_KEY_RE = re.compile(
    r"(?i)(api[_-]?key|api[_-]?secret|authorization|password)"
    r"\s*[:=]\s*[^\s,;]+"
)
_DATA_URL_RE = re.compile(r"data:image/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=]+")


def redact_sensitive_text(value: object, *, max_length: int = 300) -> str:
    text = str(value)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _KEY_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = _DATA_URL_RE.sub("data:image/[REDACTED];base64,[REDACTED]", text)
    return text[:max_length]
