from __future__ import annotations

import hashlib
import json
from typing import Any

from redis.asyncio import Redis

from app.agents.registry import AgentRegistry
from app.contracts import AgentRequest, AgentResult
from app.core.config import Settings


class WorkflowCache:
    def __init__(self, settings: Settings, registry: AgentRegistry) -> None:
        self.settings = settings
        self.registry = registry

    def key(
        self,
        agent_id: str,
        request: AgentRequest,
        *,
        course_id: str,
        intent: str,
        source_refs: list[str],
    ) -> str:
        text_values = [
            value.strip()
            for key, value in sorted(request.canonical_input.items())
            if isinstance(value, str) and value.strip()
        ]
        image_hashes = [
            attachment.checksum_sha256 or attachment.storage_key
            for attachment in request.attachments
        ]
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "flow_id": self.registry.resolve_flow_id(agent_id, self.settings),
            "text": "\n".join(text_values),
            "images": image_hashes,
            "course_id": course_id,
            "intent": intent,
            "source_refs": source_refs,
        }
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return f"xzd:workflow:{digest}"

    async def get(self, key: str) -> AgentResult | None:
        client = Redis.from_url(
            self.settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        try:
            payload = await client.get(key)
        finally:
            await client.aclose()
        if not payload:
            return None
        return AgentResult.model_validate_json(payload)

    async def set(self, key: str, result: AgentResult, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        client = Redis.from_url(
            self.settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        try:
            await client.set(key, result.model_dump_json(), ex=ttl_seconds)
        finally:
            await client.aclose()
