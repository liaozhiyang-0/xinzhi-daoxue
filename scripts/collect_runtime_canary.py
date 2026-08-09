"""Package an authorized Legacy/Runtime pair into a release-gate artifact.

This command is intentionally offline. It only reads already-captured JSON
payloads and Runtime checkpoints; it never invokes a Provider, model, or tool.
The authorization reference is an operator attestation and must point to the
change/evaluation record that approved use of the pair.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.runtime import (  # noqa: E402
    RuntimeCanaryEvidence,
    RuntimeCanaryPair,
    RuntimeCanarySuite,
    audit_checkpoint_trace,
    evaluate_runtime_canary_suite,
)


def _read_object(path: Path, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _read_checkpoints(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = (
        payload.get("checkpoints", payload)
        if isinstance(payload, dict)
        else payload
    )
    if not isinstance(records, list) or not all(
        isinstance(item, dict) for item in records
    ):
        raise ValueError("runtime checkpoints must be a JSON array of objects")
    return records


def build_suite(
    *,
    agent_id: str,
    agent_version: str,
    runtime_plan_version: str,
    suite_id: str,
    case_id: str,
    authorization_ref: str,
    captured_at: datetime,
    legacy_payload: dict[str, Any],
    runtime_payload: dict[str, Any],
    runtime_checkpoints: list[dict[str, Any]],
) -> RuntimeCanarySuite:
    """Build and validate one authorized paired artifact."""

    if captured_at.tzinfo is None:
        raise ValueError("captured_at must include a timezone")
    suite = RuntimeCanarySuite(
        suite_id=suite_id,
        evidence=RuntimeCanaryEvidence(
            kind="authorized_paired",
            agent_id=agent_id,
            agent_version=agent_version,
            runtime_plan_version=runtime_plan_version,
            authorization_ref=authorization_ref,
            captured_at=captured_at,
            redaction_status="redacted",
        ),
        pairs=[
            RuntimeCanaryPair(
                case_id=case_id,
                legacy_payload=legacy_payload,
                runtime_payload=runtime_payload,
                runtime_checkpoints=runtime_checkpoints,
            )
        ],
    )
    report = evaluate_runtime_canary_suite(suite)
    if not report.release_eligible:
        raise ValueError(
            "paired artifact is not release eligible: "
            + ",".join(
                report.failed_checks
                + report.release_failed_checks
                or ["runtime_trace_or_parity_failed"]
            )
        )
    return suite


def main(args: argparse.Namespace) -> int:
    legacy = _read_object(Path(args.legacy), "legacy payload")
    runtime = _read_object(Path(args.runtime), "runtime payload")
    checkpoints = _read_checkpoints(Path(args.checkpoints))
    trace = audit_checkpoint_trace(checkpoints)
    if not trace.valid:
        raise ValueError(
            "runtime checkpoint trace is invalid: " + ",".join(trace.errors)
        )
    suite = build_suite(
        agent_id=args.agent_id,
        agent_version=args.agent_version,
        runtime_plan_version=args.runtime_plan_version,
        suite_id=args.suite_id,
        case_id=args.case_id,
        authorization_ref=args.authorization_ref,
        captured_at=datetime.fromisoformat(args.captured_at),
        legacy_payload=legacy,
        runtime_payload=runtime,
        runtime_checkpoints=checkpoints,
    )
    output = Path(args.output)
    output.write_text(
        json.dumps(suite.model_dump(mode="json"), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    report = evaluate_runtime_canary_suite(suite)
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Package an authorized offline Runtime canary pair."
    )
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--agent-version", required=True)
    parser.add_argument("--runtime-plan-version", required=True)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--authorization-ref", required=True)
    parser.add_argument("--captured-at", required=True, help="ISO-8601 timestamp")
    parser.add_argument("--legacy", required=True, help="Legacy result JSON")
    parser.add_argument("--runtime", required=True, help="Runtime result JSON")
    parser.add_argument("--checkpoints", required=True, help="Runtime trace JSON")
    parser.add_argument("--output", required=True, help="Output suite JSON")
    return parser


if __name__ == "__main__":
    arguments = _parser().parse_args()
    try:
        raise SystemExit(main(arguments))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: {exc}") from exc
