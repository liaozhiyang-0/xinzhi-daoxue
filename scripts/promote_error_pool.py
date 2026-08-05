from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.error_pool_promotion import (  # noqa: E402
    build_error_pool_promotion_plan,
    execute_error_pool_promotion,
    rollback_error_pool_promotion,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or explicitly apply CT/AE reviewed error-template promotions. "
            "The default mode is read-only dry-run."
        )
    )
    parser.add_argument("--course", choices=("CT", "AE"), required=True)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="project root (default: repository root)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="apply a ready course-level promotion; never implied by dry-run",
    )
    parser.add_argument(
        "--source-fingerprint",
        default="",
        help="optional fingerprint returned by the dry-run plan",
    )
    parser.add_argument(
        "--rollback",
        type=Path,
        help="restore a backup produced by --execute",
    )
    parser.add_argument(
        "--expected-current-fingerprint",
        default="",
        help="optional runtime fingerprint required for rollback",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if args.rollback and args.execute:
        raise SystemExit("--rollback and --execute are mutually exclusive")
    if args.rollback:
        report = rollback_error_pool_promotion(
            root,
            args.course,
            args.rollback,
            expected_current_fingerprint=args.expected_current_fingerprint,
        )
    elif args.execute:
        report = execute_error_pool_promotion(
            root,
            args.course,
            expected_source_fingerprint=args.source_fingerprint,
        )
    else:
        report = build_error_pool_promotion_plan(root, args.course)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") not in {"blocked", "error"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
