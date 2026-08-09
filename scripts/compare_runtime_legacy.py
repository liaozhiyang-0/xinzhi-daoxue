"""Compare serialized Legacy and Runtime results without executing anything."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.runtime import (  # noqa: E402
    RuntimeTraceAudit,
    audit_checkpoint_trace,
    build_runtime_legacy_diff,
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(
    legacy_path: str,
    runtime_path: str,
    trace_path: str | None = None,
    *,
    require_canary_eligible: bool = False,
) -> int:
    legacy = _load(Path(legacy_path))
    runtime = _load(Path(runtime_path))
    if not isinstance(legacy, dict) or not isinstance(runtime, dict):
        raise SystemExit("legacy and runtime payloads must be JSON objects")

    trace_audit: RuntimeTraceAudit | None = None
    if trace_path:
        trace_payload = _load(Path(trace_path))
        records = (
            trace_payload.get("checkpoints", trace_payload)
            if isinstance(trace_payload, dict)
            else trace_payload
        )
        if not isinstance(records, list):
            raise SystemExit("trace checkpoints must be a JSON array")
        trace_audit = audit_checkpoint_trace(records)

    report = build_runtime_legacy_diff(
        legacy,
        runtime,
        runtime_trace=trace_audit,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if not require_canary_eligible or report.canary_eligible else 1


if __name__ == "__main__":
    if len(sys.argv) not in {3, 4, 5}:
        raise SystemExit(
            "usage: python scripts/compare_runtime_legacy.py "
            "LEGACY.json RUNTIME.json [RUNTIME_TRACE.json] "
            "[--require-canary-eligible]"
        )
    require_canary_eligible = "--require-canary-eligible" in sys.argv[3:]
    positional = [item for item in sys.argv[3:] if item != "--require-canary-eligible"]
    if len(positional) > 1:
        raise SystemExit("only one optional runtime trace path is supported")
    raise SystemExit(
        main(
            sys.argv[1],
            sys.argv[2],
            positional[0] if positional else None,
            require_canary_eligible=require_canary_eligible,
        )
    )
