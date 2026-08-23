from app.contracts import AgentEventType
from app.models import AgentRunModel
from app.repositories import AgentRunRepository
from app.runtime import AgentRun, AgentRunPlan, RuntimeNode
from app.services.event_service import append_task_event


def test_execution_debug_uses_persisted_task_summary_and_redacts(api, client) -> None:
    session = api.create_session()
    created = api.create_task(session["id"])
    task = api.wait_for_task(created["id"])
    assert task["status"] == "completed"

    response = client.get(f"/api/v1/debug/execution/{task['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["task"]["id"] == task["id"]
    assert data["overview"]["title"]
    assert data["retrieval"]["rag_mode"] in {
        "grounded_generation",
        "method_reference",
        "reference_only",
        "no_rag",
    }
    assert data["performance"]["waterfall"]
    serialized = response.text.casefold()
    assert "authorization" not in serialized
    assert "api_secret" not in serialized
    assert data["runtime"]["handoff"] == {}


def test_execution_debug_does_not_expose_raw_student_input(api, client) -> None:
    session = api.create_session()
    private_text = "student-private-debug-input-7e98"
    response = client.post(
        "/api/v1/tasks",
        json={
            "session_id": session["id"],
            "user_id": "user-test",
            "user_role": "student",
            "scene": "solving",
            "course_id": "CT",
            "intent": "solve_problem",
            "canonical_input": {
                "text": private_text,
                "student_attempt": private_text,
            },
            "attachments": [],
            "context_refs": [],
            "options": {},
        },
    )
    assert response.status_code == 202, response.text
    task = api.wait_for_task(response.json()["id"])

    debug = client.get(f"/api/v1/debug/execution/{task['id']}")

    assert debug.status_code == 200, debug.text
    assert private_text not in debug.text
    assert debug.json()["request"]["raw_input"]["text"] == "[redacted]"


def test_execution_debug_redacts_event_prompts_and_runtime_derived_input(
    api, app, client
) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])["id"])
    private_text = "student-private-event-prompt-4d21"

    async def persist_private_event() -> None:
        async with app.state.session_factory() as db:
            await append_task_event(
                db,
                task["id"],
                AgentEventType.AGENT_INPUT_REQUIRED,
                agent_id=task["agent_id"],
                data={
                    "user_prompt": private_text,
                    "detail": private_text,
                    "raw_input": private_text,
                },
            )
            await db.commit()

    client.portal.call(persist_private_event)

    debug = client.get(f"/api/v1/debug/execution/{task['id']}")

    assert debug.status_code == 200, debug.text
    assert private_text not in debug.text
    event = debug.json()["events"][-1]
    event_data = event["data"]["data"]
    assert event_data["user_prompt"] == "[redacted]"
    assert event_data["detail"] == "[redacted]"
    assert event_data["raw_input"] == "[redacted]"


def test_execution_debug_exposes_persisted_runtime_handoff_with_redaction(
    api, app, client
) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])["id"])

    async def persist_handoff() -> None:
        async with app.state.session_factory() as db:
            db.add(
                AgentRunModel(
                    id="debug-runtime-handoff",
                    task_id=task["id"],
                    agent_id=task["agent_id"],
                    run_kind="runtime",
                    provider=task["provider"],
                    status="failed",
                    control_data={
                        "runtime_handoff": {
                            "status": "legacy_fallback",
                            "runtime_status": "failed",
                            "bypass_legacy_execution": False,
                            "fallback_reason": "runtime_execution_failed",
                            "token": "do-not-return",
                            "nested": {"api_key": "nested-secret"},
                        }
                    },
                )
            )
            await db.commit()

    client.portal.call(persist_handoff)

    response = client.get(f"/api/v1/debug/execution/{task['id']}")
    assert response.status_code == 200
    handoff = response.json()["runtime"]["handoff"]
    assert handoff["status"] == "legacy_fallback"
    assert handoff["runtime_status"] == "failed"
    assert handoff["bypass_legacy_execution"] is False
    assert handoff["fallback_reason"] == "runtime_execution_failed"
    assert handoff["token"] == "[redacted]"
    assert handoff["nested"]["api_key"] == "[redacted]"
    assert "do-not-return" not in response.text
    assert "nested-secret" not in response.text


def test_execution_debug_exposes_checkpoint_event_correlation(
    api, app, client
) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])["id"])

    async def persist_runtime_trace() -> None:
        async with app.state.session_factory() as db:
            run = AgentRun(
                run_id="debug-runtime-checkpoint-trace",
                task_id=task["id"],
                goal="correlate debug checkpoints",
                plan=AgentRunPlan(
                    plan_id="debug-checkpoint-plan",
                    goal="correlate debug checkpoints",
                    nodes=[
                        RuntimeNode(
                            node_id="observe",
                            node_type="tool",
                            handler_id="observe.handler",
                        )
                    ],
                ),
            )
            repository = AgentRunRepository(db)
            await repository.create(
                run,
                agent_id=task["agent_id"],
                provider="mock",
            )
            await append_task_event(
                db,
                task["id"],
                AgentEventType.AGENT_PROGRESS,
                agent_id=task["agent_id"],
                data={"runtime_event": "checkpoint_debug_test"},
            )
            await repository.save_checkpoint(run)
            await db.commit()

    client.portal.call(persist_runtime_trace)

    response = client.get(f"/api/v1/debug/execution/{task['id']}")
    assert response.status_code == 200, response.text
    data = response.json()
    checkpoints = data["runtime"]["checkpoints"]
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    assert checkpoints
    assert checkpoints[-1]["event_sequence"] == max(
        event["sequence"] for event in events
    )
    assert all("state_data" not in checkpoint for checkpoint in checkpoints)
