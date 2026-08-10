"""Independent semantic review evidence for Legacy/Runtime pairs.

This module intentionally does not import or modify ``RuntimeCanarySuite``.
It records a semantic review sidecar that can be joined to an existing
structural canary artifact by suite and case identity.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SHA256_PATTERN = r"^[0-9a-f]{64}$"
SEMANTIC_EVIDENCE_SCHEMA_VERSION = "runtime_semantic_evidence.v1"


class RuntimeSemanticDimensions(BaseModel):
    """Bounded semantic review scores, normalized to ``0..1`` when present."""

    model_config = ConfigDict(extra="forbid")

    task_fulfillment: float | None = Field(default=None, ge=0, le=1)
    factual_correctness: float | None = Field(default=None, ge=0, le=1)
    evidence_faithfulness: float | None = Field(default=None, ge=0, le=1)
    safety: float | None = Field(default=None, ge=0, le=1)


class RuntimeSemanticEvidence(BaseModel):
    """A redacted semantic judgement for one Legacy/Runtime paired case."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["runtime_semantic_evidence.v1"] = (
        "runtime_semantic_evidence.v1"
    )
    suite_id: str = Field(min_length=1, max_length=160)
    case_id: str = Field(min_length=1, max_length=160)
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=64)
    runtime_plan_version: str = Field(min_length=1, max_length=64)
    input_sha256: str = Field(pattern=SHA256_PATTERN)
    legacy_output_sha256: str = Field(pattern=SHA256_PATTERN)
    runtime_output_sha256: str = Field(pattern=SHA256_PATTERN)
    dimensions: RuntimeSemanticDimensions
    decision: Literal["pass", "needs_review", "fail"]
    judge_type: Literal["human", "model", "hybrid"]
    rubric_version: str = Field(min_length=1, max_length=64)
    reviewer_ref: str = Field(min_length=1, max_length=240)
    reviewed_at: datetime
    redaction_status: Literal["redacted", "not_applicable", "unknown"]
    authorization_ref: str = Field(min_length=1, max_length=240)

    @classmethod
    def from_payloads(
        cls,
        *,
        input_payload: Any,
        legacy_payload: Any,
        runtime_payload: Any,
        suite_id: str,
        case_id: str,
        agent_id: str,
        agent_version: str,
        runtime_plan_version: str,
        dimensions: RuntimeSemanticDimensions,
        decision: Literal["pass", "needs_review", "fail"],
        judge_type: Literal["human", "model", "hybrid"],
        rubric_version: str,
        reviewer_ref: str,
        reviewed_at: datetime,
        redaction_status: Literal["redacted", "not_applicable", "unknown"],
        authorization_ref: str,
    ) -> RuntimeSemanticEvidence:
        """Create evidence while deriving all three payload hashes."""

        return cls(
            suite_id=suite_id,
            case_id=case_id,
            agent_id=agent_id,
            agent_version=agent_version,
            runtime_plan_version=runtime_plan_version,
            input_sha256=payload_sha256(input_payload),
            legacy_output_sha256=payload_sha256(legacy_payload),
            runtime_output_sha256=payload_sha256(runtime_payload),
            dimensions=dimensions,
            decision=decision,
            judge_type=judge_type,
            rubric_version=rubric_version,
            reviewer_ref=reviewer_ref,
            reviewed_at=reviewed_at,
            redaction_status=redaction_status,
            authorization_ref=authorization_ref,
        )


def payload_sha256(payload: Any) -> str:
    """Return a deterministic SHA256 for a JSON-compatible payload.

    Mapping key order and insignificant JSON whitespace do not affect the
    digest. Non-JSON values raise ``TypeError`` or ``ValueError`` instead of
    silently producing a non-reproducible evidence hash.
    """

    if isinstance(payload, bytes):
        serialized = payload
    else:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def validate_payload_hash_binding(
    evidence: RuntimeSemanticEvidence,
    *,
    input_payload: Any,
    legacy_payload: Any,
    runtime_payload: Any,
) -> None:
    """Validate that a sidecar is bound to its input and both outputs.

    A ``ValueError`` identifies every mismatched field so an operator can
    reject a stale or cross-case sidecar without modifying the artifact.
    """

    expected: Mapping[str, str] = {
        "input_sha256": payload_sha256(input_payload),
        "legacy_output_sha256": payload_sha256(legacy_payload),
        "runtime_output_sha256": payload_sha256(runtime_payload),
    }
    mismatches = [
        f"{field}:expected={digest}:actual={getattr(evidence, field)}"
        for field, digest in expected.items()
        if getattr(evidence, field) != digest
    ]
    if mismatches:
        raise ValueError(
            "runtime semantic evidence hash binding mismatch: "
            + "; ".join(mismatches)
        )


def payload_hash_binding_matches(
    evidence: RuntimeSemanticEvidence,
    *,
    input_payload: Any,
    legacy_payload: Any,
    runtime_payload: Any,
) -> bool:
    """Return whether the sidecar hashes match the supplied payloads."""

    try:
        validate_payload_hash_binding(
            evidence,
            input_payload=input_payload,
            legacy_payload=legacy_payload,
            runtime_payload=runtime_payload,
        )
    except ValueError:
        return False
    return True


def semantic_release_eligible(
    structural_release_eligible: bool,
    evidence: RuntimeSemanticEvidence,
) -> bool:
    """Return the promotion gate for structural proof and independent review.

    Model-only judgements remain valid diagnostic sidecars, but they cannot
    authorize a canary or default launch.  A release decision must include a
    human review, either directly or as part of a documented hybrid review.
    """

    return (
        structural_release_eligible
        and evidence.decision == "pass"
        and evidence.judge_type in {"human", "hybrid"}
    )


__all__ = [
    "SEMANTIC_EVIDENCE_SCHEMA_VERSION",
    "RuntimeSemanticDimensions",
    "RuntimeSemanticEvidence",
    "payload_hash_binding_matches",
    "payload_sha256",
    "semantic_release_eligible",
    "validate_payload_hash_binding",
]
