from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeCanaryEvidence,
    RuntimeCanaryPair,
    RuntimeCanarySuite,
    RuntimeCheckpointRecord,
    RuntimeLaunchSnapshot,
    RuntimeNode,
)
from app.runtime.semantic_evidence import (
    RuntimeSemanticDimensions,
    RuntimeSemanticEvidence,
)

from scripts.collect_runtime_canary import build_suite

ROOT = Path(__file__).resolve().parents[3]
PREFLIGHT = ROOT / "scripts" / "check_runtime_release_preflight.py"
AGENT_ID = "GENERAL_QUESTION_V1"
AGENT_VERSION = "1.0"
PLAN_VERSION = "general-qa-v1"
SUITE_ID = "synthetic-preflight-suite"
CASE_ID = "synthetic-case-1"


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PREFLIGHT), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _payload() -> dict[str, object]:
    return {
        "agent_id": AGENT_ID,
        "status": "completed",
        "answer": "synthetic paired answer",
    }


def _checkpoints() -> list[dict[str, object]]:
    run = AgentRun(
        run_id="synthetic-run",
        task_id="synthetic-task",
        goal="synthetic preflight fixture",
        plan=AgentRunPlan(
            plan_id="synthetic-plan",
            version=PLAN_VERSION,
            goal="synthetic preflight fixture",
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
            source="synthetic-test",
            reason="fixture only; not authorized release evidence",
        ),
    )
    return [
        RuntimeCheckpointRecord(
            sequence=1,
            state_version=1,
            state_data=run.model_dump(mode="json"),
        ).model_dump(mode="json")
    ]


def _suite(*, authorized: bool = True) -> RuntimeCanarySuite:
    legacy = _payload()
    runtime = _payload()
    if authorized:
        return build_suite(
            agent_id=AGENT_ID,
            agent_version=AGENT_VERSION,
            runtime_plan_version=PLAN_VERSION,
            suite_id=SUITE_ID,
            case_id=CASE_ID,
            authorization_ref="synthetic-test-only-not-release-evidence",
            captured_at=datetime(2026, 8, 9, tzinfo=UTC),
            input_payload={"question": "synthetic"},
            legacy_payload=legacy,
            runtime_payload=runtime,
            runtime_checkpoints=_checkpoints(),
        )
    return RuntimeCanarySuite(
        suite_id=SUITE_ID,
        evidence=RuntimeCanaryEvidence(
            kind="synthetic",
            agent_id=AGENT_ID,
        ),
        pairs=[
            RuntimeCanaryPair(
                case_id=CASE_ID,
                legacy_payload=legacy,
                runtime_payload=runtime,
                runtime_checkpoints=_checkpoints(),
            )
        ],
    )


def _semantic() -> RuntimeSemanticEvidence:
    return RuntimeSemanticEvidence.from_payloads(
        input_payload={"question": "synthetic"},
        legacy_payload=_payload(),
        runtime_payload=_payload(),
        suite_id=SUITE_ID,
        case_id=CASE_ID,
        agent_id=AGENT_ID,
        agent_version=AGENT_VERSION,
        runtime_plan_version=PLAN_VERSION,
        dimensions=RuntimeSemanticDimensions(
            task_fulfillment=1.0,
            factual_correctness=1.0,
            evidence_faithfulness=1.0,
            safety=1.0,
        ),
        decision="pass",
        judge_type="human",
        rubric_version="synthetic-test-v1",
        reviewer_ref="synthetic-reviewer",
        reviewed_at=datetime(2026, 8, 9, tzinfo=UTC),
        redaction_status="redacted",
        authorization_ref="synthetic-test-only-not-release-evidence",
    )


def _write(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_preflight_missing_suite_is_json_and_fail_closed(tmp_path: Path) -> None:
    result = _run(
        "--agent-id",
        AGENT_ID,
        "--suite",
        str(tmp_path / "missing-suite.json"),
    )

    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["provider_free"] is True
    assert payload["structural_eligible"] is False
    assert payload["semantic_eligible"] is False
    assert payload["release_eligible"] is False
    assert "structural_suite_file_missing" in payload["blocking_reasons"]


def test_preflight_structural_success_without_semantic_sidecar_fails_closed(
    tmp_path: Path,
) -> None:
    suite_path = tmp_path / "synthetic-suite.json"
    # Synthetic fixtures are local test data and must never be treated as
    # production authorization or release evidence.
    _write(suite_path, _suite().model_dump(mode="json"))

    result = _run(
        "--agent-id",
        AGENT_ID,
        "--suite",
        str(suite_path),
    )

    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["structural_eligible"] is True
    assert payload["semantic_eligible"] is False
    assert payload["release_eligible"] is False
    assert "semantic_evidence_missing" in payload["blocking_reasons"]


def test_preflight_complete_synthetic_evidence_passes_without_provider(
    tmp_path: Path,
) -> None:
    suite_path = tmp_path / "synthetic-suite.json"
    sidecar_path = tmp_path / "synthetic-semantic.json"
    # This is intentionally a temporary synthetic authorized-shaped fixture;
    # it is not an attestation and must not be promoted outside this test.
    _write(suite_path, _suite().model_dump(mode="json"))
    _write(sidecar_path, _semantic().model_dump(mode="json"))

    result = _run(
        "--agent-id",
        AGENT_ID,
        "--suite",
        str(suite_path),
        "--semantic-sidecar",
        str(sidecar_path),
        "--expected-agent-version",
        AGENT_VERSION,
        "--expected-runtime-plan-version",
        PLAN_VERSION,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["provider_free"] is True
    assert payload["structural_eligible"] is True
    assert payload["semantic_eligible"] is True
    assert payload["release_eligible"] is True
    assert payload["blocking_reasons"] == []


def test_preflight_reports_learning_development_sidecar_as_not_authorized(
    tmp_path: Path,
) -> None:
    suite_path = tmp_path / "synthetic-suite.json"
    sidecar_path = tmp_path / "learning-development-sidecar.json"
    _write(suite_path, _suite().model_dump(mode="json"))
    _write(
        sidecar_path,
        {
            "schema_version": "learning_runtime_semantic_sidecar.v1",
            "evidence_kind": "development_paired",
            "release_ready": False,
        },
    )

    result = _run(
        "--agent-id",
        AGENT_ID,
        "--suite",
        str(suite_path),
        "--semantic-sidecar",
        str(sidecar_path),
        "--expected-agent-version",
        AGENT_VERSION,
        "--expected-runtime-plan-version",
        PLAN_VERSION,
    )

    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["structural_eligible"] is True
    assert payload["semantic_eligible"] is False
    assert payload["release_eligible"] is False
    assert payload["blocking_reasons"] == [
        "semantic_development_evidence_not_authorized"
    ]


def test_preflight_rejects_model_only_semantic_pass(
    tmp_path: Path,
) -> None:
    suite_path = tmp_path / "synthetic-suite.json"
    sidecar_path = tmp_path / "model-semantic.json"
    _write(suite_path, _suite().model_dump(mode="json"))
    _write(
        sidecar_path,
        _semantic().model_copy(update={"judge_type": "model"}).model_dump(
            mode="json"
        ),
    )

    result = _run(
        "--agent-id",
        AGENT_ID,
        "--suite",
        str(suite_path),
        "--semantic-sidecar",
        str(sidecar_path),
        "--expected-agent-version",
        AGENT_VERSION,
        "--expected-runtime-plan-version",
        PLAN_VERSION,
    )

    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["semantic_eligible"] is False
    assert payload["release_eligible"] is False
    assert payload["blocking_reasons"] == ["semantic_judge_not_independent"]


def test_preflight_rejects_semantic_sidecar_output_hash_mismatch(
    tmp_path: Path,
) -> None:
    suite_path = tmp_path / "synthetic-suite.json"
    sidecar_path = tmp_path / "tampered-semantic.json"
    _write(suite_path, _suite().model_dump(mode="json"))
    semantic = _semantic().model_copy(
        update={"runtime_output_sha256": "f" * 64}
    )
    _write(sidecar_path, semantic.model_dump(mode="json"))

    result = _run(
        "--agent-id",
        AGENT_ID,
        "--suite",
        str(suite_path),
        "--semantic-sidecar",
        str(sidecar_path),
        "--expected-agent-version",
        AGENT_VERSION,
        "--expected-runtime-plan-version",
        PLAN_VERSION,
    )

    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["provider_free"] is True
    assert payload["semantic_eligible"] is False
    assert payload["release_eligible"] is False
    assert payload["blocking_reasons"] == [
        "semantic_output_hash_mismatch"
    ]


def test_preflight_rejects_semantic_sidecar_input_hash_mismatch(
    tmp_path: Path,
) -> None:
    suite_path = tmp_path / "synthetic-suite.json"
    sidecar_path = tmp_path / "tampered-input-semantic.json"
    suite = _suite()
    _write(suite_path, suite.model_dump(mode="json"))
    semantic = _semantic().model_copy(update={"input_sha256": "f" * 64})
    _write(sidecar_path, semantic.model_dump(mode="json"))

    result = _run(
        "--agent-id",
        AGENT_ID,
        "--suite",
        str(suite_path),
        "--semantic-sidecar",
        str(sidecar_path),
        "--expected-agent-version",
        AGENT_VERSION,
        "--expected-runtime-plan-version",
        PLAN_VERSION,
    )

    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["semantic_eligible"] is False
    assert payload["release_eligible"] is False
    assert payload["blocking_reasons"] == ["semantic_input_hash_mismatch"]


def test_preflight_version_mismatch_is_nonzero(tmp_path: Path) -> None:
    suite_path = tmp_path / "synthetic-suite.json"
    sidecar_path = tmp_path / "synthetic-semantic.json"
    _write(suite_path, _suite().model_dump(mode="json"))
    _write(sidecar_path, _semantic().model_dump(mode="json"))

    result = _run(
        "--agent-id",
        AGENT_ID,
        "--suite",
        str(suite_path),
        "--semantic-sidecar",
        str(sidecar_path),
        "--expected-agent-version",
        "stale-version",
    )

    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["structural_eligible"] is False
    assert payload["release_eligible"] is False
    assert "canary_artifact_agent_version_mismatch" in payload["blocking_reasons"]


def test_preflight_unauthorized_structural_evidence_is_nonzero(
    tmp_path: Path,
) -> None:
    suite_path = tmp_path / "synthetic-suite.json"
    _write(suite_path, _suite(authorized=False).model_dump(mode="json"))

    result = _run(
        "--agent-id",
        AGENT_ID,
        "--suite",
        str(suite_path),
    )

    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert payload["structural_eligible"] is False
    assert "canary_authorized_evidence_missing" in payload["blocking_reasons"]
