from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import httpx

from app.contracts import ExternalEvidenceItem

EXTERNAL_CITATION_REF = re.compile(r"\[([A-Za-z][A-Za-z0-9._:-]{2,63})\]")
HTML_TAG = re.compile(r"<[^>]+>")
ACTIVE_BLOCK = re.compile(
    r"<(?:script|style|noscript)[^>]*>.*?</(?:script|style|noscript)>",
    re.I | re.S,
)
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
PUBLIC_RESOLVER = Callable[[str, int], Sequence[str]]


class ExternalFetchError(RuntimeError):
    """A safe fetch rejection or a source-specific fetch failure."""


@dataclass(frozen=True, slots=True)
class ExternalCitationValidation:
    valid: bool
    referenced_ids: tuple[str, ...]
    valid_ids: tuple[str, ...]
    invalid_ids: tuple[str, ...]
    missing: bool
    warnings: tuple[str, ...]


class ExternalCitationValidator:
    def validate(
        self,
        answer: str,
        items: Sequence[ExternalEvidenceItem],
        declared_references: Sequence[str] = (),
        *,
        require_citations: bool = True,
    ) -> ExternalCitationValidation:
        allowed = {item.evidence_id for item in items}
        declared = [
            value.strip().strip("[]")
            for value in declared_references
            if isinstance(value, str) and value.strip()
        ]
        referenced = tuple(
            dict.fromkeys([*EXTERNAL_CITATION_REF.findall(answer), *declared])
        )
        valid_ids = tuple(value for value in referenced if value in allowed)
        invalid_ids = tuple(value for value in referenced if value not in allowed)
        missing = bool(items) and not referenced
        warnings: list[str] = []
        if require_citations and missing:
            warnings.append("external evidence was used without a citation")
        if invalid_ids:
            warnings.append("answer cited unavailable external evidence")
        return ExternalCitationValidation(
            valid=not warnings,
            referenced_ids=referenced,
            valid_ids=valid_ids,
            invalid_ids=invalid_ids,
            missing=missing,
            warnings=tuple(warnings),
        )


class ExternalContentFetcher:
    """Fetch bounded, untrusted text after DNS and redirect validation."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        max_bytes: int = 120_000,
        max_redirects: int = 2,
        resolver: PUBLIC_RESOLVER | None = None,
    ) -> None:
        self._client = client
        self._owns_client = client is None
        self._client_lock = asyncio.Lock()
        self.max_bytes = max(1, max_bytes)
        self.max_redirects = max(0, max_redirects)
        self._resolver = resolver or _resolve_public_addresses

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    follow_redirects=False,
                    timeout=httpx.Timeout(15),
                )
        assert self._client is not None
        return self._client

    async def fetch(
        self,
        item: ExternalEvidenceItem,
        *,
        max_chars: int = 12_000,
    ) -> ExternalEvidenceItem:
        client = await self._ensure_client()
        current_url = str(item.canonical_url)
        for redirect_count in range(self.max_redirects + 1):
            await self._assert_public_target(current_url)
            try:
                async with client.stream(
                    "GET",
                    current_url,
                    headers={"accept": "text/html, text/plain, application/json"},
                ) as response:
                    if response.status_code in REDIRECT_STATUSES:
                        location = response.headers.get("location", "").strip()
                        if not location or redirect_count >= self.max_redirects:
                            raise ExternalFetchError("redirect_limit_exceeded")
                        current_url = str(httpx.URL(current_url).join(location))
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if not _is_text_content(content_type):
                        raise ExternalFetchError("unsupported_content_type")
                    raw = await _read_bounded(response, self.max_bytes)
            except ExternalFetchError:
                raise
            except httpx.TimeoutException as exc:
                raise ExternalFetchError("fetch_timeout") from exc
            except httpx.HTTPError as exc:
                raise ExternalFetchError("fetch_failed") from exc
            text = _sanitize_external_text(raw, max_chars)
            digest = hashlib.sha256(raw).hexdigest()
            metadata = dict(item.metadata)
            metadata.update(
                {
                    "content_fetched": True,
                    "content_trust": "untrusted_external",
                    "content_type": content_type.split(";", 1)[0].strip(),
                    "redirects": redirect_count,
                }
            )
            return item.model_copy(
                update={
                    "canonical_url": current_url,
                    "content_excerpt": text,
                    "content_hash": digest,
                    "metadata": metadata,
                }
            )
        raise ExternalFetchError("redirect_limit_exceeded")

    async def _assert_public_target(self, value: str) -> None:
        url = httpx.URL(value)
        if url.scheme not in {"http", "https"} or url.username or url.password:
            raise ExternalFetchError("unsafe_url")
        host = url.host
        if not host or host.casefold() == "localhost":
            raise ExternalFetchError("unsafe_host")
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            try:
                resolved = await _resolve_in_thread(
                    self._resolver, host, url.port or 443
                )
            except OSError as exc:
                raise ExternalFetchError("dns_resolution_failed") from exc
            addresses = [ipaddress.ip_address(address) for address in resolved]
        if not addresses or any(
            not _is_public_address(address) for address in addresses
        ):
            raise ExternalFetchError("private_address_rejected")


async def _resolve_in_thread(
    resolver: PUBLIC_RESOLVER, host: str, port: int
) -> Sequence[str]:
    import asyncio

    return await asyncio.to_thread(resolver, host, port)


def _resolve_public_addresses(host: str, port: int) -> Sequence[str]:
    return list(
        dict.fromkeys(
            str(info[4][0])
            for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        )
    )


def _is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
        or address.is_multicast
    )


def _is_text_content(content_type: str) -> bool:
    normalized = content_type.casefold()
    return not normalized or any(
        value in normalized
        for value in ("text/", "application/json", "application/xml")
    )


async def _read_bounded(response: httpx.Response, max_bytes: int) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > max_bytes:
        raise ExternalFetchError("response_too_large")
    data = bytearray()
    async for chunk in response.aiter_bytes():
        data.extend(chunk)
        if len(data) > max_bytes:
            raise ExternalFetchError("response_too_large")
    return bytes(data)


def _sanitize_external_text(raw: bytes, max_chars: int) -> str:
    decoded = raw.decode("utf-8", errors="replace")
    without_active_content = ACTIVE_BLOCK.sub(" ", decoded)
    without_markup = HTML_TAG.sub(" ", without_active_content)
    without_controls = CONTROL_CHARACTERS.sub(" ", without_markup)
    normalized = " ".join(without_controls.split())
    return normalized[: max(1, max_chars)]
