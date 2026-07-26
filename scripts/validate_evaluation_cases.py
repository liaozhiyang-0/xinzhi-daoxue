from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.evaluation.loader import EvaluationCaseLoader  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate evaluation cases and provenance"
    )
    parser.add_argument("--root", type=Path, default=ROOT / "evaluation" / "cases")
    args = parser.parse_args()
    try:
        cases = EvaluationCaseLoader(args.root).load_all()
    except (OSError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    sources = Counter(item.provenance.source_type for item in cases)
    judges = Counter(item.judge_type for item in cases)
    payload = {
        "valid": True,
        "case_count": len(cases),
        "courses": sorted({item.course for item in cases}),
        "source_types": dict(sources),
        "judge_types": dict(judges),
        "private_publishable_violations": [
            item.case_id
            for item in cases
            if item.provenance.source_type == "private" and item.provenance.publishable
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return int(bool(payload["private_publishable_violations"]))


if __name__ == "__main__":
    raise SystemExit(main())
