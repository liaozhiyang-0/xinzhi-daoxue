from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.agents import AgentRegistry  # noqa: E402
from app.services.scenario_catalog import ScenarioCatalog  # noqa: E402


def validate() -> dict[str, object]:
    catalog = ScenarioCatalog(ROOT / "config" / "scenarios.yaml")
    registry = AgentRegistry()
    missing_agents: set[str] = set()
    for item in catalog.list(enabled_only=False):
        try:
            registry.get(item.agent_id)
        except KeyError:
            missing_agents.add(item.agent_id)
    missing_agent_list = sorted(missing_agents)
    if missing_agent_list:
        raise ValueError(f"场景引用了不存在的 Agent: {', '.join(missing_agent_list)}")
    return {
        "valid": True,
        "catalog_version": catalog.document.version,
        "scenario_count": len(catalog.list(enabled_only=False)),
        "enabled_count": len(catalog.list()),
        "agent_ids": sorted({item.agent_id for item in catalog.list()}),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
