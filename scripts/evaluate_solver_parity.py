"""Evaluate paired Legacy/Runtime solver outputs offline."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.runtime.solver_parity import (  # noqa: E402
    SolverParitySuite,
    evaluate_solver_parity_suite,
)


def main(path: str, *, require_canary_eligible: bool = False) -> int:
    payload: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    report = evaluate_solver_parity_suite(SolverParitySuite.model_validate(payload))
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if not require_canary_eligible or report.canary_eligible else 1


if __name__ == "__main__":
    if len(sys.argv) not in {2, 3} or (
        len(sys.argv) == 3 and sys.argv[2] != "--require-canary-eligible"
    ):
        raise SystemExit(
            "usage: python scripts/evaluate_solver_parity.py "
            "PAIRED_SUITE.json [--require-canary-eligible]"
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
