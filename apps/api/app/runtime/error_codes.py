from __future__ import annotations

from typing import Any

_ALIASES = {
    "timeouterror": "provider_timeout",
    "asyncio.timeouterror": "provider_timeout",
    "timeout": "provider_timeout",
    "provider_runtime_result_missing": "runtime_result_missing",
    "provider_result_missing": "runtime_result_missing",
    "provider_cancelled": "cancelled",
}


def normalize_runtime_error_code(
    value: Any, *, default: str = "runtime_node_error"
) -> str:
    """Map raw node exceptions to stable Runtime error codes."""

    code = str(value or "").strip()
    if not code:
        return default
    return _ALIASES.get(code.casefold(), code)
