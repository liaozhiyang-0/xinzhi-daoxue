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
    all_scenarios = catalog.list(enabled_only=False)
    scenarios_by_id = {item.id: item for item in all_scenarios}
    scenario_ids: set[str] = set()
    skipped_disabled_ids: list[str] = []
    for case in cases:
        scenario_id = str(case.task_options.get("scenario_id", ""))
        scenario = scenarios_by_id.get(scenario_id)
        if scenario is None:
            raise ValueError(f"{case.case_id}: unknown scenario {scenario_id}")
        if not scenario.enabled:
            skipped_disabled_ids.append(scenario_id)
            continue
        scenario_ids.add(scenario.id)
        if scenario.agent_id != case.expected_agent:
            raise ValueError(
                f"{case.case_id}: expected_agent 与场景 Agent 不一致"
            )
        if (
            case.provenance.source_type == "synthetic"
            and not scenario.evidence_policy.allow_synthetic
        ):
            raise ValueError(f"{case.case_id}: 场景策略不允许 synthetic 来源")
        if scenario.evidence_policy.citation_required != (
            case.expected_citations is True
        ):
            raise ValueError(f"{case.case_id}: 引用要求与场景证据策略不一致")
        if (
            scenario.evidence_policy.manual_review_required
            and not case.requires_manual_review
        ):
            raise ValueError(f"{case.case_id}: 场景策略要求人工复核")
        if case.provenance.source_type != "synthetic":
            raise ValueError(f"{case.case_id}: 当前基线必须明确标记为 synthetic")
        if not case.requires_manual_review:
            raise ValueError(f"{case.case_id}: 赛题基线必须保留人工复核门槛")
        if not case.evidence_requirements:
            raise ValueError(f"{case.case_id}: 缺少证据要求")
        required_sections = case.reference_solution.get("required_sections")
        if not isinstance(required_sections, list) or not required_sections:
            raise ValueError(f"{case.case_id}: 缺少标准答案结构")
        if not case.required_keywords or not case.required_steps:
            raise ValueError(f"{case.case_id}: 缺少关键词或步骤验收标准")
        if case.expected_citations is not True or not case.min_citation_count:
            raise ValueError(f"{case.case_id}: 缺少引用数量验收标准")
    return {
        "valid": True,
        "case_count": len(scenario_ids),
        "catalog_case_count": len(cases),
        "scenario_ids": sorted(scenario_ids),
        "skipped_disabled_scenarios": sorted(set(skipped_disabled_ids)),
        "all_synthetic": True,
        "manual_review_required": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
