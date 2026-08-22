from __future__ import annotations

from scripts.evaluate_planner_shadow import evaluate, load_cases


def test_planner_shadow_evaluation_is_go_for_controlled_canary() -> None:
    report = evaluate(load_cases())

    assert report["case_count"] == 5
    assert set(report["categories"]) == {
        "academic_solver",
        "knowledge_qa",
        "teaching",
        "research",
        "general_fallback",
    }
    assert report["readiness"] == "GO_FOR_CONTROLLED_CANARY"
    assert report["no_production_takeover"] is True
    assert report["checks"]["invalid_target_rate"] == 0
    assert report["checks"]["unsupported_capability_rate"] == 0
    assert report["checks"]["route_parity_rate"] == 1
    assert report["checks"]["plan_parity_rate"] == 1
