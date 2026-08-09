from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pytest
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeCanaryEvidence,
    RuntimeCanaryPair,
    RuntimeCanarySuite,
    RuntimeCheckpointRecord,
    RuntimeLaunchSnapshot,
    RuntimeNode,
    RuntimeRunStatus,
    audit_checkpoint_trace,
)
from app.runtime.semantic_evidence import (
    RuntimeSemanticDimensions,
    RuntimeSemanticEvidence,
    payload_sha256,
)
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry

# Keep direct imports of the repository's offline scripts deterministic when
# pytest has already imported application modules from ``apps/api``.
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.check_runtime_release_preflight import run_preflight  # noqa: E402
from scripts.collect_runtime_canary import (  # noqa: E402
    build_suite,
    build_suite_from_manifest,
)
from scripts.collect_runtime_semantic_evidence import (  # noqa: E402
    collect_sidecar,
)

AGENT_ID = "GENERAL_QUESTION_V1"
AGENT_VERSION = "1.0"
PLAN_VERSION = "general-qa-v1"
SUITE_ID = "evidence-intake-contract"
CASE_ID = "case-1"
AUTHORIZATION_REF = "change-record-2026-08-09"
CAPTURED_AT = datetime(2026, 8, 9, 9, 0, tzinfo=UTC)
REVIEWED_AT = datetime(2026, 8, 9, 10, 0, tzinfo=UTC)


def _run(*, run_id: str = "run-evidence", state_version: int = 1) -> AgentRun:
    return AgentRun(
        run_id=run_id,
        task_id="task-evidence",
        goal="contract fixture only",
        plan=AgentRunPlan(
            plan_id="plan-evidence",
            version=PLAN_VERSION,
            goal="contract fixture only",
            nodes=[
                RuntimeNode(
                    node_id="final",
                    node_type="terminal",
                    handler_id="runtime.final",
                )
            ],
        ),
        launch_decision=RuntimeLaunchSnapshot(
            agent_id=AGENT_ID,
            mode="canary",
            source="contract-test",
            reason="synthetic fixture; not release evidence",
        ),
        state_version=state_version,
        status=RuntimeRunStatus.COMPLETED,
    )


def _checkpoints(*, valid: bool = True) -> list[dict[str, Any]]:
    record = RuntimeCheckpointRecord(
        sequence=1 if valid else 2,
        state_version=1,
        state_data=_run().model_dump(mode="json"),
    )
    return [record.model_dump(mode="json")]


def _payload(answer: str) -> dict[str, Any]:
    return {
        "agent_id": AGENT_ID,
        "status": "completed",
        "answer": answer,
        "provider": "offline-fixture",
    }


def _suite(
    *, kind: Literal["synthetic", "authorized_paired"] = "authorized_paired"
) -> RuntimeCanarySuite:
    evidence = RuntimeCanaryEvidence(
        kind=kind,
        agent_id=AGENT_ID,
        agent_version=AGENT_VERSION,
        runtime_plan_version=PLAN_VERSION,
        authorization_ref=AUTHORIZATION_REF,
        captured_at=CAPTURED_AT,
        redaction_status="redacted",
    )
    return RuntimeCanarySuite(
        suite_id=SUITE_ID,
        evidence=evidence,
        pairs=[
            RuntimeCanaryPair(
                case_id=CASE_ID,
                legacy_payload=_payload("legacy fixture"),
                runtime_payload=_payload("runtime fixture"),
                runtime_checkpoints=_checkpoints(),
            )
        ],
    )


def _inputs() -> dict[str, Any]:
    return {
        CASE_ID: {
            "question": "synthetic contract input",
            "student_ref": "de-identified-student",
        }
    }


def _judgements(**updates: Any) -> dict[str, Any]:
    judgement: dict[str, Any] = {
        "dimensions": {
            "task_fulfillment": 1.0,
            "factual_correctness": 1.0,
            "evidence_faithfulness": None,
            "safety": 1.0,
        },
        "decision": "pass",
        "judge_type": "human",
        "rubric_version": "general-question-v1",
        "reviewer_ref": "review-record-1",
        "reviewed_at": REVIEWED_AT.isoformat(),
        "redaction_status": "redacted",
        "authorization_ref": AUTHORIZATION_REF,
    }
    judgement.update(updates)
    return {CASE_ID: judgement}


def _semantic(suite: RuntimeCanarySuite) -> RuntimeSemanticEvidence:
    pair = suite.pairs[0]
    return RuntimeSemanticEvidence.from_payloads(
        input_payload=_inputs()[CASE_ID],
        legacy_payload=pair.legacy_payload,
        runtime_payload=pair.runtime_payload,
        suite_id=suite.suite_id,
        case_id=CASE_ID,
        agent_id=suite.evidence.agent_id,
        agent_version=suite.evidence.agent_version,
        runtime_plan_version=suite.evidence.runtime_plan_version,
        dimensions=RuntimeSemanticDimensions(
            task_fulfillment=1.0,
            factual_correctness=1.0,
            safety=1.0,
        ),
        decision="pass",
        judge_type="human",
        rubric_version="general-question-v1",
        reviewer_ref="review-record-1",
        reviewed_at=REVIEWED_AT,
        redaction_status="redacted",
        authorization_ref=AUTHORIZATION_REF,
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_structural_intake_requires_authorization_and_binds_versions() -> None:
    suite = build_suite(
        agent_id=AGENT_ID,
        agent_version=AGENT_VERSION,
        runtime_plan_version=PLAN_VERSION,
        suite_id=SUITE_ID,
        case_id=CASE_ID,
        authorization_ref=AUTHORIZATION_REF,
        captured_at=CAPTURED_AT,
        legacy_payload=_payload("legacy fixture"),
        runtime_payload=_payload("runtime fixture"),
        runtime_checkpoints=_checkpoints(),
    )

    assert suite.evidence.release_ready is True
    assert suite.evidence.kind == "authorized_paired"
    assert suite.evidence.redaction_status == "redacted"
    assert suite.evidence.agent_version == AGENT_VERSION
    assert suite.evidence.runtime_plan_version == PLAN_VERSION

    with pytest.raises(ValueError):
        build_suite(
            agent_id=AGENT_ID,
            agent_version=AGENT_VERSION,
            runtime_plan_version=PLAN_VERSION,
            suite_id=SUITE_ID,
            case_id=CASE_ID,
            authorization_ref=" ",
            captured_at=CAPTURED_AT,
            legacy_payload=_payload("legacy fixture"),
            runtime_payload=_payload("runtime fixture"),
            runtime_checkpoints=_checkpoints(),
        )


def test_checkpoint_trace_audit_rejects_sequence_gaps_before_suite_creation() -> None:
    valid = audit_checkpoint_trace(_checkpoints())
    invalid = audit_checkpoint_trace(_checkpoints(valid=False))

    assert valid.valid is True
    assert valid.checkpoint_count == 1
    assert invalid.valid is False
    assert any("sequence_gap" in error for error in invalid.errors)

    with pytest.raises(ValueError):
        build_suite(
            agent_id=AGENT_ID,
            agent_version=AGENT_VERSION,
            runtime_plan_version=PLAN_VERSION,
            suite_id=SUITE_ID,
            case_id=CASE_ID,
            authorization_ref=AUTHORIZATION_REF,
            captured_at=CAPTURED_AT,
            legacy_payload=_payload("legacy fixture"),
            runtime_payload=_payload("runtime fixture"),
            runtime_checkpoints=_checkpoints(valid=False),
        )


def test_manifest_intake_rejects_naive_capture_time_and_path_escape(
    tmp_path: Path,
) -> None:
    legacy_path = tmp_path / "legacy.json"
    runtime_path = tmp_path / "runtime.json"
    checkpoints_path = tmp_path / "checkpoints.json"
    _write_json(legacy_path, _payload("legacy fixture"))
    _write_json(runtime_path, _payload("runtime fixture"))
    _write_json(checkpoints_path, _checkpoints())
    manifest: dict[str, Any] = {
        "schema_version": "runtime_canary_manifest.v1",
        "agent_id": AGENT_ID,
        "agent_version": AGENT_VERSION,
        "runtime_plan_version": PLAN_VERSION,
        "suite_id": SUITE_ID,
        "authorization_ref": AUTHORIZATION_REF,
        "captured_at": "2026-08-09T09:00:00",
        "cases": [
            {
                "case_id": CASE_ID,
                "legacy": legacy_path.name,
                "runtime": runtime_path.name,
                "checkpoints": checkpoints_path.name,
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="timezone"):
        build_suite_from_manifest(manifest_path)

    manifest["captured_at"] = CAPTURED_AT.isoformat()
    manifest["cases"][0]["legacy"] = "../outside.json"
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="outside the manifest directory"):
        build_suite_from_manifest(manifest_path)


def test_semantic_sidecar_is_redacted_deterministic_and_hash_bound() -> None:
    suite = _suite()
    sidecar = collect_sidecar(
        suite=suite,
        inputs=_inputs(),
        judgements=_judgements(),
    )

    assert len(sidecar) == 1
    item = sidecar[0]
    assert item.redaction_status == "redacted"
    assert item.input_sha256 == payload_sha256(_inputs()[CASE_ID])
    assert item.legacy_output_sha256 == payload_sha256(
        suite.pairs[0].legacy_payload
    )
    assert item.runtime_output_sha256 == payload_sha256(
        suite.pairs[0].runtime_payload
    )
    serialized = json.dumps(item.model_dump(mode="json"), ensure_ascii=False)
    assert "synthetic contract input" not in serialized
    assert "de-identified-student" not in serialized


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"redaction_status": "unknown"}, "redacted"),
        ({"reviewed_at": "2026-08-09T10:00:00"}, "timezone"),
        ({"decision": "invalid"}, "decision"),
        ({"unexpected": "field"}, "fields"),
    ],
)
def test_semantic_judgement_contract_is_strict(
    updates: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        collect_sidecar(
            suite=_suite(),
            inputs=_inputs(),
            judgements=_judgements(**updates),
        )


def test_semantic_case_coverage_requires_exact_structural_case_set() -> None:
    inputs = _inputs()
    del inputs[CASE_ID]
    with pytest.raises(ValueError, match="case_id mismatch"):
        collect_sidecar(suite=_suite(), inputs=inputs, judgements=_judgements())

    extra_judgements = _judgements()
    extra_judgements["case-extra"] = extra_judgements[CASE_ID].copy()
    with pytest.raises(ValueError, match="case_id mismatch"):
        collect_sidecar(
            suite=_suite(),
            inputs=_inputs(),
            judgements=extra_judgements,
        )


def test_preflight_binds_sidecar_identity_and_versions(tmp_path: Path) -> None:
    suite = _suite()
    suite_path = tmp_path / "suite.json"
    sidecar_path = tmp_path / "sidecar.json"
    _write_json(suite_path, suite.model_dump(mode="json"))
    _write_json(sidecar_path, _semantic(suite).model_dump(mode="json"))

    payload, exit_code = run_preflight(
        agent_id=AGENT_ID,
        suite=str(suite_path),
        semantic_sidecar=str(sidecar_path),
        expected_agent_version="stale-agent-version",
        expected_runtime_plan_version=PLAN_VERSION,
    )

    assert exit_code != 0
    assert payload["provider_free"] is True
    assert payload["release_eligible"] is False
    assert "canary_artifact_agent_version_mismatch" in payload[
        "blocking_reasons"
    ]

    sidecar = _semantic(suite).model_copy(update={"runtime_plan_version": "stale-plan"})
    registry = RuntimeCanaryReleaseRegistry.from_paths(
        f"{AGENT_ID}={suite_path}",
        semantic_paths=f"{AGENT_ID}={sidecar_path}",
    )
    # The registry is checked independently below after replacing the sidecar;
    # the first preflight assertion above proves expected-version binding.
    _write_json(sidecar_path, sidecar.model_dump(mode="json"))
    with pytest.raises(ValueError, match="runtime_plan_version mismatch"):
        RuntimeCanaryReleaseRegistry.from_paths(
            f"{AGENT_ID}={suite_path}",
            semantic_paths=f"{AGENT_ID}={sidecar_path}",
        )
    assert registry.release_eligible(AGENT_ID) is True


def test_synthetic_suite_never_becomes_release_eligible(tmp_path: Path) -> None:
    suite = _suite(kind="synthetic")
    suite_path = tmp_path / "synthetic-suite.json"
    sidecar_path = tmp_path / "synthetic-sidecar.json"
    _write_json(suite_path, suite.model_dump(mode="json"))
    _write_json(sidecar_path, _semantic(suite).model_dump(mode="json"))

    payload, exit_code = run_preflight(
        agent_id=AGENT_ID,
        suite=str(suite_path),
        semantic_sidecar=str(sidecar_path),
    )

    assert exit_code != 0
    assert payload["provider_free"] is True
    assert payload["structural_eligible"] is False
    assert payload["semantic_eligible"] is False
    assert payload["release_eligible"] is False


def test_missing_suite_and_sidecar_fail_closed(tmp_path: Path) -> None:
    payload, exit_code = run_preflight(
        agent_id=AGENT_ID,
        suite=str(tmp_path / "missing-suite.json"),
        semantic_sidecar=str(tmp_path / "missing-sidecar.json"),
    )

    assert exit_code != 0
    assert payload["provider_free"] is True
    assert payload["release_eligible"] is False
    assert "structural_suite_file_missing" in payload["blocking_reasons"]
    assert "semantic_sidecar_file_missing" in payload["blocking_reasons"]


def test_structural_and_semantic_artifacts_require_exact_case_identity(
    tmp_path: Path,
) -> None:
    suite = _suite()
    sidecar = _semantic(suite).model_copy(update={"case_id": "other-case"})
    suite_path = tmp_path / "suite.json"
    sidecar_path = tmp_path / "sidecar.json"
    _write_json(suite_path, suite.model_dump(mode="json"))
    _write_json(sidecar_path, sidecar.model_dump(mode="json"))

    with pytest.raises(ValueError, match="case_id mismatch"):
        RuntimeCanaryReleaseRegistry.from_paths(
            f"{AGENT_ID}={suite_path}",
            semantic_paths=f"{AGENT_ID}={sidecar_path}",
        )

    # The malformed sidecar above is rejected before it can influence a
    # release decision; this fixture is never considered real evidence.
    registry = RuntimeCanaryReleaseRegistry({}, semantic_evidence={})
    assert registry.release_eligible(AGENT_ID) is False
    assert sidecar.case_id == "other-case"
