"""Validate a local research-analysis pilot package before API execution.

The validator performs contract and data-manifest checks only. It never calls a
model, searches the web, or runs a statistical analysis. It intentionally omits
the dataset source path from its JSON output.
"""

from __future__ import annotations

# ruff: noqa: E402, I001

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.contracts.research_analysis import ResearchAnalysisRequest  # noqa: E402
from app.services.research_data_quality import (  # noqa: E402
    ResearchDataQualityService,
)
from app.services.research_tabular_io import (  # noqa: E402
    ResearchTabularReadError,
    read_tabular_rows,
)


def validate_pilot_request(
    payload: dict[str, Any], *, check_data: bool = False
) -> dict[str, object]:
    """Return a bounded, path-free readiness report for one pilot request."""

    try:
        request = ResearchAnalysisRequest.model_validate(payload)
    except ValidationError as exc:
        return {
            "valid": False,
            "ready_for_execution": False,
            "status": "invalid_contract",
            "errors": [
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            ],
        }

    gate = ResearchDataQualityService().evaluate(request)
    report: dict[str, object] = {
        "valid": gate.analysis_status == "ready_for_execution",
        "ready_for_execution": gate.analysis_status == "ready_for_execution",
        "status": gate.analysis_status,
        "quality_gate": gate.report.model_dump(mode="json"),
        "reasons": list(gate.reasons),
        "dataset_check": {
            "checked": False,
            "source_ref_included": False,
        },
        "errors": [],
    }
    if not check_data or request.data_manifest is None:
        return report

    dataset_check = _check_local_dataset(request)
    report["dataset_check"] = dataset_check
    errors = list(report["errors"])
    if dataset_check["status"] != "passed":
        errors.append(str(dataset_check["error"]))
        report["valid"] = False
        report["ready_for_execution"] = False
        report["status"] = "dataset_check_failed"
    report["errors"] = errors
    return report


def _check_local_dataset(request: ResearchAnalysisRequest) -> dict[str, object]:
    manifest = request.data_manifest
    assert manifest is not None
    source = manifest.source_ref.strip()
    result: dict[str, object] = {
        "checked": True,
        "source_ref_included": False,
        "status": "failed",
        "checksum_match": False,
        "shape_match": False,
    }
    if not source or "://" in source:
        result["error"] = "pilot_dataset_must_be_a_local_filesystem_source"
        return result
    path = Path(source)
    if not path.is_file():
        result["error"] = "pilot_dataset_file_not_found"
        return result
    actual_checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    checksum_match = actual_checksum == manifest.checksum_sha256
    result["checksum_match"] = checksum_match
    if not checksum_match:
        result["error"] = "pilot_dataset_checksum_mismatch"
        return result
    try:
        columns, rows = read_tabular_rows(path, manifest.format)
    except (OSError, ResearchTabularReadError) as exc:
        result["error"] = str(exc)
        return result
    shape_match = (
        (manifest.row_count is None or manifest.row_count == len(rows))
        and (manifest.column_count is None or manifest.column_count == len(columns))
    )
    result.update(
        {
            "row_count": len(rows),
            "column_count": len(columns),
            "shape_match": shape_match,
        }
    )
    if not shape_match:
        result["error"] = "pilot_dataset_shape_mismatch"
        return result
    result["status"] = "passed"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a local research-analysis pilot request"
    )
    parser.add_argument("--request-json", type=Path, required=True)
    parser.add_argument(
        "--check-data",
        action="store_true",
        help="also verify the local file checksum and declared shape",
    )
    args = parser.parse_args()
    try:
        payload = json.loads(args.request_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"valid": False, "status": "invalid_input", "errors": [str(exc)]},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    if not isinstance(payload, dict):
        print(
            json.dumps(
                {
                    "valid": False,
                    "status": "invalid_input",
                    "errors": ["request_json_must_be_an_object"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    report = validate_pilot_request(payload, check_data=args.check_data)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("valid") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
