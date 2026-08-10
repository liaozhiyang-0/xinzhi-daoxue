from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.runtime import (
    RuntimeCanaryEvidence,
    RuntimeCanaryPair,
    RuntimeCanaryReport,
    RuntimeCanarySuite,
    RuntimeCanaryThresholds,
    evaluate_runtime_canary_suite,
)
from app.runtime.semantic_evidence import (
    SEMANTIC_EVIDENCE_SCHEMA_VERSION,
    RuntimeSemanticDimensions,
    RuntimeSemanticEvidence,
    payload_hash_binding_matches,
    payload_sha256,
    semantic_release_eligible,
    validate_payload_hash_binding,
)
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from pydantic import ValidationError

INPUT = {"text": "What is an agent?", "course_id": "CT"}
LEGACY = {"status": "completed", "answer": "A legacy answer"}
RUNTIME = {"status": "completed", "answer": "A runtime answer"}
AGENT_ID = "GENERAL_QUESTION_V1"
AGENT_VERSION = "1.0"
PLAN_VERSION = "general-qa-v1"
SUITE_ID = "semantic-suite"


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


def _release_report(**updates: object) -> RuntimeCanaryReport:
    structural_payload: dict[str, object] = {
        "kind": "authorized_paired",
        "agent_id": AGENT_ID,
        "agent_version": AGENT_VERSION,
        "runtime_plan_version": PLAN_VERSION,
        "authorization_ref": "structural-auth-123",
        "captured_at": datetime(2026, 8, 9, tzinfo=UTC),
        "redaction_status": "redacted",
    }
    structural_payload.update(updates)
    return RuntimeCanaryReport(
        suite_id=SUITE_ID,
        suite_version="1",
        canary_eligible=True,
        release_eligible=True,
        evidence=RuntimeCanaryEvidence.model_validate(structural_payload),
        thresholds=RuntimeCanaryThresholds(),
    )


def _suite_for_sidecar_hash_binding() -> RuntimeCanarySuite:
    return RuntimeCanarySuite(
        suite_id=SUITE_ID,
        evidence=RuntimeCanaryEvidence(
            kind="authorized_paired",
            agent_id=AGENT_ID,
            agent_version=AGENT_VERSION,
            runtime_plan_version=PLAN_VERSION,
            authorization_ref="structural-auth-123",
            captured_at=datetime(2026, 8, 9, tzinfo=UTC),
            redaction_status="redacted",
        ),
        pairs=[
            RuntimeCanaryPair(
                case_id="semantic-case",
                input_sha256=payload_sha256(INPUT),
                legacy_payload=LEGACY,
                runtime_payload=RUNTIME,
            )
        ],
    )


def _write_json(path: Path, payload: object) -> None:
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


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
    ("structural", "decision", "judge_type", "expected"),
    [
        (True, "pass", "human", True),
        (True, "pass", "hybrid", True),
        (True, "pass", "model", False),
        (False, "pass", "human", False),
        (True, "needs_review", "human", False),
        (True, "fail", "human", False),
    ],
)
def test_semantic_release_eligibility_requires_both_gates(
    structural: bool,
    decision: str,
    judge_type: str,
    expected: bool,
) -> None:
    evidence = _evidence(decision=decision, judge_type=judge_type)

    assert semantic_release_eligible(structural, evidence) is expected


def test_model_only_pass_is_diagnostic_not_release_eligible() -> None:
    evidence = _evidence(judge_type="model")
    registry = RuntimeCanaryReleaseRegistry(
        {AGENT_ID: _release_report()},
        semantic_evidence={AGENT_ID: evidence},
    )

    assert registry.release_eligible(AGENT_ID) is False
    assert registry.reason(AGENT_ID) == "semantic_judge_not_independent"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("redaction_status", "unknown", "semantic_redaction_status_invalid"),
        ("redaction_status", "not_applicable", "semantic_redaction_status_invalid"),
        ("authorization_ref", "   ", "semantic_authorization_ref_missing"),
    ],
)
def test_manually_loaded_sidecar_cannot_bypass_provenance_gate(
    field: str,
    value: str,
    reason: str,
) -> None:
    registry = RuntimeCanaryReleaseRegistry(
        {AGENT_ID: _release_report()},
        semantic_evidence={AGENT_ID: _evidence(**{field: value})},
    )

    assert registry.release_eligible(AGENT_ID) is False
    assert registry.reason(AGENT_ID) == reason


@pytest.mark.parametrize(
    ("field", "value"),
    [("redaction_status", "unknown"), ("authorization_ref", " ")],
)
def test_manual_sidecar_cannot_bypass_structural_suite_authorization(
    field: str,
    value: str,
) -> None:
    registry = RuntimeCanaryReleaseRegistry(
        {AGENT_ID: _release_report(**{field: value})},
        semantic_evidence={AGENT_ID: _evidence()},
    )

    assert registry.release_eligible(AGENT_ID) is False
    assert registry.reason(AGENT_ID) == "canary_authorized_evidence_missing"


def test_manual_sidecar_keeps_legacy_separate_review_authorization_compatible() -> None:
    registry = RuntimeCanaryReleaseRegistry(
        {AGENT_ID: _release_report()},
        semantic_evidence={AGENT_ID: _evidence()},
    )

    assert registry.release_eligible(AGENT_ID) is True


def test_from_paths_recomputes_sidecar_output_hashes_from_structural_case(
    tmp_path: Path,
) -> None:
    suite = _suite_for_sidecar_hash_binding()
    suite_path = tmp_path / "suite.json"
    sidecar_path = tmp_path / "sidecar.json"
    _write_json(suite_path, suite.model_dump(mode="json"))
    _write_json(sidecar_path, _evidence().model_dump(mode="json"))

    RuntimeCanaryReleaseRegistry.from_paths(
        f"{AGENT_ID}={suite_path}",
        semantic_paths=f"{AGENT_ID}={sidecar_path}",
    )


@pytest.mark.parametrize(
    "field",
    ["legacy_output_sha256", "runtime_output_sha256"],
)
def test_from_paths_rejects_manually_tampered_sidecar_output_hash(
    tmp_path: Path,
    field: str,
) -> None:
    suite = _suite_for_sidecar_hash_binding()
    suite_path = tmp_path / "suite.json"
    sidecar_path = tmp_path / "sidecar.json"
    _write_json(suite_path, suite.model_dump(mode="json"))
    tampered = _evidence(**{field: "f" * 64})
    _write_json(sidecar_path, tampered.model_dump(mode="json"))

    with pytest.raises(ValueError, match=f"{field}"):
        RuntimeCanaryReleaseRegistry.from_paths(
            f"{AGENT_ID}={suite_path}",
            semantic_paths=f"{AGENT_ID}={sidecar_path}",
        )


def test_from_paths_rejects_missing_structural_input_hash(
    tmp_path: Path,
) -> None:
    suite = _suite_for_sidecar_hash_binding().model_copy(
        update={
            "pairs": [
                _suite_for_sidecar_hash_binding().pairs[0].model_copy(
                    update={"input_sha256": None}
                )
            ]
        }
    )
    suite_path = tmp_path / "suite.json"
    sidecar_path = tmp_path / "sidecar.json"
    _write_json(suite_path, suite.model_dump(mode="json"))
    _write_json(sidecar_path, _evidence().model_dump(mode="json"))

    with pytest.raises(ValueError, match="input hash binding missing"):
        RuntimeCanaryReleaseRegistry.from_paths(
            f"{AGENT_ID}={suite_path}",
            semantic_paths=f"{AGENT_ID}={sidecar_path}",
        )


def test_authorized_suite_without_input_hash_is_not_release_eligible() -> None:
    suite = _suite_for_sidecar_hash_binding().model_copy(
        update={
            "pairs": [
                _suite_for_sidecar_hash_binding().pairs[0].model_copy(
                    update={"input_sha256": None}
                )
            ]
        }
    )

    report = evaluate_runtime_canary_suite(suite)

    assert report.release_eligible is False
    assert "semantic-case:input_sha256_missing" in report.release_failed_checks


def test_runtime_canary_pair_rejects_an_invalid_input_hash() -> None:
    with pytest.raises(ValidationError):
        RuntimeCanaryPair(
            case_id="semantic-case",
            input_sha256="not-a-sha256",
            legacy_payload=LEGACY,
            runtime_payload=RUNTIME,
        )
