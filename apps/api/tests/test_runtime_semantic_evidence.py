from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.runtime.semantic_evidence import (
    SEMANTIC_EVIDENCE_SCHEMA_VERSION,
    RuntimeSemanticDimensions,
    RuntimeSemanticEvidence,
    payload_hash_binding_matches,
    payload_sha256,
    semantic_release_eligible,
    validate_payload_hash_binding,
)
from pydantic import ValidationError

INPUT = {"text": "What is an agent?", "course_id": "CT"}
LEGACY = {"status": "completed", "answer": "A legacy answer"}
RUNTIME = {"status": "completed", "answer": "A runtime answer"}


def _evidence(**updates: object) -> RuntimeSemanticEvidence:
    evidence = RuntimeSemanticEvidence.from_payloads(
        input_payload=INPUT,
        legacy_payload=LEGACY,
        runtime_payload=RUNTIME,
        suite_id="semantic-suite",
        case_id="semantic-case",
        agent_id="GENERAL_QUESTION_V1",
        agent_version="1.0",
        runtime_plan_version="general-qa-v1",
        dimensions=RuntimeSemanticDimensions(
            task_fulfillment=1.0,
            factual_correctness=0.9,
            evidence_faithfulness=None,
            safety=1.0,
        ),
        decision="pass",
        judge_type="human",
        rubric_version="general-question-v1",
        reviewer_ref="review-123",
        reviewed_at=datetime(2026, 8, 9, tzinfo=UTC),
        redaction_status="redacted",
        authorization_ref="auth-123",
    )
    if not updates:
        return evidence
    updated = evidence.model_dump(mode="python")
    updated.update(updates)
    return RuntimeSemanticEvidence.model_validate(updated)


def test_payload_sha256_is_deterministic_for_json_mapping_order() -> None:
    first = payload_sha256({"b": 2, "a": [1, "中文"]})
    second = payload_sha256({"a": [1, "中文"], "b": 2})

    assert first == second
    assert first == (
        "56f350d2b1910eac68f0f353030416ac3292a6984296f398642b3d24fa2497a3"
    )
    assert len(first) == 64


def test_from_payloads_records_sidecar_contract_and_nullable_dimensions() -> None:
    evidence = _evidence()

    assert evidence.schema_version == SEMANTIC_EVIDENCE_SCHEMA_VERSION
    assert evidence.input_sha256 == payload_sha256(INPUT)
    assert evidence.legacy_output_sha256 == payload_sha256(LEGACY)
    assert evidence.runtime_output_sha256 == payload_sha256(RUNTIME)
    assert evidence.dimensions.evidence_faithfulness is None
    assert evidence.model_dump(mode="json")["judge_type"] == "human"


def test_validate_payload_hash_binding_accepts_matching_payloads() -> None:
    evidence = _evidence()

    validate_payload_hash_binding(
        evidence,
        input_payload=INPUT,
        legacy_payload=LEGACY,
        runtime_payload=RUNTIME,
    )
    assert payload_hash_binding_matches(
        evidence,
        input_payload=INPUT,
        legacy_payload=LEGACY,
        runtime_payload=RUNTIME,
    ) is True


def test_validate_payload_hash_binding_rejects_stale_runtime_payload() -> None:
    evidence = _evidence()

    with pytest.raises(ValueError, match="runtime_output_sha256"):
        validate_payload_hash_binding(
            evidence,
            input_payload=INPUT,
            legacy_payload=LEGACY,
            runtime_payload={"status": "failed"},
        )
    assert payload_hash_binding_matches(
        evidence,
        input_payload=INPUT,
        legacy_payload=LEGACY,
        runtime_payload={"status": "failed"},
    ) is False


def test_contract_rejects_invalid_hash_extra_fields_and_out_of_range_scores() -> None:
    valid_payload = _evidence().model_dump(mode="python")
    invalid_hash_payload = {**valid_payload, "input_sha256": "not-a-sha256"}
    with pytest.raises(ValidationError):
        RuntimeSemanticEvidence.model_validate(invalid_hash_payload)
    invalid_score_payload = {
        **valid_payload,
        "dimensions": {"task_fulfillment": 1.1},
    }
    with pytest.raises(ValidationError):
        RuntimeSemanticEvidence.model_validate(invalid_score_payload)
    extra_field_payload = {**valid_payload, "unexpected_field": "rejected"}
    with pytest.raises(ValidationError):
        RuntimeSemanticEvidence.model_validate(extra_field_payload)


@pytest.mark.parametrize(
    ("structural", "decision", "expected"),
    [
        (True, "pass", True),
        (False, "pass", False),
        (True, "needs_review", False),
        (True, "fail", False),
    ],
)
def test_semantic_release_eligibility_requires_both_gates(
    structural: bool,
    decision: str,
    expected: bool,
) -> None:
    evidence = _evidence(decision=decision)

    assert semantic_release_eligible(structural, evidence) is expected
