from scripts.validate_external_sources import validate


def test_external_source_registry_is_complete_and_manual_reviewed() -> None:
    report = validate()

    assert report["valid"] is True
    assert report["source_count"] == 3
    assert report["scenarios_with_external_path"] == 6
    assert report["metadata_only_by_default"] is True
    assert report["manual_review_required"] is True
