from pathlib import Path


def test_task_engine_has_no_agent_literal() -> None:
    source = (
        Path(__file__).parents[1]
        / "app"
        / "services"
        / "runtime_task_engine.py"
    ).read_text(encoding="utf-8")

    assert "ACADEMIC_PROBLEM_SOLVER" not in source
    assert "self.runtime_execution.execute" in source


def test_route_is_persisted_before_runtime_submission(api, client) -> None:
    session = api.create_session()
    payload = api.task_payload(session["id"])
    payload.update(
        {
            "scene": "learning",
            "course_id": "AE",
            "intent": "general_qa",
            "canonical_input": {"question": "什么是负反馈"},
        }
    )
    response = client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 202
    task = response.json()
    assert task["agent_id"] == "LEARN_01_KNOWLEDGE_QA_V1"
    assert task["route_status"] == "selected"
