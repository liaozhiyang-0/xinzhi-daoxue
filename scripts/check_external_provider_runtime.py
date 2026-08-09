"""Run a low-intensity live smoke check for configured retrieval providers.

The check calls each configured provider sequentially with a bounded result limit.
It is intentionally not a load test and must not be used for benchmarking quotas.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections.abc import Sequence

from app.core.config import get_settings
from app.providers.retrieval.factory import create_external_search_service


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
    selected = set(provider_names or ())
    results: list[dict[str, object]] = []

    for provider in service.providers:
        if selected and provider.provider_name not in selected:
            continue
        started = time.perf_counter()
        try:
            items = await provider.search(query, limit=limit)
            results.append(
                {
                    "provider": provider.provider_name,
                    "status": "completed",
                    "items": len(items),
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                }
            )
        except Exception as exc:  # noqa: BLE001 - smoke check reports provider failure
            results.append(
                {
                    "provider": provider.provider_name,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:200],
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                }
            )

    return {
        "query": query,
        "limit": limit,
        "results": results,
        "health": service.health(),
    }


def main() -> None:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    payload = asyncio.run(run_check(args.query, args.limit, args.providers))
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
