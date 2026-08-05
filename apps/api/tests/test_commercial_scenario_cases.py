from scripts.validate_commercial_scenarios import validate


def test_six_commercial_scenarios_are_synthetic_and_review_gated() -> None:
    report = validate()

    assert report["valid"] is True
    assert report["case_count"] == 6
    assert report["all_synthetic"] is True
    assert report["manual_review_required"] is True
