from __future__ import annotations

import re

SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\b(api[_ -]?key|secret|password|token)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\b\d{17}[\dXx]\b"),
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"(?i)\b[A-Z]:\\(?:[^\\\r\n]+\\)+[^\\\r\n]*"),
)


def sanitize_runtime_text(value: str, *, max_chars: int = 50_000) -> str:
    text = " ".join(value.split())[:max_chars]
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub("[已脱敏]", text)
    return text


def contains_sensitive_information(value: str) -> bool:
    return any(pattern.search(value) for pattern in SENSITIVE_PATTERNS)
