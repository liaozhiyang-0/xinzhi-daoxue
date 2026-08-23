from pathlib import Path

from app.services.scenario_catalog import ScenarioCatalog

from scripts.validate_external_sources import validate

ROOT = Path(__file__).resolve().parents[3]


def test_external_source_registry_is_complete_and_manual_reviewed() -> None:
    report = validate()

    assert report["valid"] is True
    assert report["source_count"] >= 1
    catalog_count = len(
        ScenarioCatalog(ROOT / "config" / "scenarios.yaml").list(enabled_only=False)
    )
    assert report["scenarios_with_external_path"] == catalog_count
    assert report["metadata_only_by_default"] is True
    assert report["manual_review_required"] is True
