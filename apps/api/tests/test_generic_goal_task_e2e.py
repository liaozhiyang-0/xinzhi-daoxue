from __future__ import annotations

import time
from typing import Any

from app.main import create_app
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
