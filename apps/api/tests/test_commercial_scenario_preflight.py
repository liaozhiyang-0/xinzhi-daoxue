from scripts.run_commercial_scenario_preflight import run


def test_enabled_commercial_cases_route_without_network_or_provider_calls() -> None:
    report = run()

    assert report["valid"] is True
    assert report["catalog_case_count"] == 6
    assert report["case_count"] == 5
    assert report["skipped_disabled_scenarios"] == [
        "research_data_workbench_v1"
    ]
    assert report["route_passed_count"] == 5
    assert report["route_only_passed_count"] == 5
    assert report["course_passed_count"] == 5
    assert report["intent_passed_count"] == 5
    assert report["network_calls"] == 0
    assert report["provider_calls"] == 0
