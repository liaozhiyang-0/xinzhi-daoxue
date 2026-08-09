from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeCheckpointRecord,
    RuntimeLaunchSnapshot,
    RuntimeNode,
)

from scripts.collect_runtime_canary import build_suite


def test_build_suite_requires_a_structurally_valid_paired_trace() -> None:
    run = AgentRun(
        run_id="run-collection",
        task_id="task-collection",
        goal="collect",
        plan=AgentRunPlan(
            plan_id="plan-collection",
            version="general-qa-v1",
            goal="collect",
            nodes=[
                RuntimeNode(
                    node_id="final",
                    node_type="terminal",
                    handler_id="runtime.final",
                )
            ],
        ),
        launch_decision=RuntimeLaunchSnapshot(
            agent_id="GENERAL_QUESTION_V1",
            mode="canary",
            source="test",
            reason="paired trace test",
        ),
    )
    checkpoints = [
        RuntimeCheckpointRecord(
            sequence=1,
            state_version=1,
            state_data=run.model_dump(mode="json"),
        ).model_dump(mode="json")
    ]

    suite = build_suite(
        agent_id="GENERAL_QUESTION_V1",
        suite_id="collection-suite",
        case_id="collection-case",
        authorization_ref="change-collection-1",
        captured_at=datetime(2026, 8, 9, tzinfo=UTC),
        agent_version="1.0",
        runtime_plan_version="general-qa-v1",
        legacy_payload={
            "agent_id": "GENERAL_QUESTION_V1",
            "status": "completed",
            "answer": "same",
        },
        runtime_payload={
            "agent_id": "GENERAL_QUESTION_V1",
            "status": "completed",
            "answer": "same",
        },
        runtime_checkpoints=checkpoints,
    )

    assert suite.evidence.kind == "authorized_paired"
    assert suite.evidence.release_ready is True
    assert suite.pairs[0].runtime_checkpoints == checkpoints


def test_build_suite_rejects_an_invalid_trace() -> None:
    with pytest.raises(ValueError, match="not release eligible"):
        build_suite(
            agent_id="GENERAL_QUESTION_V1",
            agent_version="1.0",
            runtime_plan_version="general-qa-v1",
            suite_id="invalid-suite",
            case_id="invalid-case",
            authorization_ref="change-invalid-1",
            captured_at=datetime(2026, 8, 9, tzinfo=UTC),
            legacy_payload={"status": "completed", "answer": "same"},
            runtime_payload={"status": "completed", "answer": "same"},
            runtime_checkpoints=[],
        )
