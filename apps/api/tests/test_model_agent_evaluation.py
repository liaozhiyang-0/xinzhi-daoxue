from pathlib import Path

from scripts.evaluate_model_agents import load_cases, validate_result


def test_model_agent_cases_are_valid_and_unique() -> None:
    root = Path(__file__).resolve().parents[3]
    cases = load_cases(root / "evaluation" / "model_agents" / "cases.yaml")

    assert len(cases) == 11
    assert len({case["case_id"] for case in cases}) == len(cases)


def test_model_agent_quality_assertions() -> None:
    passed, failures = validate_result(
        {"course": "CT", "keywords": ["电容"]},
        {
            "expect": {"course": "CT"},
            "expect_non_empty": ["keywords"],
        },
    )

    assert passed
    assert failures == []
