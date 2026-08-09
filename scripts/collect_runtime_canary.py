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

_MANIFEST_SCHEMA_VERSION = "runtime_canary_manifest.v1"
_MANIFEST_KEYS = {
    "schema_version",
    "agent_id",
    "agent_version",
    "runtime_plan_version",
    "suite_id",
    "authorization_ref",
    "captured_at",
    "cases",
}
_CASE_KEYS = {"case_id", "legacy", "runtime", "checkpoints"}


def _read_object(path: Path, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _read_checkpoints(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = (
        payload.get("checkpoints", payload) if isinstance(payload, dict) else payload
    )
    if not isinstance(records, list) or not all(
        isinstance(item, dict) for item in records
    ):
        raise ValueError("runtime checkpoints must be a JSON array of objects")
    return records


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _validate_keys(payload: dict[str, Any], *, allowed: set[str], label: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"{label} contains unsupported fields: {','.join(unknown)}")


def _resolve_manifest_input(manifest_root: Path, raw_path: Any, label: str) -> Path:
    """Resolve a manifest input and reject traversal, missing files, and symlinks out.

    ``Path.resolve(strict=True)`` makes the containment check apply to the final
    target, not merely to the textual path.  This keeps a symlinked input from
    escaping the directory that owns the manifest.
    """

    relative_path = _require_string(raw_path, label)
    try:
        resolved = (manifest_root / relative_path).resolve(strict=True)
        resolved.relative_to(manifest_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(
            f"{label} is missing or outside the manifest directory"
        ) from exc
    if not resolved.is_file():
        raise ValueError(f"{label} must reference a regular file")
    return resolved


def _build_validated_suite(
    *,
    agent_id: str,
    agent_version: str,
    runtime_plan_version: str,
    suite_id: str,
    authorization_ref: str,
    captured_at: datetime,
    pairs: list[RuntimeCanaryPair],
) -> RuntimeCanarySuite:
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
        pairs=pairs,
    )
    report = evaluate_runtime_canary_suite(suite)
    if not report.release_eligible:
        raise ValueError(
            "paired artifact is not release eligible: "
            + ",".join(
                report.failed_checks + report.release_failed_checks
                or ["runtime_trace_or_parity_failed"]
            )
        )
    return suite


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

    return _build_validated_suite(
        agent_id=agent_id,
        agent_version=agent_version,
        runtime_plan_version=runtime_plan_version,
        suite_id=suite_id,
        authorization_ref=authorization_ref,
        captured_at=captured_at,
        pairs=[
            RuntimeCanaryPair(
                case_id=case_id,
                legacy_payload=legacy_payload,
                runtime_payload=runtime_payload,
                runtime_checkpoints=runtime_checkpoints,
            )
        ],
    )


def build_suite_from_manifest(manifest_path: Path) -> RuntimeCanarySuite:
    """Build one authorized suite from a provider-free multi-case manifest.

    The manifest is the trust boundary for file access: every case input must
    resolve beneath the manifest directory, and each case is audited before it
    can enter the suite.  The manifest itself is never copied into the output.
    """

    try:
        resolved_manifest = manifest_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("manifest is missing or cannot be resolved") from exc
    if not resolved_manifest.is_file():
        raise ValueError("manifest must reference a regular file")
    manifest = _read_object(resolved_manifest, "manifest")
    _validate_keys(manifest, allowed=_MANIFEST_KEYS, label="manifest")
    if manifest.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"manifest schema_version must be {_MANIFEST_SCHEMA_VERSION}")

    agent_id = _require_string(manifest.get("agent_id"), "manifest agent_id")
    agent_version = _require_string(
        manifest.get("agent_version"), "manifest agent_version"
    )
    runtime_plan_version = _require_string(
        manifest.get("runtime_plan_version"),
        "manifest runtime_plan_version",
    )
    suite_id = _require_string(manifest.get("suite_id"), "manifest suite_id")
    authorization_ref = _require_string(
        manifest.get("authorization_ref"),
        "manifest authorization_ref",
    )
    captured_at_raw = _require_string(
        manifest.get("captured_at"), "manifest captured_at"
    )
    try:
        captured_at = datetime.fromisoformat(captured_at_raw)
    except ValueError as exc:
        raise ValueError(
            "manifest captured_at must be a valid ISO-8601 timestamp"
        ) from exc

    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest cases must be a non-empty JSON array")

    pairs: list[RuntimeCanaryPair] = []
    case_ids: set[str] = set()
    for index, raw_case in enumerate(cases):
        label = f"manifest cases[{index}]"
        if not isinstance(raw_case, dict):
            raise ValueError(f"{label} must be a JSON object")
        _validate_keys(raw_case, allowed=_CASE_KEYS, label=label)
        case_id = _require_string(raw_case.get("case_id"), f"{label}.case_id")
        if case_id in case_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        case_ids.add(case_id)

        legacy_path = _resolve_manifest_input(
            resolved_manifest.parent, raw_case.get("legacy"), f"{label}.legacy"
        )
        runtime_path = _resolve_manifest_input(
            resolved_manifest.parent, raw_case.get("runtime"), f"{label}.runtime"
        )
        checkpoints_path = _resolve_manifest_input(
            resolved_manifest.parent,
            raw_case.get("checkpoints"),
            f"{label}.checkpoints",
        )
        legacy_payload = _read_object(legacy_path, f"{label}.legacy payload")
        runtime_payload = _read_object(runtime_path, f"{label}.runtime payload")
        checkpoints = _read_checkpoints(checkpoints_path)
        trace = audit_checkpoint_trace(checkpoints)
        if not trace.valid:
            raise ValueError(
                f"{case_id}: runtime checkpoint trace is invalid: "
                + ",".join(trace.errors)
            )
        pairs.append(
            RuntimeCanaryPair(
                case_id=case_id,
                legacy_payload=legacy_payload,
                runtime_payload=runtime_payload,
                runtime_checkpoints=checkpoints,
            )
        )

    return _build_validated_suite(
        agent_id=agent_id,
        agent_version=agent_version,
        runtime_plan_version=runtime_plan_version,
        suite_id=suite_id,
        authorization_ref=authorization_ref,
        captured_at=captured_at,
        pairs=pairs,
    )


def main(args: argparse.Namespace) -> int:
    if args.manifest:
        if any(
            getattr(args, name, None)
            for name in (
                "agent_id",
                "agent_version",
                "runtime_plan_version",
                "suite_id",
                "case_id",
                "authorization_ref",
                "captured_at",
                "legacy",
                "runtime",
                "checkpoints",
            )
        ):
            raise ValueError("--manifest cannot be combined with single-case options")
        suite = build_suite_from_manifest(Path(args.manifest))
    else:
        required = (
            "agent_id",
            "agent_version",
            "runtime_plan_version",
            "suite_id",
            "case_id",
            "authorization_ref",
            "captured_at",
            "legacy",
            "runtime",
            "checkpoints",
        )
        missing = [name for name in required if not getattr(args, name, None)]
        if missing:
            raise ValueError("single-case options missing: " + ",".join(missing))
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
        json.dumps(suite.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = evaluate_runtime_canary_suite(suite)
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Package an authorized offline Runtime canary pair."
    )
    parser.add_argument("--manifest", help="v1 multi-case JSON manifest")
    parser.add_argument("--agent-id")
    parser.add_argument("--agent-version")
    parser.add_argument("--runtime-plan-version")
    parser.add_argument("--suite-id")
    parser.add_argument("--case-id")
    parser.add_argument("--authorization-ref")
    parser.add_argument("--captured-at", help="ISO-8601 timestamp")
    parser.add_argument("--legacy", help="Legacy result JSON")
    parser.add_argument("--runtime", help="Runtime result JSON")
    parser.add_argument("--checkpoints", help="Runtime trace JSON")
    parser.add_argument("--output", required=True, help="Output suite JSON")
    return parser


if __name__ == "__main__":
    arguments = _parser().parse_args()
    try:
        raise SystemExit(main(arguments))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: {exc}") from exc
