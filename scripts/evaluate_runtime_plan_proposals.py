"""Evaluate adaptive Runtime plan proposals without invoking a Provider."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.runtime import (  # noqa: E402
    RuntimePlanProposalSuite,
    evaluate_runtime_plan_proposal_suite,
)


def main(suite_path: str, *, require_canary_eligible: bool = False) -> int:
    payload: Any = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    suite = RuntimePlanProposalSuite.model_validate(payload)
    report = evaluate_runtime_plan_proposal_suite(suite)
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    if not report.canary_eligible:
        return 1 if require_canary_eligible else 0
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in {2, 3}:
        raise SystemExit(
            "usage: python scripts/evaluate_runtime_plan_proposals.py "
            "SUITE.json [--require-canary-eligible]"
        )
    raise SystemExit(
        main(
            sys.argv[1],
            require_canary_eligible=(
                len(sys.argv) == 3
                and sys.argv[2] == "--require-canary-eligible"
            ),
        )
    )
