from __future__ import annotations

import asyncio

from app.models import AgentRunModel
from app.repositories import AgentRunRepository
from app.runtime import AgentRun

from apps.api.tests.phase3_helpers import learning_action, submit_power


def test_phase3_revision_uses_durable_learning_progress_runtime(api, app) -> None:
    app.state.learning_progress_runtime.enabled = True
    session = api.create_session()
    task = submit_power(
        api,
        session["id"],
        student_attempt={"raw_text": "P=20", "final_answer": "20"},
    )

    response = learning_action(
        api,
        task["id"],
        "submit_attempt_revision",
        key="learning-progress-runtime-0001",
        answer="P=20 W",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["runtime_status"] == "completed"
    assert body["runtime_run_id"]
    assert body["attempt"]["attempt_sequence"] == 2

    async def load_runtime() -> tuple[AgentRunModel, AgentRun]:
        async with app.state.session_factory() as db:
            model = await db.get(AgentRunModel, body["runtime_run_id"])
            assert model is not None
            restored = await AgentRunRepository(db).restore(model.id)
            assert restored is not None
            return model, restored

    runtime_model, restored = asyncio.run(load_runtime())
    assert runtime_model.run_kind == "learning_progress"
    assert runtime_model.plan_version == "learning-progress-v1"
    assert runtime_model.status == "completed"
    assert restored.nodes["learning.progress.observe"].status.value == "succeeded"
    assert restored.nodes["learning.progress.apply"].status.value == "succeeded"
    assert restored.nodes["learning.progress.verify"].status.value == "succeeded"
    assert restored.nodes["learning.progress.approval"].status.value == "skipped"

    events = api.client.get(f"/api/v1/tasks/{task['id']}/events").json()
    runtime_events = [
        item
        for item in events
        if item["event_data"]["data"].get("runtime_run_id")
        == body["runtime_run_id"]
    ]
    assert runtime_events
    assert [item["sequence"] for item in runtime_events] == sorted(
        item["sequence"] for item in runtime_events
    )


def test_phase3_runtime_pauses_for_manual_review_and_resumes(api, app) -> None:
    app.state.learning_progress_runtime.enabled = True
    session = api.create_session()
    task = submit_power(
        api,
        session["id"],
        student_attempt={"raw_text": "P=20", "final_answer": "20"},
    )

    response = learning_action(
        api,
        task["id"],
        "submit_attempt_revision",
        key="learning-progress-runtime-0002",
        answer="I changed the method but did not provide a numeric result.",
    )
    assert response.status_code == 200, response.text
    accepted = response.json()
    assert accepted["status"] == "accepted"
    assert accepted["runtime_status"] == "waiting_approval"
    assert accepted["approval_required"] is True

    approved = api.client.post(
        f"/api/v1/learning/runtime/{accepted['runtime_run_id']}/approve",
        json={},
    )
    assert approved.status_code == 200, approved.text
    completed = approved.json()
    assert completed["status"] == "completed"
    assert completed["runtime_status"] == "completed"
    assert completed["approval_required"] is False
