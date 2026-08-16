from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.api.v1 import tasks as tasks_api
from app.api.v1.tasks import _project_task_runtime_controls
from app.services.auth_service import Principal


def _runtime(
    *,
    status: str,
    run_kind: str = "runtime",
    control_request: str = "",
) -> SimpleNamespace:
    return SimpleNamespace(
        id="runtime-workspace",
        run_kind=run_kind,
        status=status,
        state_version=7,
        control_request=control_request,
    )


def test_workspace_runtime_control_projection_is_redacted_and_state_aware() -> None:
    projection = _project_task_runtime_controls(
        "task-workspace", _runtime(status="running")  # type: ignore[arg-type]
    )

    assert projection.task_id == "task-workspace"
    assert projection.runtime_run_id == "runtime-workspace"
    assert projection.state_version == 7
    assert [(item.action, item.available) for item in projection.controls] == [
        ("pause", True),
        ("resume", False),
        ("approve", False),
        ("input", False),
    ]
    assert "control_data" not in projection.model_dump()
    assert "request_snapshot" not in projection.model_dump()


def test_workspace_runtime_control_projection_waits_for_the_exact_handoff() -> None:
    input_projection = _project_task_runtime_controls(
        "task-input", _runtime(status="waiting_input")  # type: ignore[arg-type]
    )
    approval_projection = _project_task_runtime_controls(
        "task-approval", _runtime(status="waiting_approval")  # type: ignore[arg-type]
    )

    assert [item.action for item in input_projection.controls if item.available] == [
        "input"
    ]
    assert [item.action for item in approval_projection.controls if item.available] == [
        "approve"
    ]


def test_workspace_runtime_control_projection_fails_closed() -> None:
    missing = _project_task_runtime_controls("task-missing", None)
    pending = _project_task_runtime_controls(
        "task-pending",
        _runtime(status="running", control_request="pause"),  # type: ignore[arg-type]
    )
    unsupported = _project_task_runtime_controls(
        "task-child",
        _runtime(status="paused", run_kind="subagent"),  # type: ignore[arg-type]
    )

    assert all(not item.available for item in missing.controls)
    assert all(item.reason_code == "runtime_not_started" for item in missing.controls)
    pending_pause = next(
        item for item in pending.controls if item.action == "pause"
    )
    assert not pending_pause.available
    assert pending_pause.reason_code == "runtime_control_pending"
    assert all(not item.available for item in unsupported.controls)


def test_pending_plan_proposal_is_not_exposed_as_side_effect_approval() -> None:
    proposal = SimpleNamespace(
        id="proposal-workspace",
        status="pending",
        state_version=9,
        base_iteration=0,
        target_iteration=1,
        reason_codes=["bounded_replan"],
        affected_node_ids=["execute"],
    )
    projection = _project_task_runtime_controls(
        "task-proposal",
        _runtime(status="waiting_approval"),  # type: ignore[arg-type]
        plan_proposal=proposal,
    )

    assert projection.control_scope == "runtime_plan_proposal"
    assert projection.plan_proposal is not None
    assert projection.plan_proposal.proposal_id == "proposal-workspace"
    assert all(not item.available for item in projection.controls)
    assert all(
        item.reason_code == "runtime_plan_proposal_requires_explicit_decision"
        for item in projection.controls
    )


def test_task_runtime_controls_endpoint_uses_public_projection(
    api: Any, app: Any
) -> None:
    app.state.task_engine.runtime_lifecycle.enabled = True
    session = api.create_session()
    task = api.create_task(session["id"])
    completed = api.wait_for_task(task["id"])
    assert completed["status"] == "completed"

    response = api.client.get(f"/api/v1/tasks/{task['id']}/runtime-controls")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task["id"]
    assert payload["run_kind"] == "runtime"
    assert payload["status"] == "completed"
    assert all(not item["available"] for item in payload["controls"])
    assert "control_data" not in payload
    assert "request_snapshot" not in payload


@pytest.mark.asyncio
async def test_teacher_runtime_controls_can_project_learner_owned_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = SimpleNamespace(id="task-learner", user_id="guest-user")
    get_task = AsyncMock(return_value=task)

    class _Query:
        def __init__(self, _db: object) -> None:
            pass

        async def get(self, _task_id: str) -> SimpleNamespace:
            return await get_task(_task_id)

    monkeypatch.setattr(tasks_api, "TaskQueryService", _Query)
    teacher = Principal(
        authenticated=True,
        user_id="teacher-user",
        role="teacher",
    )

    projected = await tasks_api._get_runtime_control_task(object(), task.id, teacher)

    assert projected is task
    get_task.assert_awaited_once_with(task.id)


def test_workspace_markup_uses_public_runtime_control_projection() -> None:
    static_root = Path(__file__).parents[1] / "app" / "static" / "debug"
    html = (static_root / "workspace.html").read_text(encoding="utf-8")
    script = (static_root / "workspace.js").read_text(encoding="utf-8")

    assert 'id="runtime-task-controls"' in html
    assert 'id="runtime-task-pause"' in html
    assert 'id="runtime-task-resume"' in html
    assert 'id="runtime-task-approve"' in html
    assert 'id="runtime-task-input-form"' in html
    assert 'id="runtime-task-reject-proposal"' in html
    assert "/runtime-controls" in script
    assert "runtime-plan-proposals/" in script
    assert 'decision: action === "approve" ? "approved" : "rejected"' in script
    assert "function runtimeApprovalAllowed()" in script
    assert '["teacher", "admin"]' in script
    assert '"RESEARCH_02_ACADEMIC_WRITING_V1"' in script
    assert "/api/v1/learning/runtime/" in script
    assert 'control_scope === "learning_loop"' in script
    assert '...(action === "input" ? { data: payload?.data || {} } : {})' in script
    assert "result.runtime_run_id" in script
    assert "/debug/execution" not in script
    assert "expected_state_version: runtimeTaskControls?.state_version" in script
    assert "runtimeTaskControlAvailable(action)" in script


def test_workspace_sse_reconnect_keeps_cursor_and_reconciles_controls() -> None:
    static_root = Path(__file__).parents[1] / "app" / "static" / "debug"
    script = "\n".join(
        (
            (static_root / "workspace.js").read_text(encoding="utf-8"),
            (static_root / "workspace-task-transport.js").read_text(
                encoding="utf-8"
            ),
        )
    )
    error_block = script.split("events.onerror = () => {", 1)[1].split("};", 1)[0]

    assert "Last-Event-ID" in error_block
    assert "events.close()" not in error_block
    assert "reconnectPollTimer = setInterval" in error_block
    assert "refreshRuntimeTaskControls(id)" in error_block


def test_workspace_reconciles_controls_while_sse_is_open() -> None:
    static_root = Path(__file__).parents[1] / "app" / "static" / "debug"
    script = (static_root / "workspace-task-transport.js").read_text(
        encoding="utf-8"
    )

    assert "let controlRefreshTimer = null" in script
    assert "controlRefreshTimer = setInterval" in script
    assert "clearInterval(controlRefreshTimer)" in script
