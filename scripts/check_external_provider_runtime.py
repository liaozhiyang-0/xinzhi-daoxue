"""Run a low-intensity live smoke check for configured retrieval providers.

The check calls each configured provider sequentially with a bounded result limit.
It is intentionally not a load test and must not be used for benchmarking quotas.
"""

# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import get_settings  # type: ignore[import-untyped]
from app.providers.retrieval.factory import (  # type: ignore[import-untyped]
    create_external_search_service,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="柔性电子器件")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument(
        "--providers",
        nargs="*",
        help="Optional provider names; defaults to all providers enabled in .env.",
    )
    return parser.parse_args()


async def run_check(
    query: str,
    limit: int,
    provider_names: Sequence[str] | None,
) -> dict[str, object]:
    service = create_external_search_service(get_settings())
    initial_health = service.health()
    configured = initial_health.get("providers", [])
    configured_items = configured if isinstance(configured, list) else []
    configured_names = tuple(
        str(item["name"])
        for item in configured_items
        if isinstance(item, dict) and item.get("name")
    )
    selected_names = tuple(provider_names) if provider_names else configured_names
    results: list[dict[str, object]] = []

    for provider_name in selected_names:
        started = time.perf_counter()
        try:
            retrieval = await service.search(
                query,
                limit=limit,
                provider_names=(provider_name,),
            )
            provider_status = retrieval.provider_status.get(
                provider_name, retrieval.status
            )
            results.append(
                {
                    "provider": provider_name,
                    "status": provider_status,
                    "retrieval_status": retrieval.status,
                    "items": sum(
                        1 for item in retrieval.items if item.provider == provider_name
                    ),
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                }
            )
        except Exception as exc:  # noqa: BLE001 - smoke check reports provider failure
            results.append(
                {
                    "provider": provider_name,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:200],
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                }
            )

    health = service.health()
    await service.close()
    return {
        "query": query,
        "limit": limit,
        "results": results,
        "health": health,
    }


def main() -> None:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    payload = asyncio.run(run_check(args.query, args.limit, args.providers))
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
