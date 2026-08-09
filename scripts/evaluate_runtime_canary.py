"""Evaluate serialized Legacy/Runtime pairs without invoking a Provider."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.runtime import (  # noqa: E402
    RuntimeCanarySuite,
    evaluate_runtime_canary_suite,
)


def main(
    path: str,
    *,
    require_canary_eligible: bool = False,
    require_release_eligible: bool = False,
) -> int:
    """Evaluate a suite and optionally enforce the release gate.

    ``require_canary_eligible`` is retained as a compatibility parameter for
    existing callers. Historically this CLI used that name for the stricter
    ``release_eligible`` decision, so the command-line alias keeps that
    behavior while ``require_release_eligible`` makes the intent explicit.
    """

    if require_canary_eligible and require_release_eligible:
        raise ValueError(
            "choose only one of require_canary_eligible and "
            "require_release_eligible"
        )
    payload: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    suite = RuntimeCanarySuite.model_validate(payload)
    report = evaluate_runtime_canary_suite(suite)
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return (
        0
        if not (require_canary_eligible or require_release_eligible)
        or report.release_eligible
        else 1
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate an offline Runtime canary suite without a Provider."
    )
    parser.add_argument("suite", help="Serialized Runtime canary suite JSON")
    gate = parser.add_mutually_exclusive_group()
    gate.add_argument(
        "--require-release-eligible",
        action="store_true",
        help="exit 1 unless the authorized release gate passes",
    )
    gate.add_argument(
        "--require-canary-eligible",
        action="store_true",
        help=(
            "legacy compatibility alias for --require-release-eligible; "
            "checks release_eligible"
        ),
    )
    return parser


if __name__ == "__main__":
    arguments = _parser().parse_args()
    raise SystemExit(
        main(
            arguments.suite,
            require_canary_eligible=(
                arguments.require_canary_eligible
            ),
            require_release_eligible=arguments.require_release_eligible,
        )
    )
