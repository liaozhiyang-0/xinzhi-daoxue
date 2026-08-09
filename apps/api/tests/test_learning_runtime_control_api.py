from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import pytest
from app.contracts.learning import (
    LearningActionResponse,
    LearningRuntimeStatusRead,
)
from app.models import AuditLogModel
from app.services.learning_loop import LearningRuntimeControlOutcome
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select


def _status(
    *,
    run_id: str = "learning-control-run",
    status: str = "waiting_approval",
    state_version: int = 7,
) -> LearningRuntimeStatusRead:
    return LearningRuntimeStatusRead(
        run_id=run_id,
        task_id="learning-control-task",
        runtime_id="TEACHING_INTERACTION_V1",
        run_kind="teaching_interaction",
        status=status,
        state_version=state_version,
        goal="review a teaching interaction",
        success_criteria=["learning_feedback_verified"],
        required_capabilities=["teaching.feedback.apply"],
        node_statuses=[],
        available_controls={
            "running": ["pause"],
            "paused": ["resume"],
            "waiting_input": ["input"],
            "waiting_approval": ["approve"],
        }.get(status, []),
        approval_required=status == "waiting_approval",
        resumable=status in {"paused", "waiting_input", "waiting_approval"},
    )


class _FakeLearningLoop:
    def __init__(self, statuses: Sequence[LearningRuntimeStatusRead]) -> None:
        self.statuses = list(statuses)
        self.approve_calls: list[dict[str, Any]] = []
        self.control_calls: list[dict[str, Any]] = []

    async def runtime_status(
        self, _session: Any, _run_id: str, *, user_id: str
    ) -> LearningRuntimeStatusRead:
        assert user_id == ""
        if len(self.statuses) > 1:
            return self.statuses.pop(0)
        return self.statuses[0]

    async def approve_runtime_interaction(
        self,
        _session: Any,
        run_id: str,
        *,
        user_id: str,
        expected_state_version: int | None,
    ) -> LearningActionResponse:
        self.approve_calls.append(
            {
                "run_id": run_id,
                "user_id": user_id,
                "expected_state_version": expected_state_version,
            }
        )
        return LearningActionResponse(
            interaction_id="learning-control-interaction",
            action="request_more_hint",
            status="completed",
            message="approved",
            runtime_run_id=run_id,
            runtime_status="completed",
        )

    async def control_runtime_interaction(
        self,
        _session: Any,
        run_id: str,
        *,
        action: str,
        user_id: str,
        expected_state_version: int | None,
        data: dict[str, Any],
        idempotency_key: str,
    ) -> LearningRuntimeControlOutcome:
        self.control_calls.append(
            {
                "run_id": run_id,
                "action": action,
                "user_id": user_id,
                "expected_state_version": expected_state_version,
                "data": data,
                "idempotency_key": idempotency_key,
            }
        )
        return LearningRuntimeControlOutcome(
            run_id=run_id,
            action=action,  # type: ignore[arg-type]
            status="paused" if action == "pause" else "completed",
            state_version=8,
        )


def test_learning_runtime_controls_are_redacted_and_provider_free(
    app: FastAPI, client: TestClient
) -> None:
    fake = _FakeLearningLoop([_status()])
    app.state.learning_loop = fake

    response = client.get(
        "/api/v1/learning/runtime/learning-control-run/controls"
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provider_called"] is False
    assert payload["control_scope"] == "learning_loop"
    assert payload["available_controls"] == ["approve"]
    controls = {item["action"]: item for item in payload["controls"]}
    assert controls["approve"]["available"] is True
    assert controls["pause"]["reason_code"] == (
        "learning_runtime_pause_not_available"
    )
    assert controls["resume"]["reason_code"] == (
        "learning_runtime_resume_not_available"
    )
    assert controls["input"]["reason_code"] == (
        "learning_runtime_input_not_available"
    )
    assert "request_snapshot" not in str(payload)
    assert fake.approve_calls == []


@pytest.mark.parametrize(
    ("action", "reason_code"),
    [
        ("pause", "learning_runtime_pause_not_available"),
        ("resume", "learning_runtime_resume_not_available"),
        ("input", "learning_runtime_input_not_available"),
    ],
)
def test_learning_runtime_control_rejects_unsupported_actions_and_audits_reason(
    app: FastAPI,
    client: TestClient,
    action: str,
    reason_code: str,
) -> None:
    fake = _FakeLearningLoop([_status()])
    app.state.learning_loop = fake

    response = client.post(
        "/api/v1/learning/runtime/learning-control-run/control",
        json={
            "action": action,
            "expected_state_version": 7,
            "data": {"answer": "more"} if action == "input" else {},
        },
    )

    assert response.status_code == 409, response.text
    details = response.json()["error"]["details"]
    assert details["action"] == action
    assert details["reason_code"] == reason_code
    assert details["status"] == "waiting_approval"
    assert details["state_version"] == 7
    assert details["provider_called"] is False
    assert fake.approve_calls == []
    assert fake.control_calls == []

    async def read_audit() -> list[AuditLogModel]:
        async with app.state.session_factory() as db:
            return list(
                await db.scalars(
                    select(AuditLogModel).where(
                        AuditLogModel.action == "learning_runtime.control_rejected"
                    )
                )
            )

    audit_rows = asyncio.run(read_audit())
    assert len(audit_rows) == 1
    assert audit_rows[0].details["reason_code"] == reason_code
    assert audit_rows[0].details["run_id"] == "learning-control-run"


def test_learning_runtime_control_delegates_only_approve_and_preserves_result_contract(
    app: FastAPI, client: TestClient
) -> None:
    fake = _FakeLearningLoop([_status(), _status(status="completed", state_version=9)])
    app.state.learning_loop = fake

    response = client.post(
        "/api/v1/learning/runtime/learning-control-run/control",
        json={"action": "approve", "expected_state_version": 7},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provider_called"] is False
    assert payload["accepted"] is True
    assert payload["action"] == "approve"
    assert payload["status"] == "completed"
    assert payload["state_version"] == 9
    assert payload["result"]["action"] == "request_more_hint"
    assert payload["result"]["runtime_run_id"] == "learning-control-run"
    assert fake.approve_calls == [
        {
            "run_id": "learning-control-run",
            "user_id": "",
            "expected_state_version": 7,
        }
    ]


@pytest.mark.parametrize(
    ("action", "initial_status", "updated_status", "data"),
    [
        ("pause", "running", "paused", {}),
        ("resume", "paused", "completed", {}),
        ("input", "waiting_input", "completed", {"answer": "clarify"}),
    ],
)
def test_learning_runtime_control_delegates_durable_controls(
    app: FastAPI,
    client: TestClient,
    action: str,
    initial_status: str,
    updated_status: str,
    data: dict[str, Any],
) -> None:
    fake = _FakeLearningLoop(
        [
            _status(status=initial_status),
            _status(status=updated_status, state_version=8),
        ]
    )
    app.state.learning_loop = fake

    response = client.post(
        "/api/v1/learning/runtime/learning-control-run/control",
        json={
            "action": action,
            "expected_state_version": 7,
            "data": data,
            "idempotency_key": f"learning-{action}-0001",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provider_called"] is False
    assert payload["accepted"] is True
    assert payload["action"] == action
    assert payload["status"] == updated_status
    assert payload["state_version"] == 8
    assert payload["result"] is None
    assert fake.control_calls == [
        {
            "run_id": "learning-control-run",
            "action": action,
            "user_id": "",
            "expected_state_version": 7,
            "data": data,
            "idempotency_key": f"learning-{action}-0001",
        }
    ]


def test_learning_runtime_control_requires_operator_when_auth_is_enabled(
    app: FastAPI, client: TestClient
) -> None:
    app.state.settings.auth_required = True
    fake = _FakeLearningLoop([_status(status="running")])
    app.state.learning_loop = fake

    response = client.post(
        "/api/v1/learning/runtime/learning-control-run/control",
        json={"action": "pause", "expected_state_version": 7},
    )

    assert response.status_code in {401, 403}
    assert fake.control_calls == []
