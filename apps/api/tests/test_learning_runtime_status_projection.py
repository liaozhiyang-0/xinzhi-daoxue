from __future__ import annotations

from apps.api.tests.phase3_helpers import learning_action, power_payload


def _submit_power_with_extended_wait(api, session_id: str) -> dict:
    response = api.client.post(
        "/api/v1/tasks",
        json=power_payload(
            api,
            session_id,
            student_attempt={"raw_text": "P=20", "final_answer": "20"},
        ),
    )
    assert response.status_code == 202, response.text
    return api.wait_for_task(response.json()["id"], timeout=20)


def test_learning_runtime_status_is_redacted_and_provider_free(api, app) -> None:
    app.state.learning_progress_runtime.enabled = True
    session = api.create_session()
    task = _submit_power_with_extended_wait(api, session["id"])
    action = learning_action(
        api,
        task["id"],
        "submit_attempt_revision",
        key="learning-runtime-status-0001",
        answer="P=20 W",
    )
    assert action.status_code == 200, action.text
    run_id = action.json()["runtime_run_id"]

    response = api.client.get(f"/api/v1/learning/runtime/{run_id}")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["run_kind"] == "learning_progress"
    assert payload["status"] == "completed"
    assert payload["control_scope"] == "learning_loop"
    assert payload["available_controls"] == []
    assert payload["resumable"] is False
    assert payload["node_statuses"]
    assert "request_snapshot" not in payload
    assert "student_answer" not in str(payload)
    assert "idempotency_key" not in str(payload)

    debug = api.client.get(f"/api/v1/debug/execution/{task['id']}")
    assert debug.status_code == 200, debug.text
    learning_runtime = debug.json()["learning_runtime"]
    assert learning_runtime["run_id"] == run_id
    assert learning_runtime["run_kind"] == "learning_progress"
    assert learning_runtime["status"] == "completed"
    assert learning_runtime["control_scope"] == "learning_loop"
    assert "student_answer" not in str(learning_runtime)
    assert "request_snapshot" not in str(learning_runtime)


def test_learning_runtime_status_reports_approval_wait_and_rejects_missing_run(
    api, app
) -> None:
    app.state.learning_progress_runtime.enabled = True
    session = api.create_session()
    task = _submit_power_with_extended_wait(api, session["id"])
    action = learning_action(
        api,
        task["id"],
        "submit_attempt_revision",
        key="learning-runtime-status-0002",
        answer="I changed the method but did not provide a numeric result.",
    )
    assert action.status_code == 200, action.text
    run_id = action.json()["runtime_run_id"]

    status = api.client.get(f"/api/v1/learning/runtime/{run_id}")
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "waiting_approval"
    assert status.json()["approval_required"] is True
    assert status.json()["available_controls"] == ["approve"]
    assert status.json()["resumable"] is True

    missing = api.client.get("/api/v1/learning/runtime/missing-run")
    assert missing.status_code == 404
