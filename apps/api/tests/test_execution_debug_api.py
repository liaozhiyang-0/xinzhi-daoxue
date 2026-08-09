import asyncio

from app.models import AgentRunModel


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

    asyncio.run(persist_handoff())

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
