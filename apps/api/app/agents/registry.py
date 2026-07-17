from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.core.config import PROJECT_ROOT


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    agent_id: str
    provider: str
    enabled: bool
    publication_status: str
    mode: str


@dataclass(frozen=True, slots=True)
class RoutingRule:
    course_ids: frozenset[str]
    intents: frozenset[str]
    agent_id: str
    scene: str
    retrieval_required: bool
    provider_required: bool


class AgentRegistry:
    """Validated, read-only view of the YAML agent and routing registry."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PROJECT_ROOT / "agent_configs" / "registry.yaml"
        payload = self._load_payload(self.path)
        self._agents = self._load_agents(payload.get("agents"))
        self._routing_rules = self._load_rules(payload.get("routing"))

    @staticmethod
    def _load_payload(path: Path) -> dict[str, Any]:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ValueError(f"无法读取 Agent 注册表: {path}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Agent 注册表顶层必须是映射")
        return payload

    @staticmethod
    def _load_agents(value: Any) -> dict[str, AgentDefinition]:
        if not isinstance(value, dict) or not value:
            raise ValueError("Agent 注册表必须包含非空 agents")
        agents: dict[str, AgentDefinition] = {}
        for agent_id, raw in value.items():
            if not isinstance(agent_id, str) or not isinstance(raw, dict):
                raise ValueError("agents 条目格式无效")
            agents[agent_id] = AgentDefinition(
                agent_id=agent_id,
                provider=str(raw.get("provider", "local")),
                enabled=bool(raw.get("enabled", True)),
                publication_status=str(raw.get("publication_status", "local")),
                mode=str(raw.get("mode", "provider")),
            )
        return agents

    def _load_rules(self, value: Any) -> tuple[RoutingRule, ...]:
        if not isinstance(value, list) or not value:
            raise ValueError("Agent 注册表必须包含非空 routing")
        rules: list[RoutingRule] = []
        for raw in value:
            if not isinstance(raw, dict):
                raise ValueError("routing 条目必须是映射")
            agent_id = str(raw.get("agent_id", ""))
            if agent_id not in self._agents:
                raise ValueError(f"routing 引用了未注册 Agent: {agent_id}")
            course_ids = frozenset(str(item) for item in raw.get("course_ids", []))
            intents = frozenset(str(item) for item in raw.get("intents", []))
            if not course_ids or not intents:
                raise ValueError("routing 条目必须包含 course_ids 和 intents")
            rules.append(
                RoutingRule(
                    course_ids=course_ids,
                    intents=intents,
                    agent_id=agent_id,
                    scene=str(raw.get("scene", "learning")),
                    retrieval_required=bool(raw.get("retrieval_required", False)),
                    provider_required=bool(raw.get("provider_required", False)),
                )
            )
        return tuple(rules)

    @property
    def routing_rules(self) -> tuple[RoutingRule, ...]:
        return self._routing_rules

    def get(self, agent_id: str) -> AgentDefinition:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise KeyError(f"未注册 Agent: {agent_id}") from exc

    def list_agents(self) -> tuple[AgentDefinition, ...]:
        return tuple(self._agents.values())
