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
            definition = registry.get(item.agent_id)
        except KeyError:
            missing_agents.add(item.agent_id)
            continue
        unsupported_courses = set(item.courses) - set(definition.capabilities.courses)
        unsupported_roles = set(item.roles) - set(definition.capabilities.user_roles)
        unsupported_intents = set(item.intents) - set(definition.capabilities.intents)
        unsupported_inputs = set(item.input_modes) - set(
            definition.capabilities.input_modes
        )
        if (
            unsupported_courses
            or unsupported_roles
            or unsupported_intents
            or unsupported_inputs
        ):
            raise ValueError(
                f"{item.id}: 超出 Agent 能力契约 "
                f"courses={sorted(unsupported_courses)} "
                f"roles={sorted(unsupported_roles)} "
                f"intents={sorted(unsupported_intents)} "
                f"inputs={sorted(unsupported_inputs)}"
            )
        policy = item.evidence_policy
        if policy.citation_required and not item.evidence_requirements:
            raise ValueError(f"{item.id}: 引用要求缺少场景证据要求")
        if (
            policy.allow_synthetic
            and "synthetic" not in policy.supplemental_source_types
        ):
            raise ValueError(f"{item.id}: allow_synthetic 必须声明 synthetic 补充来源")
    missing_agent_list = sorted(missing_agents)
    if missing_agent_list:
        raise ValueError(f"场景引用了不存在的 Agent: {', '.join(missing_agent_list)}")
    return {
        "valid": True,
        "catalog_version": catalog.document.version,
        "scenario_count": len(catalog.list(enabled_only=False)),
        "enabled_count": len(catalog.list()),
        "evidence_policy_count": len(catalog.list()),
        "agent_ids": sorted({item.agent_id for item in catalog.list()}),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
