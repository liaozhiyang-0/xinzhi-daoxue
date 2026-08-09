"""Audit a serialized Agent Runtime checkpoint trace without invoking tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.runtime import audit_checkpoint_trace  # noqa: E402


def main(path: str) -> int:
    payload: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    records = (
        payload.get("checkpoints", payload) if isinstance(payload, dict) else payload
    )
    audit = audit_checkpoint_trace(records)
    print(audit.model_dump_json(indent=2))
    return 0 if audit.valid else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/audit_runtime_trace.py TRACE.json")
    raise SystemExit(main(sys.argv[1]))
