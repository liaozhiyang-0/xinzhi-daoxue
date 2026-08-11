"""Bind an independent semantic judgement to a LearningLoop pair.

This command reads a redacted development pair package plus private operator
inputs/outputs and emits hashes and judgement metadata only.  It never copies
the supplied payloads into the sidecar and never turns development evidence
into release evidence; the generic Runtime release preflight still requires
an authorized structural suite and a separate release authorization.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.runtime.semantic_evidence import (  # noqa: E402
    RuntimeSemanticDimensions,
    RuntimeSemanticEvidence,
)

SIDECAR_SCHEMA_VERSION = "learning_runtime_semantic_sidecar.v1"
PAIR_SCHEMA_VERSION = "learning_runtime_paired_evidence.v1"
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


def _read_object(path: Path, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _read_pair_identity(
    pair_package: Mapping[str, Any],
    *,
    agent_id: str,
    agent_version: str,
    runtime_plan_version: str,
) -> tuple[str, dict[str, str]]:
    if pair_package.get("schema_version") != PAIR_SCHEMA_VERSION:
        raise ValueError("pair package schema_version is invalid")
    if pair_package.get("evidence_kind") != "development_paired":
        raise ValueError("LearningLoop sidecar requires development_paired evidence")
    structural_checks = pair_package.get("structural_checks")
    if not isinstance(structural_checks, Mapping) or structural_checks.get(
        "passed"
    ) is not True:
        raise ValueError("pair package structural checks must pass")
    if pair_package.get("release_ready") is not False:
        raise ValueError("development pair package must remain release_ready=false")

    case_id = _require_string(pair_package.get("case_id"), "pair package case_id")
    raw_identity = pair_package.get("capability_identity")
    if not isinstance(raw_identity, Mapping):
        raise ValueError("pair package capability_identity is missing")
    identity = {
        "capability_id": _require_string(
            raw_identity.get("capability_id"),
            "capability_identity.capability_id",
        ),
        "agent_version": _require_string(
            raw_identity.get("agent_version"),
            "capability_identity.agent_version",
        ),
        "runtime_plan_version": _require_string(
            raw_identity.get("runtime_plan_version"),
            "capability_identity.runtime_plan_version",
        ),
    }
    if raw_identity.get("authorization_status") != "not_authorized":
        raise ValueError("development pair identity must remain not_authorized")
    expected = {
        "capability_id": agent_id,
        "agent_version": agent_version,
        "runtime_plan_version": runtime_plan_version,
    }
    if identity != expected:
        raise ValueError(
            "pair package capability identity does not match the supplied "
            "release identity"
        )
    return case_id, identity


def _require_single_case(
    value: Mapping[str, Any], *, label: str, case_id: str
) -> Any:
    if set(value) != {case_id}:
        raise ValueError(f"{label} must contain exactly case_id={case_id}")
    return value[case_id]


def _reviewed_at(value: Any, *, case_id: str) -> datetime:
    text = _require_string(value, f"reviewed_at for {case_id}")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"reviewed_at for {case_id} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"reviewed_at for {case_id} must include a timezone")
    return parsed


def _build_evidence(
    *,
    suite_id: str,
    case_id: str,
    agent_id: str,
    agent_version: str,
    runtime_plan_version: str,
    input_payload: Any,
    output_payload: Any,
    judgement: Any,
) -> RuntimeSemanticEvidence:
    if not isinstance(output_payload, Mapping):
        raise ValueError(f"outputs for {case_id} must be an object")
    if set(output_payload) != {"legacy", "runtime"}:
        raise ValueError(
            f"outputs for {case_id} must contain exactly legacy and runtime"
        )
    if not isinstance(judgement, Mapping):
        raise ValueError(f"judgement for {case_id} must be an object")
    if set(judgement) != JUDGEMENT_FIELDS:
        missing = sorted(JUDGEMENT_FIELDS - set(judgement))
        extra = sorted(set(judgement) - JUDGEMENT_FIELDS)
        raise ValueError(
            f"judgement fields for {case_id} invalid: "
            f"missing={missing!r}, extra={extra!r}"
        )
    if judgement["redaction_status"] != "redacted":
        raise ValueError(f"judgement for {case_id} must be redacted")

    return RuntimeSemanticEvidence.from_payloads(
        input_payload=input_payload,
        legacy_payload=output_payload["legacy"],
        runtime_payload=output_payload["runtime"],
        suite_id=suite_id,
        case_id=case_id,
        agent_id=agent_id,
        agent_version=agent_version,
        runtime_plan_version=runtime_plan_version,
        dimensions=RuntimeSemanticDimensions.model_validate(
            judgement["dimensions"]
        ),
        decision=judgement["decision"],
        judge_type=judgement["judge_type"],
        rubric_version=_require_string(
            judgement["rubric_version"], f"rubric_version for {case_id}"
        ),
        reviewer_ref=_require_string(
            judgement["reviewer_ref"], f"reviewer_ref for {case_id}"
        ),
        reviewed_at=_reviewed_at(judgement["reviewed_at"], case_id=case_id),
        redaction_status="redacted",
        authorization_ref=_require_string(
            judgement["authorization_ref"], f"authorization_ref for {case_id}"
        ),
    )


def collect_sidecar(
    *,
    pair_package: Mapping[str, Any],
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any],
    judgements: Mapping[str, Any],
    suite_id: str,
    agent_id: str,
    agent_version: str,
    runtime_plan_version: str,
) -> dict[str, Any]:
    case_id, identity = _read_pair_identity(
        pair_package,
        agent_id=agent_id,
        agent_version=agent_version,
        runtime_plan_version=runtime_plan_version,
    )
    input_payload = _require_single_case(inputs, label="inputs", case_id=case_id)
    output_payload = _require_single_case(
        outputs, label="outputs", case_id=case_id
    )
    judgement = _require_single_case(
        judgements, label="judgements", case_id=case_id
    )
    evidence = _build_evidence(
        suite_id=suite_id,
        case_id=case_id,
        agent_id=agent_id,
        agent_version=agent_version,
        runtime_plan_version=runtime_plan_version,
        input_payload=input_payload,
        output_payload=output_payload,
        judgement=judgement,
    )
    return {
        "schema_version": SIDECAR_SCHEMA_VERSION,
        "evidence_kind": "development_paired",
        "suite_id": suite_id,
        "capability_identity": {
            **identity,
            "source": "declared_runtime_contract",
            "authorization_status": "not_authorized",
        },
        "cases": [evidence.model_dump(mode="json")],
        "structural_release_eligible": False,
        "semantic_release_eligible": False,
        "canary_release_eligible": False,
        "release_ready": False,
        "blockers": [
            "learning_runtime_development_paired_evidence_only",
            "learning_runtime_human_release_decision_missing",
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect a redacted LearningLoop semantic sidecar."
    )
    parser.add_argument("--pair-package", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--judgements", type=Path, required=True)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--agent-version", required=True)
    parser.add_argument("--runtime-plan-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(args: argparse.Namespace) -> int:
    report = collect_sidecar(
        pair_package=_read_object(args.pair_package, "pair package"),
        inputs=_read_object(args.inputs, "inputs"),
        outputs=_read_object(args.outputs, "outputs"),
        judgements=_read_object(args.judgements, "judgements"),
        suite_id=_require_string(args.suite_id, "suite_id"),
        agent_id=_require_string(args.agent_id, "agent_id"),
        agent_version=_require_string(args.agent_version, "agent_version"),
        runtime_plan_version=_require_string(
            args.runtime_plan_version, "runtime_plan_version"
        ),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "case_count": len(report["cases"]),
                "release_ready": report["release_ready"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(_parser().parse_args()))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
