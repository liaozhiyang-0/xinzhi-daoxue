from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402
from app.database.session import create_engine_and_session  # noqa: E402
from app.services.evaluation_attachment_maintenance import (  # noqa: E402
    cleanup_stale_evaluation_attachments,
    inspect_evaluation_attachment_residue,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect controlled evaluation attachment residue; cleanup requires "
            "an explicit --execute."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="delete one bounded batch of eligible candidates",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        choices=range(1, 1001),
        metavar="N",
        help="maximum files to remove when --execute is supplied (default: 100)",
    )
    return parser.parse_args()


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


async def run(*, execute: bool, limit: int) -> dict[str, object]:
    settings = Settings()
    engine, session_factory = create_engine_and_session(settings.active_database_url)
    try:
        async with session_factory() as db:
            report = await inspect_evaluation_attachment_residue(db, settings)
            removed = 0
            if execute:
                removed = await cleanup_stale_evaluation_attachments(
                    db, settings, limit=limit
                )
                await db.commit()
            return {
                "mode": "execute" if execute else "dry_run",
                "report": report.__dict__,
                "removed_count": removed,
            }
    finally:
        await engine.dispose()


if __name__ == "__main__":
    args = parse_args()
    print(
        json.dumps(
            asyncio.run(run(execute=args.execute, limit=args.limit)),
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        )
    )
