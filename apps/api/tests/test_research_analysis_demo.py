from __future__ import annotations

from pathlib import Path

from scripts.research_analysis_demo import run_demo


def test_research_analysis_demo_runs_all_four_local_mvp_paths(
    tmp_path: Path,
) -> None:
    manifest = run_demo(tmp_path / "demo")

    assert manifest["network_calls"] == 0
    assert manifest["external_evidence_used"] is False
    assert len(manifest["records"]) == 4
    assert {record["status"] for record in manifest["records"]} == {"executed"}
    assert all(record["human_review_required"] for record in manifest["records"])
    assert (tmp_path / "demo" / "demo_manifest.json").is_file()
