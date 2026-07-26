import json
from pathlib import Path


def test_saved_draft_benchmark_runs_have_required_metrics() -> None:
    root = Path(__file__).parents[3] / "evaluation" / "knowledge_retrieval" / "results"
    required = {
        "Recall@1",
        "Recall@3",
        "Recall@5",
        "MRR",
        "nDCG@5",
        "zero_hit_rate",
        "wrong_course_rate",
        "mean_latency_ms",
        "p95_latency_ms",
    }
    for run_id in ("baseline_lexical_v1", "local_lexical_v2"):
        payload = json.loads((root / f"{run_id}.json").read_text(encoding="utf-8"))
        assert payload["case_count"] == 15
        assert payload["case_status"] == "draft"
        assert required == set(payload["metrics"])


def test_benchmark_summary_api_labels_results_as_draft(client) -> None:
    response = client.get("/api/v1/knowledge/benchmark-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["benchmark_status"] == "draft"
    assert payload["human_review_required"] is True
    assert payload["runs"]["baseline_lexical_v1"]["available"] is True
    assert payload["runs"]["local_lexical_v2"]["available"] is True
