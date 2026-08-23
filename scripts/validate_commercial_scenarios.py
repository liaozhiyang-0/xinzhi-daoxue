from __future__ import annotations

# ruff: noqa: E402, I001

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

# ruff: noqa: E402
from app.evaluation.loader import (  # type: ignore[import-untyped]
    EvaluationCaseLoader,
)
from app.services.scenario_catalog import ScenarioCatalog  # type: ignore[import-untyped]


CASE_DOCS = {
    "faculty_course_copilot_v1": "faculty_course_copilot_v1.md",
    "assessment_diagnosis_v1": "assessment_diagnosis_v1.md",
    "student_learning_path_v1": "student_learning_path_v1.md",
    "research_data_workbench_v1": "research_data_workbench_v1.md",
    "academic_visual_problem_solver_v1": "academic_visual_problem_solver_v1.md",
    "academic_visual_spectrum_solver_v1": "academic_visual_spectrum_solver_v1.md",
    "academic_text_diagnostic_solver_v1": "academic_text_diagnostic_solver_v1.md",
    "rubric_generation_v1": "rubric_generation_v1.md",
    "department_knowledge_governance_v1": "department_knowledge_governance_v1.md",
}


def validate() -> dict[str, object]:
    cases = EvaluationCaseLoader(
        ROOT / "evaluation" / "cases" / "commercial_scenarios"
    ).load_all()
    catalog = ScenarioCatalog(ROOT / "config" / "scenarios.yaml")
    all_scenarios = catalog.list(enabled_only=False)
    scenarios = [item for item in all_scenarios if item.enabled]
    expected_ids = {item.id for item in scenarios}
    actual_ids: set[str] = set()
    skipped_disabled_ids: list[str] = []
    for case in cases:
        scenario_id = str(case.task_options.get("scenario_id", ""))
        if scenario_id in actual_ids:
            raise ValueError(f"duplicate commercial scenario case: {scenario_id}")
        scenario = next(
            (item for item in all_scenarios if item.id == scenario_id),
            None,
        )
        if scenario is None:
            raise ValueError(
                "commercial case references unknown scenario: "
                f"{scenario_id}"
            )
        if not scenario.enabled:
            # A frozen scenario remains documented and auditable, but must not
            # be treated as an enabled commercial execution path.
            skipped_disabled_ids.append(scenario_id)
            continue
        actual_ids.add(scenario_id)
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
        if len(scenario.demo_steps) < 6:
            raise ValueError(f"{case.case_id}: six executable demo steps are required")
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
    if actual_ids != expected_ids:
        raise ValueError(
            f"commercial scenario coverage mismatch: expected={sorted(expected_ids)} "
            f"actual={sorted(actual_ids)}"
        )
    docs_root = ROOT / "docs" / "commercial_cases"
    missing_docs = sorted(
        filename
        for scenario_id, filename in CASE_DOCS.items()
        if scenario_id in expected_ids and not (docs_root / filename).is_file()
    )
    if missing_docs:
        raise ValueError(f"commercial case documents missing: {missing_docs}")
    return {
        "valid": True,
        "case_count": len(actual_ids),
        "catalog_case_count": len(cases),
        "scenario_ids": sorted(actual_ids),
        "skipped_disabled_scenarios": sorted(set(skipped_disabled_ids)),
        "all_synthetic": True,
        "manual_review_required": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
