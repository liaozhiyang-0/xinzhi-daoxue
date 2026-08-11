from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from app.runtime.semantic_evidence import payload_sha256

from scripts.collect_learning_runtime_semantic_sidecar import (
    collect_sidecar,
    main,
)

CASE_ID = "teaching_request_more_hint"
IDENTITY = {
    "capability_id": "TEACHING_INTERACTION_V1",
    "agent_version": "learning-agent-v1",
    "runtime_plan_version": "teaching-interaction-v1",
}


def _pair_package() -> dict[str, object]:
    return {
        "schema_version": "learning_runtime_paired_evidence.v1",
        "evidence_kind": "development_paired",
        "case_id": CASE_ID,
        "capability_identity": {
            **IDENTITY,
            "source": "declared_runtime_contract",
            "authorization_status": "not_authorized",
        },
        "structural_checks": {"passed": True, "reasons": []},
        "release_ready": False,
    }


def _judgement(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "dimensions": {
            "task_fulfillment": 1.0,
            "factual_correctness": 0.9,
            "evidence_faithfulness": None,
            "safety": 1.0,
        },
        "decision": "pass",
        "judge_type": "human",
        "rubric_version": "learning-runtime-semantic-v1",
        "reviewer_ref": "review-123",
        "reviewed_at": "2026-08-12T08:00:00+08:00",
        "redaction_status": "redacted",
        "authorization_ref": "review-auth-123",
    }
    value.update(updates)
    return value


def test_learning_sidecar_hashes_payloads_and_never_serializes_them() -> None:
    input_payload = {"prompt": "private student prompt"}
    outputs = {
        "legacy": {"answer": "legacy private answer"},
        "runtime": {"answer": "runtime private answer"},
    }
    report = collect_sidecar(
        pair_package=_pair_package(),
        inputs={CASE_ID: input_payload},
        outputs={CASE_ID: outputs},
        judgements={CASE_ID: _judgement()},
        suite_id="learning-dev-suite-001",
        agent_id=IDENTITY["capability_id"],
        agent_version=IDENTITY["agent_version"],
        runtime_plan_version=IDENTITY["runtime_plan_version"],
    )

    evidence = report["cases"][0]
    assert evidence["input_sha256"] == payload_sha256(input_payload)
    assert evidence["legacy_output_sha256"] == payload_sha256(outputs["legacy"])
    assert evidence["runtime_output_sha256"] == payload_sha256(
        outputs["runtime"]
    )
    assert report["release_ready"] is False
    assert report["semantic_release_eligible"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    assert "private student prompt" not in serialized
    assert "legacy private answer" not in serialized
    assert "runtime private answer" not in serialized


def test_learning_sidecar_rejects_identity_mismatch() -> None:
    with pytest.raises(ValueError, match="capability identity"):
        collect_sidecar(
            pair_package=_pair_package(),
            inputs={CASE_ID: {}},
            outputs={CASE_ID: {"legacy": {}, "runtime": {}}},
            judgements={CASE_ID: _judgement()},
            suite_id="learning-dev-suite-001",
            agent_id="LEARNING_PROGRESS_V1",
            agent_version=IDENTITY["agent_version"],
            runtime_plan_version=IDENTITY["runtime_plan_version"],
        )


def test_learning_sidecar_cli_writes_only_redacted_evidence(tmp_path: Path) -> None:
    pair_path = tmp_path / "pair.json"
    inputs_path = tmp_path / "inputs.json"
    outputs_path = tmp_path / "outputs.json"
    judgements_path = tmp_path / "judgements.json"
    output_path = tmp_path / "sidecar.json"
    pair_path.write_text(json.dumps(_pair_package()), encoding="utf-8")
    inputs_path.write_text(
        json.dumps({CASE_ID: {"prompt": "private"}}), encoding="utf-8"
    )
    outputs_path.write_text(
        json.dumps(
            {
                CASE_ID: {
                    "legacy": {"answer": "legacy"},
                    "runtime": {"answer": "runtime"},
                }
            }
        ),
        encoding="utf-8",
    )
    judgements_path.write_text(
        json.dumps({CASE_ID: _judgement()}), encoding="utf-8"
    )

    result = main(
        argparse.Namespace(
            pair_package=pair_path,
            inputs=inputs_path,
            outputs=outputs_path,
            judgements=judgements_path,
            suite_id="learning-dev-suite-001",
            agent_id=IDENTITY["capability_id"],
            agent_version=IDENTITY["agent_version"],
            runtime_plan_version=IDENTITY["runtime_plan_version"],
            output=output_path,
        )
    )

    assert result == 0
    rendered = output_path.read_text(encoding="utf-8")
    assert "private" not in rendered
    assert json.loads(rendered)["release_ready"] is False


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("redaction_status", "unknown", "must be redacted"),
        ("reviewed_at", "2026-08-12T08:00:00", "must include a timezone"),
    ],
)
def test_learning_sidecar_rejects_unreviewable_judgement(
    field: str, value: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        collect_sidecar(
            pair_package=_pair_package(),
            inputs={CASE_ID: {}},
            outputs={CASE_ID: {"legacy": {}, "runtime": {}}},
            judgements={CASE_ID: _judgement(**{field: value})},
            suite_id="learning-dev-suite-001",
            agent_id=IDENTITY["capability_id"],
            agent_version=IDENTITY["agent_version"],
            runtime_plan_version=IDENTITY["runtime_plan_version"],
        )
