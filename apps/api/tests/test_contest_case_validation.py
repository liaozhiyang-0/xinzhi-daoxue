from scripts.validate_contest_cases import validate


def test_contest_cases_are_linked_to_scenarios_and_marked_synthetic() -> None:
    report = validate()

    assert report["valid"] is True
    assert report["case_count"] == 3
    assert report["all_synthetic"] is True
    assert report["manual_review_required"] is True
