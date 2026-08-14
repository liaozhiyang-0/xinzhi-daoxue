from scripts.validate_commercial_scenarios import validate


def test_enabled_commercial_scenarios_are_synthetic_and_review_gated() -> None:
    report = validate()

    assert report["valid"] is True
    assert report["catalog_case_count"] == 6
    assert report["case_count"] == 5
    assert report["skipped_disabled_scenarios"] == [
        "research_data_workbench_v1"
    ]
    assert report["all_synthetic"] is True
    assert report["manual_review_required"] is True
