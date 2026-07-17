from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    comparison = {
        metric: {
            "baseline": baseline["metrics"][metric],
            "candidate": candidate["metrics"][metric],
            "delta": round(
                candidate["metrics"][metric] - baseline["metrics"][metric], 6
            ),
        }
        for metric in baseline["metrics"]
    }
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
