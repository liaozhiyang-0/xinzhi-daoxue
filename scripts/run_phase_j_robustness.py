"""Run bounded provider-free concurrency checks for Phase J.

The script exercises the already-running local API with a fixed, read-only
question. It deliberately treats review/input-wait states as terminal for a
load probe: those are user-visible workflow outcomes, not worker hangs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "evaluation" / "reports" / "phase_j" / "concurrency.json"
TERMINAL_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "waiting_review",
    "waiting_user",
    "waiting_input",
}
QUESTION = "为什么服务器要回复 SYN+ACK？"


def _parse_levels(value: str) -> tuple[int, ...]:
    levels = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not levels or any(level < 1 or level > 20 for level in levels):
        raise argparse.ArgumentTypeError("levels must be bounded integers in [1, 20]")
    return levels


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction)))
    return round(ordered[index], 3)


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _poll_task(
    client: httpx.AsyncClient, task_id: str, timeout_seconds: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = await client.get(f"/api/v1/tasks/{task_id}")
        response.raise_for_status()
        task = response.json()
        if task.get("status") in TERMINAL_STATUSES:
            return task
        await asyncio.sleep(0.25)
    return {"id": task_id, "status": "probe_timeout"}


async def _one(
    client: httpx.AsyncClient, level: int, ordinal: int, timeout_seconds: float
) -> dict[str, Any]:
    started = time.monotonic()
    response = await client.post(
        "/api/v1/chat",
        json={
            "message": QUESTION,
            "user_id": f"phase-j-concurrency-{level}",
            "metadata": {"source": "phase_j_robustness", "level": level},
        },
    )
    response.raise_for_status()
    submission = response.json()
    task = await _poll_task(client, str(submission["task_id"]), timeout_seconds)
    created = _timestamp(task.get("created_at"))
    started_at = _timestamp(task.get("started_at"))
    queue_delay_ms = (
        round((started_at - created).total_seconds() * 1000, 3)
        if created is not None and started_at is not None
        else None
    )
    return {
        "ordinal": ordinal,
        "task_id": task.get("id"),
        "status": task.get("status"),
        "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        "queue_delay_ms": queue_delay_ms,
        "failure_category": task.get("failure_category"),
    }


async def _run_level(
    client: httpx.AsyncClient, level: int, timeout_seconds: float
) -> dict[str, Any]:
    started = time.monotonic()
    results = await asyncio.gather(
        *(_one(client, level, ordinal, timeout_seconds) for ordinal in range(level)),
        return_exceptions=True,
    )
    records: list[dict[str, Any]] = []
    for ordinal, result in enumerate(results):
        if isinstance(result, BaseException):
            records.append(
                {
                    "ordinal": ordinal,
                    "status": "request_error",
                    "error_type": type(result).__name__,
                    "error": str(result),
                }
            )
        else:
            records.append(result)
    latencies = [
        float(item["elapsed_ms"])
        for item in records
        if isinstance(item.get("elapsed_ms"), (int, float))
    ]
    queue_delays = [
        float(item["queue_delay_ms"])
        for item in records
        if isinstance(item.get("queue_delay_ms"), (int, float))
    ]
    failures = [
        item
        for item in records
        if item.get("status") not in {"completed", "waiting_review", "waiting_user"}
    ]
    return {
        "concurrency": level,
        "requested": level,
        "observed": len(records),
        "failures": len(failures),
        "failure_rate": round(len(failures) / level, 4),
        "p50_ms": _percentile(latencies, 0.50),
        "p95_ms": _percentile(latencies, 0.95),
        "p99_ms": _percentile(latencies, 0.99),
        "queue_delay_p50_ms": _percentile(queue_delays, 0.50),
        "queue_delay_p95_ms": _percentile(queue_delays, 0.95),
        "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        "status_counts": {
            status: sum(item.get("status") == status for item in records)
            for status in sorted({str(item.get("status")) for item in records})
        },
        "records": records,
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    timeout = httpx.Timeout(10.0, connect=5.0)
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=20)
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        timeout=timeout,
        limits=limits,
        trust_env=False,
    ) as client:
        levels = [
            await _run_level(client, level, args.timeout_seconds)
            for level in args.levels
        ]
    return {
        "schema_version": "phase_j_concurrency.v1",
        "synthetic": True,
        "provider_free": True,
        "question": QUESTION,
        "levels": levels,
        "resource_sampling": {
            "cpu_percent": None,
            "memory_mb": None,
            "reason": (
                "psutil is not installed; no process-wide resource sample claimed"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--levels", type=_parse_levels, default=(1, 5, 10, 20))
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(level["failures"] == 0 for level in report["levels"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
