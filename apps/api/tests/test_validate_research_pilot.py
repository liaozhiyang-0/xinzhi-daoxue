from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.validate_research_pilot import validate_pilot_request


def _payload(path: Path, checksum: str) -> dict[str, object]:
    return {
        "research_question": "Do the declared groups differ?",
        "hypothesis": "The declared groups differ.",
        "analysis_goal": "compare",
        "design": "experimental_comparison",
        "unit_of_analysis": "one row",
        "variables": [
            {"name": "outcome", "role": "outcome", "unit": "score"},
            {"name": "treatment", "role": "treatment", "unit": "label"},
        ],
        "data_manifest": {
            "dataset_id": "pilot-dataset",
            "version": "1",
            "format": "csv",
            "checksum_sha256": checksum,
            "row_count": 4,
            "column_count": 2,
            "authorized": True,
            "source_ref": str(path),
        },
        "data_dictionary": "outcome is a score; treatment is a declared group",
        "exploratory": False,
    }


def test_pilot_validator_checks_checksum_shape_and_hides_source_path(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "pilot.csv"
    data_path.write_text(
        "outcome,treatment\n10,control\n12,control\n16,treatment\n18,treatment\n",
        encoding="utf-8",
    )
    checksum = hashlib.sha256(data_path.read_bytes()).hexdigest()

    report = validate_pilot_request(_payload(data_path, checksum), check_data=True)

    assert report["valid"] is True
    assert report["ready_for_execution"] is True
    assert report["dataset_check"]["status"] == "passed"
    assert report["dataset_check"]["source_ref_included"] is False
    assert str(data_path) not in str(report)


def test_pilot_validator_blocks_checksum_mismatch(tmp_path: Path) -> None:
    data_path = tmp_path / "pilot.csv"
    data_path.write_text("outcome,treatment\n10,control\n", encoding="utf-8")

    report = validate_pilot_request(_payload(data_path, "0" * 64), check_data=True)

    assert report["valid"] is False
    assert report["status"] == "dataset_check_failed"
    assert "pilot_dataset_checksum_mismatch" in report["errors"]


def test_pilot_validator_reports_contract_errors_without_raw_payload() -> None:
    report = validate_pilot_request(
        {"research_question": "", "source_ref": "C:\\private\\dataset.csv"}
    )

    assert report["valid"] is False
    assert report["status"] == "invalid_contract"
    assert "C:\\private\\dataset.csv" not in str(report)
