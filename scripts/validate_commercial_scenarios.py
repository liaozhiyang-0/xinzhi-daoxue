from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.evaluation.loader import EvaluationCaseLoader  # noqa: E402
from app.services.scenario_catalog import ScenarioCatalog  # noqa: E402


def validate() -> dict[str, object]:
    cases = EvaluationCaseLoader(
        ROOT / "evaluation" / "cases" / "commercial_scenarios"
    ).load_all()
    catalog = ScenarioCatalog(ROOT / "config" / "scenarios.yaml")
    scenarios = catalog.list()
    expected_ids = {item.id for item in scenarios}
    actual_ids: set[str] = set()
    for case in cases:
        scenario_id = str(case.task_options.get("scenario_id", ""))
        if scenario_id in actual_ids:
            raise ValueError(f"duplicate commercial scenario case: {scenario_id}")
        actual_ids.add(scenario_id)
        scenario = catalog.get(scenario_id)
        if case.expected_agent != scenario.agent_id:
            raise ValueError(f"{case.case_id}: expected_agent does not match scenario")
        if case.provenance.source_type != "synthetic":
            raise ValueError(f"{case.case_id}: case must remain synthetic")
        if case.requires_manual_review is not True:
            raise ValueError(f"{case.case_id}: manual review gate is required")
        if case.expected_citations is not True or not case.min_citation_count:
            raise ValueError(f"{case.case_id}: citation acceptance criteria missing")
        if not case.reference_solution.get("required_sections"):
            raise ValueError(f"{case.case_id}: standard answer sections missing")
        if not case.evidence_requirements:
            raise ValueError(f"{case.case_id}: evidence requirements missing")
        commercialization = scenario.commercialization
        if not all(
            (
                commercialization.buyer,
                commercialization.delivery_unit,
                commercialization.value_capture,
                commercialization.expansion_path,
            )
        ):
            raise ValueError(f"{case.case_id}: commercialization plan incomplete")
    if len(cases) != 6 or actual_ids != expected_ids:
        raise ValueError(
            f"commercial scenario coverage mismatch: expected={sorted(expected_ids)} "
            f"actual={sorted(actual_ids)}"
        )
    return {
        "valid": True,
        "case_count": len(cases),
        "scenario_ids": sorted(actual_ids),
        "all_synthetic": True,
        "manual_review_required": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
