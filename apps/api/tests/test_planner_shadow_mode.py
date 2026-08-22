from __future__ import annotations

from app.contracts import AgentRequest, RouteDecision, RouteStatus
from app.services.planner import PlannerService


def _route() -> RouteDecision:
    return RouteDecision(
        agent_id="GENERAL_QUESTION_V1",
        scene="dispatch",
        course_id="UNKNOWN",
        intent="general_qa",
        route_status=RouteStatus.SELECTED,
        reason="shadow test",
        retrieval_required=False,
        provider_required=False,
    )


def test_tasks_persist_provider_free_planner_shadow(api, app, client) -> None:
    app.state.settings.planner_shadow_enabled = True
    session = api.create_session()
    task = api.create_task(session["id"])

    persisted = client.get(f"/api/v1/tasks/{task['id']}")
    assert persisted.status_code == 200, persisted.text
    snapshot = persisted.json()["input_content"]["options"]["_planner_snapshot"]
    assert snapshot["mode"] == "shadow"
    assert snapshot["status"] == "completed"
    assert snapshot["model_calls"] == 0
    assert snapshot["lineage"]["context_snapshot_id"]
    assert snapshot["lineage"]["registry_snapshot_id"]

    events = client.get(f"/api/v1/tasks/{task['id']}/events")
    assert events.status_code == 200, events.text
    plan_event = next(
        item for item in events.json() if item["event_type"] == "plan.created"
    )
    assert (
        plan_event["event_data"]["data"]["planner_snapshot"]["mode"]
        == "shadow"
    )


def test_chat_persists_the_same_planner_shadow_contract(api, app, client) -> None:
    app.state.settings.planner_shadow_enabled = True
    session = api.create_session()
    response = client.post(
        "/api/v1/chat",
        json={
            "request_id": "req-planner-shadow-chat",
            "session_id": session["id"],
            "user_id": "user-test",
            "message": "解释采样定理",
            "course_hint": "DSP",
            "intent_hint": "explain_concept",
        },
    )
    assert response.status_code == 202, response.text
    task_id = response.json()["task_id"]
    persisted = client.get(f"/api/v1/tasks/{task_id}")
    assert persisted.status_code == 200, persisted.text
    snapshot = persisted.json()["input_content"]["options"]["_planner_snapshot"]
    assert snapshot["mode"] == "shadow"
    assert snapshot["route_match"] is True
    assert snapshot["plan_match"] is True


def test_planner_failure_snapshot_keeps_legacy_path_explicit() -> None:
    request = AgentRequest(
        task_id="planner-failure",
        session_id="planner-failure-session",
        user_id="planner-failure-user",
        canonical_input={"text": "failure snapshot"},
        options={},
    )
    snapshot = PlannerService().failed_snapshot(
        request,
        _route(),
        error_type="SyntheticPlannerFailure",
    )

    assert snapshot.mode == "failed"
    assert snapshot.status == "failed"
    assert snapshot.fallback_reason == "planner_failure_legacy_path"
    assert snapshot.error_type == "SyntheticPlannerFailure"
