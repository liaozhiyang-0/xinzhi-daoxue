from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

def validate() -> dict[str, object]:
    from app.evaluation.loader import EvaluationCaseLoader  # type: ignore[import-untyped]  # noqa: I001,E501
    from app.services.scenario_catalog import ScenarioCatalog  # type: ignore[import-untyped]

    case_root = ROOT / "evaluation" / "cases" / "contest_scenarios"
    cases = EvaluationCaseLoader(case_root).load_all()
    catalog = ScenarioCatalog(ROOT / "config" / "scenarios.yaml")
    if len(cases) < 3:
        raise ValueError("赛题基线至少需要三个典型问题")
    scenario_ids: set[str] = set()
    for case in cases:
        scenario_id = str(case.task_options.get("scenario_id", ""))
        scenario = catalog.get(scenario_id)
        scenario_ids.add(scenario.id)
        if scenario.agent_id != case.expected_agent:
            raise ValueError(
                f"{case.case_id}: expected_agent 与场景 Agent 不一致"
            )
        if case.provenance.source_type != "synthetic":
            raise ValueError(f"{case.case_id}: 当前基线必须明确标记为 synthetic")
        if not case.requires_manual_review:
            raise ValueError(f"{case.case_id}: 赛题基线必须保留人工复核门槛")
        if not case.evidence_requirements:
            raise ValueError(f"{case.case_id}: 缺少证据要求")
    return {
        "valid": True,
        "case_count": len(cases),
        "scenario_ids": sorted(scenario_ids),
        "all_synthetic": True,
        "manual_review_required": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
