from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two evaluation JSON reports")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    baseline, candidate = load(args.baseline), load(args.candidate)
    old = {item["case_id"]: item for item in baseline.get("results", [])}
    new = {item["case_id"]: item for item in candidate.get("results", [])}
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
