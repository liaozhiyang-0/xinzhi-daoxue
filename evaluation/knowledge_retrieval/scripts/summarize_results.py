from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.result.read_text(encoding="utf-8"))
    run_summary = (
        f"run={payload['run_id']} cases={payload['case_count']} "
        f"status={payload['case_status']}"
    )
    print(run_summary)
    for name, value in payload["metrics"].items():
        print(f"{name}: {value}")
    failures = [
        row["case_id"] for row in payload["cases"] if row["relevant_rank"] is None
    ]
    print("unrecalled@5: " + (", ".join(failures) if failures else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
