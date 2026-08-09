"""Evaluate a serialized Agent Runtime trace against a versioned case."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.runtime import (  # noqa: E402
    AgentRun,
    RuntimeCheckpointRecord,
    RuntimeEvaluationCase,
    audit_checkpoint_trace,
    evaluate_runtime_run,
)


def main(trace_path: str, case_path: str) -> int:
    trace_payload: Any = json.loads(
        Path(trace_path).read_text(encoding="utf-8")
    )
    case_payload: Any = json.loads(Path(case_path).read_text(encoding="utf-8"))
    records_payload = (
        trace_payload.get("checkpoints", trace_payload)
        if isinstance(trace_payload, dict)
        else trace_payload
    )
    case = RuntimeEvaluationCase.model_validate(case_payload)
    audit = audit_checkpoint_trace(records_payload)
    output: dict[str, Any] = {
        "audit": audit.model_dump(mode="json"),
        "evaluation": None,
    }
    if not audit.valid:
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1

    records = [
        RuntimeCheckpointRecord.model_validate(item) for item in records_payload
    ]
    final_record = max(records, key=lambda item: item.sequence)
    run = AgentRun.model_validate(final_record.state_data)
    evaluation = evaluate_runtime_run(
        run,
        case,
        checkpoint_count=audit.checkpoint_count,
    )
    output["evaluation"] = evaluation.model_dump(mode="json")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if evaluation.passed else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python scripts/evaluate_runtime_trace.py TRACE.json CASE.json"
        )
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
