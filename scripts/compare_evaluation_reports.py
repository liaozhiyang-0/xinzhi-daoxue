from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def result_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("results", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two evaluation JSON reports")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    baseline, candidate = load(args.baseline), load(args.candidate)
    old = {str(item["case_id"]): item for item in result_rows(baseline)}
    new = {str(item["case_id"]): item for item in result_rows(candidate)}
    shared = sorted(set(old) & set(new))
    comparison = {
        "baseline_mode": baseline.get("mode"),
        "candidate_mode": candidate.get("mode"),
        "shared_cases": len(shared),
        "score_delta": {
            case_id: round(
                float(new[case_id]["total_score"]) - float(old[case_id]["total_score"]),
                2,
            )
            for case_id in shared
        },
        "new_failures": [
            case_id
            for case_id in shared
            if old[case_id]["status"] == "passed" and new[case_id]["status"] != "passed"
        ],
    }
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return int(bool(comparison["new_failures"]))


if __name__ == "__main__":
    raise SystemExit(main())
