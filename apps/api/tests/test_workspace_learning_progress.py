from __future__ import annotations

from apps.api.tests.phase3_helpers import submit_power


def test_workspace_exposes_current_task_and_evidence_controls(api) -> None:
    response = api.client.get("/workspace")
    assert response.status_code == 200
    html = response.text
    root = __import__("pathlib").Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )
    for text in (
        'class="workspace-page"',
        'id="student-form"',
        'id="runtime-task-controls"',
        'id="context-evidence"',
    ):
        assert text in html
    assert "renderEvidence(" in script
    assert "retryCurrentTask" in script
    assert "尝试历史" not in html
    assert "待复习" not in html
    assert "内部置信度" not in html
    assert "真实掌握概率" not in html


def test_p3_20_direct_answer_does_not_create_mastered_attempt(api) -> None:
    session = api.create_session()
    task = submit_power(api, session["id"], mode="direct_answer")
    assert task["result_content"]["metrics"]["additional_model_calls"] == 0
    attempts = api.client.get(
        "/api/v1/learning/attempts",
        params={"user_id": "user-test", "source_task_id": task["id"]},
    )
    assert attempts.status_code == 200
    assert attempts.json() == []
    states = api.client.get(
        "/api/v1/learning/states",
        params={"user_id": "user-test", "course_id": "CT"},
    )
    assert states.status_code == 200
    assert states.json() == []
