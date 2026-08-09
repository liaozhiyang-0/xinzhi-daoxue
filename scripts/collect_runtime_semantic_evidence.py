"""Collect a deterministic semantic evidence sidecar from a paired suite.

This command is intentionally provider-free.  It reads an already captured
authorized structural suite, the corresponding inputs, and redacted semantic
judgements, then derives payload hashes through ``RuntimeSemanticEvidence``.
It never stores the original input payloads in the sidecar.

Explicit synthetic suites remain usable for provider-free contract fixtures,
but their sidecars cannot authorize a release.
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

from app.runtime import RuntimeCanarySuite  # noqa: E402
from app.runtime.semantic_evidence import (  # noqa: E402
    RuntimeSemanticDimensions,
    RuntimeSemanticEvidence,
    payload_sha256,
)

JUDGEMENT_FIELDS = frozenset(
    {
        "dimensions",
        "decision",
        "judge_type",
        "rubric_version",
        "reviewer_ref",
        "reviewed_at",
        "redaction_status",
        "authorization_ref",
    }
)


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _read_suite(path: Path) -> RuntimeCanarySuite:
    payload = json.loads(path.read_text(encoding="utf-8"))
    suite = RuntimeCanarySuite.model_validate(payload)
    evidence = suite.evidence
    if evidence.kind == "authorized_paired" and not evidence.release_ready:
        raise ValueError(
            "structural suite is not authorized or lacks agent/version/plan"
        )
    return suite


def _require_matching_case_ids(
    expected: set[str],
    actual: set[str],
    *,
    label: str,
) -> None:
    if expected == actual:
        return
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    raise ValueError(
        f"{label} case_id mismatch: "
        f"missing={missing!r}, extra={extra!r}"
    )


def _parse_reviewed_at(value: Any, *, case_id: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"reviewed_at for {case_id} must be an ISO-8601 string")
    try:
        reviewed_at = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid reviewed_at for {case_id}") from exc
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise ValueError(f"reviewed_at for {case_id} must include a timezone")
    return reviewed_at


def _build_evidence(
    *,
    suite: RuntimeCanarySuite,
    pair_case_id: str,
    input_payload: Any,
    judgement: Any,
    legacy_payload: dict[str, Any],
    runtime_payload: dict[str, Any],
) -> RuntimeSemanticEvidence:
    if not isinstance(judgement, dict):
        raise ValueError(f"judgement for {pair_case_id} must be a JSON object")
    missing = sorted(JUDGEMENT_FIELDS - set(judgement))
    extra = sorted(set(judgement) - JUDGEMENT_FIELDS)
    if missing or extra:
        raise ValueError(
            f"judgement fields for {pair_case_id} invalid: "
            f"missing={missing!r}, extra={extra!r}"
        )
    if judgement["redaction_status"] != "redacted":
        raise ValueError(f"judgement for {pair_case_id} must be redacted")

    dimensions = RuntimeSemanticDimensions.model_validate(judgement["dimensions"])
    reviewed_at = _parse_reviewed_at(
        judgement["reviewed_at"],
        case_id=pair_case_id,
    )
    evidence = suite.evidence
    return RuntimeSemanticEvidence.from_payloads(
        input_payload=input_payload,
        legacy_payload=legacy_payload,
        runtime_payload=runtime_payload,
        suite_id=suite.suite_id,
        case_id=pair_case_id,
        agent_id=evidence.agent_id,
        agent_version=evidence.agent_version,
        runtime_plan_version=evidence.runtime_plan_version,
        dimensions=dimensions,
        decision=judgement["decision"],
        judge_type=judgement["judge_type"],
        rubric_version=judgement["rubric_version"],
        reviewer_ref=judgement["reviewer_ref"],
        reviewed_at=reviewed_at,
        redaction_status="redacted",
        authorization_ref=judgement["authorization_ref"],
    )


def collect_sidecar(
    *,
    suite: RuntimeCanarySuite,
    inputs: dict[str, Any],
    judgements: dict[str, Any],
) -> list[RuntimeSemanticEvidence]:
    """Build one semantic evidence record for every structural pair."""

    pair_case_ids = [pair.case_id for pair in suite.pairs]
    if len(pair_case_ids) != len(set(pair_case_ids)):
        raise ValueError("structural suite contains duplicate case_id values")
    pair_case_id_set = set(pair_case_ids)
    _require_matching_case_ids(pair_case_id_set, set(inputs), label="inputs")
    _require_matching_case_ids(
        pair_case_id_set,
        set(judgements),
        label="judgements",
    )

    # Validate the structural binding before constructing any sidecar record.
    # Legacy synthetic suites may predate input hashes; authorized paired
    # suites must bind every case to the supplied, private input payload.
    for pair in suite.pairs:
        input_hash = pair.input_sha256
        if input_hash is None:
            if suite.evidence.kind == "authorized_paired":
                raise ValueError(
                    f"structural suite pair {pair.case_id} is missing "
                    "input_sha256"
                )
            continue
        expected_input_hash = payload_sha256(inputs[pair.case_id])
        if input_hash != expected_input_hash:
            raise ValueError(
                f"structural suite pair {pair.case_id} input_sha256 mismatch: "
                f"expected={expected_input_hash}:actual={input_hash}"
            )

    evidence: list[RuntimeSemanticEvidence] = []
    for pair in suite.pairs:
        evidence.append(
            _build_evidence(
                suite=suite,
                pair_case_id=pair.case_id,
                input_payload=inputs[pair.case_id],
                judgement=judgements[pair.case_id],
                legacy_payload=pair.legacy_payload,
                runtime_payload=pair.runtime_payload,
            )
        )
    return evidence


def main(args: argparse.Namespace) -> int:
    suite = _read_suite(Path(args.suite))
    inputs = _read_json_object(Path(args.inputs), "inputs")
    judgements = _read_json_object(Path(args.judgements), "judgements")
    evidence = collect_sidecar(
        suite=suite,
        inputs=inputs,
        judgements=judgements,
    )

    output = Path(args.output)
    output.write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in evidence],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"case_count": len(evidence)}, ensure_ascii=False))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect a redacted, provider-free Runtime semantic sidecar."
    )
    parser.add_argument("--suite", required=True, help="Structural suite JSON")
    parser.add_argument("--inputs", required=True, help="Case input JSON")
    parser.add_argument("--judgements", required=True, help="Case judgement JSON")
    parser.add_argument("--output", required=True, help="Sidecar output JSON")
    return parser


if __name__ == "__main__":
    try:
        raise SystemExit(main(_parser().parse_args()))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
