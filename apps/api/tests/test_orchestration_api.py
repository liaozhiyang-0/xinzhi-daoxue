from __future__ import annotations

from time import monotonic, sleep

from fastapi.testclient import TestClient


def test_capabilities_and_workflow_status(client: TestClient) -> None:
    capabilities = client.get("/api/v1/capabilities")
    workflows = client.get("/api/v1/workflows")

    assert capabilities.status_code == 200
    assert capabilities.json()["supervisor"] == "XZD_SUPERVISOR"
    showcase_ids = {
        item["id"] for item in capabilities.json()["workspace_features"]
    }
    assert {
        "lesson_prep",
        "assignment_review",
        "student_learning_path",
        "academic_search",
        "knowledge_governance",
        "solve_problem",
    } <= showcase_ids
    assert len(workflows.json()) >= 9
    assert {item["execution_mode"] for item in workflows.json()} <= {
        "local",
        "disabled",
    }
    lesson_prep = next(
        item
        for item in workflows.json()
        if item["agent_id"] == "TEACH_01_LESSON_PREP_V1"
    )
    assert lesson_prep["execution_mode"] == "local"
    assert lesson_prep["local_ready"] is True
    assert lesson_prep["available"] is True
    general = next(
        item
        for item in workflows.json()
        if item["agent_id"] == "GENERAL_QUESTION_V1"
    )
    assert general["execution_mode"] == "local"
    assert general["local_ready"] is True
    assert general["available"] is True


def test_chat_reuses_existing_non_blocking_task_flow(client: TestClient) -> None:
    created = client.post(
        "/api/v1/chat",
        json={"message": "为什么电容电压不能突变？", "user_id": "user-chat"},
    )

    assert created.status_code == 202, created.text
    submission = created.json()
    assert submission["trace_id"].startswith("trace_")
    deadline = monotonic() + 5
    while monotonic() < deadline:
        result = client.get(submission["result_url"])
        assert result.status_code == 200
        if result.json()["answer_text"]:
            break
        sleep(0.02)
    payload = result.json()
    assert payload["course"] == "CT"
    assert payload["intent"] == "explain_concept"
    trace = client.get(f"/api/v1/debug/traces/{submission['trace_id']}")
    assert trace.status_code == 200
    assert trace.json()["selected_agent"]
