r"""Run the four local research-analysis MVPs against synthetic, non-sensitive data.

This script deliberately makes no network calls and does not claim scientific or
commercial performance. It is a reproducible route-and-artifact demonstration for
the local RESEARCH_03_DATA_ANALYSIS_V2 path.

Example (PowerShell, from the repository root)::

    $env:PYTHONPATH = "apps/api"
    .venv\Scripts\python.exe scripts\research_analysis_demo.py `
      --output-root .local_outputs\research-analysis-demo
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from app.contracts.research_analysis import (
    ResearchAnalysisRequest,
    ResearchDataManifest,
    ResearchVariable,
)
from app.services.research_analysis_planner import ResearchAnalysisPlannerService
from app.services.research_local_analysis import ResearchLocalAnalysisExecutor


def _write_csv(path: Path, columns: list[str], rows: list[list[object]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(
    *,
    dataset_path: Path,
    dataset_id: str,
    design: str,
    columns: list[str],
    rows: list[list[object]],
    variables: list[ResearchVariable],
    goal: str,
    output_root: Path,
) -> tuple[ResearchAnalysisRequest, Path]:
    checksum = _write_csv(dataset_path, columns, rows)
    request = ResearchAnalysisRequest(
        research_question=f"Synthetic demonstration for {dataset_id}",
        hypothesis=(
            "The declared groups differ."
            if design in {"experimental_comparison", "small_sample"}
            else ""
        ),
        analysis_goal=goal,  # type: ignore[arg-type]
        design=design,  # type: ignore[arg-type]
        estimand=(
            "difference in observed group means"
            if design in {"experimental_comparison", "small_sample"}
            else ""
        ),
        unit_of_analysis="one synthetic row",
        variables=variables,
        data_manifest=ResearchDataManifest(
            dataset_id=dataset_id,
            version="demo-1",
            format="csv",
            checksum_sha256=checksum,
            row_count=len(rows),
            column_count=len(columns),
            authorized=True,
            source_ref=str(dataset_path),
        ),
        data_dictionary=(
            "Synthetic demonstration data only; values are not research evidence."
        ),
        software_environment="local deterministic MVP demo",
        exploratory=design not in {"experimental_comparison", "small_sample"},
    )
    return request, output_root / "artifacts" / dataset_id


def build_demo_requests(root: Path) -> list[tuple[str, ResearchAnalysisRequest, Path]]:
    variables = {
        "outcome": ResearchVariable(
            name="outcome", role="outcome", unit="score"
        ),
        "treatment": ResearchVariable(name="treatment", role="treatment"),
        "exposure": ResearchVariable(
            name="exposure", role="exposure", unit="dose"
        ),
        "control": ResearchVariable(name="control", role="control", unit="level"),
        "time": ResearchVariable(name="time", role="time", unit="period"),
    }
    cases = [
        _request(
            dataset_path=root / "inputs" / "two_group.csv",
            dataset_id="two_group",
            design="experimental_comparison",
            columns=["outcome", "treatment"],
            rows=[
                [10, "control"],
                [11, "control"],
                [16, "treatment"],
                [18, "treatment"],
            ],
            variables=[variables["outcome"], variables["treatment"]],
            goal="compare",
            output_root=root,
        ),
        _request(
            dataset_path=root / "inputs" / "observational_regression.csv",
            dataset_id="observational_regression",
            design="observational_regression",
            columns=["outcome", "exposure", "control"],
            rows=[[8, 1, 2], [10, 2, 1], [13, 3, 4], [16, 4, 3], [20, 5, 5]],
            variables=[
                variables["outcome"],
                variables["exposure"],
                variables["control"],
            ],
            goal="explain",
            output_root=root,
        ),
        _request(
            dataset_path=root / "inputs" / "time_series.csv",
            dataset_id="time_series",
            design="time_series",
            columns=["time", "outcome"],
            rows=[["2026-01", 10], ["2026-02", 12], ["2026-03", 11], ["2026-04", 14]],
            variables=[variables["time"], variables["outcome"]],
            goal="predict",
            output_root=root,
        ),
        _request(
            dataset_path=root / "inputs" / "small_sample.csv",
            dataset_id="small_sample",
            design="small_sample",
            columns=["outcome", "treatment"],
            rows=[[5, "control"], [7, "control"], [11, "treatment"], [12, "treatment"]],
            variables=[variables["outcome"], variables["treatment"]],
            goal="compare",
            output_root=root,
        ),
    ]
    result: list[tuple[str, ResearchAnalysisRequest, Path]] = []
    for request, output in cases:
        if request.data_manifest is None:
            raise RuntimeError("demo request is missing its data manifest")
        result.append((request.data_manifest.dataset_id, request, output))
    return result


def run_demo(output_root: Path) -> dict[str, Any]:
    root = output_root.resolve()
    planner = ResearchAnalysisPlannerService()
    executor = ResearchLocalAnalysisExecutor(planner_service=planner)
    records: list[dict[str, Any]] = []
    for case_id, request, artifact_root in build_demo_requests(root):
        planning = planner.create_plan(request)
        if planning.plan is None:
            raise RuntimeError(
                f"demo planning failed for {case_id}: {planning.warnings}"
            )
        result = executor.execute(request, planning.plan, output_dir=artifact_root)
        records.append(
            {
                "case_id": case_id,
                "design": request.design,
                "status": result.status,
                "quality_status": result.data_quality.status,
                "artifact_count": len(result.artifacts),
                "artifact_root": str(artifact_root.relative_to(root)),
                "human_review_required": result.human_review_required,
                "limitations": result.limitations,
            }
        )
    manifest = {
        "demo_type": "synthetic_local_research_analysis_v2",
        "network_calls": 0,
        "external_evidence_used": False,
        "records": records,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "demo_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help=(
            "Directory for synthetic inputs, analysis artifacts, and "
            "demo_manifest.json."
        ),
    )
    args = parser.parse_args()
    manifest = run_demo(args.output_root)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
