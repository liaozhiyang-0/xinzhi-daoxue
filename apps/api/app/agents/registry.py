from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.core.config import PROJECT_ROOT, Settings


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    agent_id: str
    provider: str
    flow_env: str
    enabled: bool
    mode: str


class AgentRegistry:
    """Validated, read-only view of the existing Agent registry."""

    ROUTING_TARGETS = frozenset({"SOLVER_CT_V1", "LEARN_01_KNOWLEDGE_QA_V1"})

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PROJECT_ROOT / "agent_configs" / "registry.yaml"
        payload = self._load(self.path)
        raw_agents = payload.get("agents")
        if not isinstance(raw_agents, dict) or not raw_agents:
            raise ValueError("Agent 注册表必须包含非空 agents")
        self._agents: dict[str, AgentDefinition] = {}
        for agent_id, raw in raw_agents.items():
            if not isinstance(agent_id, str) or not isinstance(raw, dict):
                raise ValueError("Agent 注册表条目格式无效")
            self._agents[agent_id] = AgentDefinition(
                agent_id=agent_id,
                provider=str(raw.get("provider", "xingchen")),
                flow_env=str(raw.get("flow_env", "")),
                enabled=bool(raw.get("enabled", True)),
                mode=str(raw.get("mode", "professional_solver")),
            )

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ValueError(f"无法读取 Agent 注册表: {path}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Agent 注册表顶层必须是映射")
        return payload

    def get(self, agent_id: str) -> AgentDefinition:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise KeyError(f"未注册 Agent: {agent_id}") from exc

    def available_routing_targets(self) -> list[str]:
        return [
            agent_id
            for agent_id in sorted(self.ROUTING_TARGETS)
            if agent_id in self._agents and self._agents[agent_id].enabled
        ]

    def resolve_flow_id(self, agent_id: str, settings: Settings) -> str:
        self.get(agent_id)
        mapping = {
            "SOLVER_CT_V1": settings.xingchen_solver_ct_flow_id
            or settings.xingchen_solver_ct_workflow_id,
            "LEARN_01_KNOWLEDGE_QA_V1": settings.xingchen_knowledge_qa_flow_id,
            "ROUTER_01_FALLBACK_V1": settings.xingchen_fallback_router_flow_id,
        }
        return mapping.get(agent_id, "").strip()

    def is_callable(self, agent_id: str, settings: Settings) -> bool:
        try:
            definition = self.get(agent_id)
        except KeyError:
            return False
        return definition.enabled and bool(self.resolve_flow_id(agent_id, settings))

    def timeout_seconds(self, agent_id: str, settings: Settings) -> float:
        return {
            "SOLVER_CT_V1": settings.xingchen_solver_timeout_seconds,
            "LEARN_01_KNOWLEDGE_QA_V1": settings.xingchen_knowledge_timeout_seconds,
            "ROUTER_01_FALLBACK_V1": settings.xingchen_router_timeout_seconds,
        }.get(agent_id, settings.xingchen_timeout_seconds)

    def cache_ttl_seconds(self, agent_id: str, settings: Settings) -> int:
        return {
            "SOLVER_CT_V1": settings.xingchen_solver_cache_ttl_seconds,
            "LEARN_01_KNOWLEDGE_QA_V1": settings.xingchen_knowledge_cache_ttl_seconds,
            "ROUTER_01_FALLBACK_V1": settings.xingchen_router_cache_ttl_seconds,
        }.get(agent_id, 0)

