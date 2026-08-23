from __future__ import annotations

from scripts.run_runtime_authorized_dev_e2e import (
    CASES,
    paired_input_payload,
)


def test_paired_input_snapshot_keeps_content_and_drops_upload_identity() -> None:
    case = next(
        item
        for item in CASES
        if item.case_id == "research_data_analysis_runtime_handoff"
    )
    runtime_request = {
        **case.runtime_request,
        "data_manifest": {
            "dataset_id": "research-data-analysis-runtime-handoff-synthetic",
            "checksum_sha256": "0" * 64,
            "source_ref": "attachment:upload-generated-id",
        },
    }

    snapshot = paired_input_payload(
        case,
        attachments=[
            {
                "file_id": "upload-generated-id",
                "storage_key": "private/random-key",
                "filename": "sample.csv",
                "content_type": "text/csv",
                "size_bytes": 42,
                "checksum_sha256": "0" * 64,
            }
        ],
        runtime_request=runtime_request,
    )

    assert snapshot["attachments"] == [
        {
            "filename": "sample.csv",
            "content_type": "text/csv",
            "size_bytes": 42,
            "checksum_sha256": "0" * 64,
        }
    ]
    assert snapshot["runtime_request"]["data_manifest"]["source_ref"] == (
        "dataset:research-data-analysis-runtime-handoff-synthetic"
    )
    serialized = str(snapshot)
    assert "upload-generated-id" not in serialized
    assert "private/random-key" not in serialized


def test_paired_input_snapshot_is_independent_of_runtime_mode_switch() -> None:
    case = CASES[0]
    legacy = paired_input_payload(
        case,
        attachments=[],
        runtime_request=None,
    )
    runtime = paired_input_payload(
        case,
        attachments=[],
        runtime_request=None,
    )

    assert legacy == runtime
