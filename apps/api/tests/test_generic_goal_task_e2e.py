from __future__ import annotations

import time
from typing import Any

from app.main import create_app
from app.runtime import (
    AgentRun,
    RuntimeHandlerDescriptor,
    RuntimeNode,
    RuntimeObservation,
)
from app.services.runtime_goal_intake import RuntimeGoalIntakePolicy
from fastapi.testclient import TestClient


def _wait_for_terminal(client: TestClient, task_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200, response.text
        latest = response.json()
        if latest["status"] in {"completed", "failed", "cancelled"}:
            return latest
        time.sleep(0.02)
    raise AssertionError(f"task did not become terminal: {latest}")


def _wait_for_status(
    client: TestClient, task_id: str, expected_status: str
) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200, response.text
        latest = response.json()
        if latest["status"] == expected_status:
            return latest
        if latest["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.02)
    raise AssertionError(
        f"task did not reach {expected_status}: {latest}"
    )


def test_task_api_executes_explicit_generic_goal_with_read_only_tool(settings) -> None:
    """A Task can opt into a declarative plan without a fixed business flow."""

    settings.agent_runtime_shadow_enabled = True
    with TestClient(create_app(settings)) as client:
        session_response = client.post(
            "/api/v1/sessions",
            json={
                "user_id": "user-test",
                "course_id": "CT",
                "title": "generic goal runtime",
            },
        )
        assert session_response.status_code == 201, session_response.text
        session_id = session_response.json()["id"]
        response = client.post(
            "/api/v1/tasks",
            json={
                "session_id": session_id,
                "user_id": "user-test",
                "user_role": "admin",
                "course_id": "CT",
                "intent": "general_qa",
                "canonical_input": {"text": "Calculate two plus three."},
                "options": {
                    "debug_agent_id": "GENERAL_QUESTION_V1",
                    "runtime_agent_id": "GENERAL_QUESTION_V1",
                    "runtime_goal_runtime": {
                        "execute": True,
                        "goal": {
                            "objective": "Calculate a declared arithmetic result.",
                            "success_criteria": ["calculator returns a value"],
                            "required_capabilities": ["tool.calculator"],
                        },
                        "node_inputs": {
                            "goal.step.1.tool-calculator": {"expression": "2+3"}
                        },
                    },
                },
            },
        )
        assert response.status_code == 202, response.text
        task_id = response.json()["id"]

        task = _wait_for_terminal(client, task_id)
        assert task["status"] == "completed"
        assert task["agent_id"] == "GENERAL_QUESTION_V1"
        assert task["result_content"]["provider"] == "runtime"
        assert task["result_content"]["answer"] == "5"
        assert task["result_content"]["structured_result"]["node_statuses"] == {
            "goal.step.1.tool-calculator": "succeeded"
        }

        execution_response = client.get(f"/api/v1/debug/execution/{task_id}")
        assert execution_response.status_code == 200, execution_response.text
        execution = execution_response.json()
        runtime = execution["runtime"]
        assert runtime["plan_version"] == "goal-runtime-v1.r0"
        assert runtime["nodes"][0]["handler_id"] == "tool.calculator"
        assert runtime["nodes"][0]["observation"]["facts"]["output"] == 5
        assert runtime["observability"]["timing"]["completed_node_elapsed_ms"] >= 0

        events_response = client.get(f"/api/v1/tasks/{task_id}/events")
        assert events_response.status_code == 200, events_response.text
        runtime_events = [
            event
            for event in events_response.json()
            if event["event_data"].get("data", {}).get("runtime_event") in {
                "node_started",
                "node_completed",
            }
        ]
        assert [
            event["event_data"]["data"]["runtime_event"]
            for event in runtime_events
        ] == ["node_started", "node_completed"]
        assert runtime_events[-1]["event_data"]["data"]["node_elapsed_ms"] is not None


def test_task_api_pauses_and_resumes_explicit_goal_after_approval(settings) -> None:
    """An allowlisted privileged Goal node uses the durable Task approval API."""

    settings.agent_runtime_shadow_enabled = True
    app = create_app(settings)

    async def approved_handler(
        _run: AgentRun, node: RuntimeNode
    ) -> RuntimeObservation:
        return RuntimeObservation(
            node_id=node.node_id,
            facts={"output": "approved goal completed"},
        )

    with TestClient(app) as client:
        app.state.runtime_handler_registry.register(
            RuntimeHandlerDescriptor(
                handler_id="tool.approved_fixture",
                kind="tool",
                requires_approval=True,
                side_effecting=True,
                replay_safe=False,
            ),
            approved_handler,
        )
        generic_runtime = app.state.task_runner.generic_goal_runtime
        assert generic_runtime is not None
        generic_runtime.intake_policy = RuntimeGoalIntakePolicy.from_config(
            "GENERAL_QUESTION_V1=tool.approved_fixture"
        )
        session_response = client.post(
            "/api/v1/sessions",
            json={
                "user_id": "user-approval-test",
                "course_id": "CT",
                "title": "generic goal approval",
            },
        )
        assert session_response.status_code == 201, session_response.text
        response = client.post(
            "/api/v1/tasks",
            json={
                "session_id": session_response.json()["id"],
                "user_id": "user-approval-test",
                "user_role": "admin",
                "course_id": "CT",
                "intent": "general_qa",
                "canonical_input": {"text": "Run the approved goal."},
                "options": {
                    "debug_agent_id": "GENERAL_QUESTION_V1",
                    "runtime_agent_id": "GENERAL_QUESTION_V1",
                    "runtime_goal_runtime": {
                        "execute": True,
                        "goal": {
                            "objective": "Execute one approved capability.",
                            "success_criteria": ["approval is recorded"],
                            "required_capabilities": ["tool.approved_fixture"],
                        },
                    },
                },
            },
        )
        assert response.status_code == 202, response.text
        task_id = response.json()["id"]

        waiting = _wait_for_status(client, task_id, "waiting_review")
        approval_response = client.post(
            f"/api/v1/tasks/{task_id}/approve",
            json={"decision": "approved", "reason": "test authorization"},
        )
        assert approval_response.status_code == 200, approval_response.text
        assert approval_response.json()["status"] == "queued"

        completed = _wait_for_terminal(client, task_id)
        assert completed["status"] == "completed"
        assert completed["result_content"]["answer"] == "approved goal completed"

        execution = client.get(f"/api/v1/debug/execution/{task_id}").json()
        assert execution["runtime"]["status"] == "completed"
        assert execution["runtime"]["nodes"][0]["status"] == "succeeded"
        assert waiting["status"] == "waiting_review"
        events = client.get(f"/api/v1/tasks/{task_id}/events").json()
        assert any(
            event["event_data"].get("data", {}).get("runtime_event")
            == "approval_required"
            for event in events
        )
