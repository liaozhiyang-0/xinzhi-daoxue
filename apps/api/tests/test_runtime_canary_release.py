from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeCanaryEvidence,
    RuntimeCanaryPair,
    RuntimeCanaryReport,
    RuntimeCanarySuite,
    RuntimeCanaryThresholds,
    RuntimeCheckpointRecord,
    RuntimeLaunchSnapshot,
    RuntimeNode,
)
from app.runtime.semantic_evidence import (
    RuntimeSemanticDimensions,
    RuntimeSemanticEvidence,
)
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry

AGENT_ID = "GENERAL_QUESTION_V1"
AGENT_VERSION = "1.0"
PLAN_VERSION = "general-qa-v1"
SUITE_ID = "runtime-canary-release-test"
CASE_ID = "case-1"


def _structural_evidence(**updates: object) -> RuntimeCanaryEvidence:
    payload: dict[str, object] = {
        "kind": "authorized_paired",
        "agent_id": AGENT_ID,
        "agent_version": AGENT_VERSION,
        "runtime_plan_version": PLAN_VERSION,
        "authorization_ref": "change-123",
        "captured_at": datetime(2026, 8, 9, tzinfo=UTC),
        "redaction_status": "redacted",
    }
    payload.update(updates)
    return RuntimeCanaryEvidence.model_validate(payload)


def _report(**evidence_updates: object) -> RuntimeCanaryReport:
    return RuntimeCanaryReport(
        suite_id=SUITE_ID,
        suite_version="1",
        canary_eligible=True,
        release_eligible=True,
        evidence=_structural_evidence(**evidence_updates),
        thresholds=RuntimeCanaryThresholds(),
    )


def _semantic_evidence(**updates: object) -> RuntimeSemanticEvidence:
    payload: dict[str, object] = {
        "suite_id": SUITE_ID,
        "case_id": CASE_ID,
        "agent_id": AGENT_ID,
        "agent_version": AGENT_VERSION,
        "runtime_plan_version": PLAN_VERSION,
        "input_sha256": "0" * 64,
        "legacy_output_sha256": "1" * 64,
        "runtime_output_sha256": "2" * 64,
        "dimensions": RuntimeSemanticDimensions(
            task_fulfillment=1.0,
            factual_correctness=1.0,
            safety=1.0,
        ),
        "decision": "pass",
        "judge_type": "human",
        "rubric_version": "general-question-v1",
        "reviewer_ref": "review-123",
        "reviewed_at": datetime(2026, 8, 9, tzinfo=UTC),
        "redaction_status": "redacted",
        "authorization_ref": "review-auth-123",
    }
    payload.update(updates)
    return RuntimeSemanticEvidence.model_validate(payload)


def _suite() -> RuntimeCanarySuite:
    checkpoint_run = AgentRun(
        run_id="run-release",
        task_id="task-release",
        goal="release gate",
        plan=AgentRunPlan(
            plan_id="plan-release",
            version=PLAN_VERSION,
            goal="release gate",
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
            source="test",
            reason="release gate test",
        ),
    )
    return RuntimeCanarySuite(
        suite_id=SUITE_ID,
        evidence=_structural_evidence(),
        pairs=[
            RuntimeCanaryPair(
                case_id=CASE_ID,
                legacy_payload={
                    "agent_id": AGENT_ID,
                    "status": "completed",
                    "answer": "same",
                },
                runtime_payload={
                    "agent_id": AGENT_ID,
                    "status": "completed",
                    "answer": "same",
                },
                runtime_checkpoints=[
                    RuntimeCheckpointRecord(
                        sequence=1,
                        state_version=1,
                        state_data=checkpoint_run.model_dump(mode="json"),
                    ).model_dump(mode="json")
                ],
            )
        ],
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def test_registry_without_sidecar_preserves_structural_gate() -> None:
    registry = RuntimeCanaryReleaseRegistry({AGENT_ID: _report()})

    assert registry.release_eligible(
        AGENT_ID,
        expected_agent_version=AGENT_VERSION,
        expected_runtime_plan_version=PLAN_VERSION,
    ) is True
    assert registry.reason(AGENT_ID) == "canary_release_evidence_approved"


def test_configured_sidecar_requires_a_passing_semantic_decision() -> None:
    report = _report()
    passing = RuntimeCanaryReleaseRegistry(
        {AGENT_ID: report},
        semantic_evidence={AGENT_ID: _semantic_evidence()},
    )
    missing = RuntimeCanaryReleaseRegistry(
        {AGENT_ID: report},
        semantic_evidence={},
    )
    needs_review = RuntimeCanaryReleaseRegistry(
        {AGENT_ID: report},
        semantic_evidence={
            AGENT_ID: _semantic_evidence(decision="needs_review")
        },
    )

    assert passing.release_eligible(AGENT_ID) is True
    assert passing.reason(AGENT_ID) == "canary_release_evidence_approved"
    assert missing.release_eligible(AGENT_ID) is False
    assert missing.reason(AGENT_ID) == "semantic_evidence_missing"
    assert needs_review.release_eligible(AGENT_ID) is False
    assert needs_review.reason(AGENT_ID) == "semantic_decision_not_pass"


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("agent_id", "semantic_evidence_identity_mismatch"),
        ("agent_version", "semantic_evidence_agent_version_mismatch"),
        (
            "runtime_plan_version",
            "semantic_evidence_runtime_plan_version_mismatch",
        ),
        ("suite_id", "semantic_evidence_suite_id_mismatch"),
    ],
)
def test_reason_distinguishes_sidecar_identity_and_version_mismatch(
    field: str,
    reason: str,
) -> None:
    updates: dict[str, object] = {field: "stale-value"}
    registry = RuntimeCanaryReleaseRegistry(
        {AGENT_ID: _report()},
        semantic_evidence={AGENT_ID: _semantic_evidence(**updates)},
    )

    assert registry.release_eligible(AGENT_ID) is False
    assert registry.reason(AGENT_ID) == reason


def test_from_paths_loads_and_binds_optional_semantic_sidecar(
    tmp_path: Path,
) -> None:
    suite = _suite()
    suite_path = tmp_path / "suite.json"
    sidecar_path = tmp_path / "semantic.json"
    _write_json(suite_path, suite.model_dump(mode="json"))
    _write_json(sidecar_path, _semantic_evidence().model_dump(mode="json"))

    registry = RuntimeCanaryReleaseRegistry.from_paths(
        f"{AGENT_ID}={suite_path}",
        semantic_paths=f"{AGENT_ID}={sidecar_path}",
    )

    assert registry.release_eligible(
        AGENT_ID,
        expected_agent_version=AGENT_VERSION,
        expected_runtime_plan_version=PLAN_VERSION,
    ) is True


def test_from_paths_empty_semantic_config_keeps_legacy_compatibility(
    tmp_path: Path,
) -> None:
    suite_path = tmp_path / "suite.json"
    _write_json(suite_path, _suite().model_dump(mode="json"))

    registry = RuntimeCanaryReleaseRegistry.from_paths(
        f"{AGENT_ID}={suite_path}",
        semantic_paths="",
    )

    assert registry.release_eligible(AGENT_ID) is True


def test_from_paths_requires_semantic_coverage_for_every_case(
    tmp_path: Path,
) -> None:
    suite = _suite()
    second_pair = suite.pairs[0].model_copy(update={"case_id": "case-2"})
    suite = suite.model_copy(update={"pairs": [suite.pairs[0], second_pair]})
    suite_path = tmp_path / "suite.json"
    sidecar_path = tmp_path / "semantic.json"
    _write_json(suite_path, suite.model_dump(mode="json"))
    _write_json(sidecar_path, [_semantic_evidence().model_dump(mode="json")])

    with pytest.raises(ValueError, match="case coverage incomplete"):
        RuntimeCanaryReleaseRegistry.from_paths(
            f"{AGENT_ID}={suite_path}",
            semantic_paths=f"{AGENT_ID}={sidecar_path}",
        )


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("agent_id", "agent_id mismatch"),
        ("agent_version", "agent_version mismatch"),
        ("runtime_plan_version", "runtime_plan_version mismatch"),
        ("suite_id", "suite_id mismatch"),
        ("case_id", "case_id mismatch"),
    ],
)
def test_from_paths_rejects_sidecar_not_bound_to_structural_suite(
    tmp_path: Path,
    field: str,
    message: str,
) -> None:
    suite_path = tmp_path / "suite.json"
    sidecar_path = tmp_path / "semantic.json"
    _write_json(suite_path, _suite().model_dump(mode="json"))
    sidecar = _semantic_evidence(**{field: "stale-value"})
    _write_json(sidecar_path, sidecar.model_dump(mode="json"))

    with pytest.raises(ValueError, match=message):
        RuntimeCanaryReleaseRegistry.from_paths(
            f"{AGENT_ID}={suite_path}",
            semantic_paths=f"{AGENT_ID}={sidecar_path}",
        )
