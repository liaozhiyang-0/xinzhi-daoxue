from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime


def normalize_login(value: str) -> str:
    return value.strip().casefold()


def hash_password(password: str, *, n_log2: int, r: int, p: int) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=1 << n_log2,
        r=r,
        p=p,
        maxmem=128 * 1024 * 1024,
    )
    encode = base64.urlsafe_b64encode
    return "$".join(
        (
            "scrypt",
            f"ln={n_log2},r={r},p={p}",
            encode(salt).decode("ascii").rstrip("="),
            encode(digest).decode("ascii").rstrip("="),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, parameters, salt_text, digest_text = encoded.split("$", 3)
        if scheme != "scrypt":
            return False
        values = dict(item.split("=", 1) for item in parameters.split(","))
        n_log2 = int(values["ln"])
        r = int(values["r"])
        p = int(values["p"])
        if not 14 <= n_log2 <= 20 or not 1 <= r <= 32 or not 1 <= p <= 8:
            return False
        decode = base64.urlsafe_b64decode
        salt = decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = decode(digest_text + "=" * (-len(digest_text) % 4))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=1 << n_log2,
            r=r,
            p=p,
            maxmem=128 * 1024 * 1024,
        )
    except (ValueError, KeyError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def create_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_guest_token(signing_key: str, *, ttl_seconds: int) -> str:
    """Create a stateless, signed browser-scoped guest identity token."""
    if not signing_key:
        raise ValueError("guest signing key must not be empty")
    guest_id = f"guest_{secrets.token_hex(16)}"
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{guest_id}.{expires_at}"
    signature = hmac.new(
        signing_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_guest_token(
    token: str, signing_key: str, *, now: int | None = None
) -> tuple[str, datetime] | None:
    """Return the guest id and expiry only when the signed token is valid."""
    if not token or not signing_key:
        return None
    try:
        guest_id, expires_text, signature = token.split(".", 2)
        expires_at = int(expires_text)
    except (AttributeError, ValueError):
        return None
    current = int(time.time() if now is None else now)
    if not guest_id.startswith("guest_") or expires_at <= current:
        return None
    payload = f"{guest_id}.{expires_at}"
    expected = hmac.new(
        signing_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    return guest_id, datetime.fromtimestamp(expires_at, tz=UTC)
