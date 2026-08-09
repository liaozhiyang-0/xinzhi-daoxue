from __future__ import annotations

import asyncio

from app.models import AgentRunModel, TaskModel
from app.repositories import AgentRunRepository
from app.runtime import AgentRun
from app.services.answer_disclosure import INTERNAL_TEACHING_KEY
from app.services.session_working_state import SessionWorkingStateService


def power_payload(api, session_id: str, *, options: dict) -> dict:
    payload = api.task_payload(session_id, options=options)
    payload["canonical_input"] = {
        "text": "已知电阻电压u=10V、电流i=2A，按关联参考方向求吸收功率。",
        "problem_type": "power",
        "equations_given": ["P=10*2"],
        "known_conditions": [
            {"name": "u", "value": 10, "unit": "V"},
            {"name": "i", "value": 2, "unit": "A"},
        ],
        "target_quantities": [{"name": "P", "unit": "W"}],
        "structure_status": "complete",
        "extraction_confidence": 0.99,
    }
    return payload


def submit_power(api, session_id: str, *, options: dict) -> dict:
    response = api.client.post(
        "/api/v1/tasks",
        json=power_payload(api, session_id, options=options),
    )
    assert response.status_code == 202, response.text
    task = api.wait_for_task(response.json()["id"])
    owner = api.client.get(
        f"/api/v1/tasks/{task['id']}",
        params={"user_id": "user-test"},
    )
    assert owner.status_code == 200
    return owner.json()


def teaching_action(api, task_id: str, action: str, *, answer: str = "") -> dict:
    response = api.client.post(
        "/api/v1/learning/actions",
        json={
            "source_task_id": task_id,
            "user_id": "user-test",
            "action": action,
            "idempotency_key": f"{action}_{task_id}"[:128],
            "student_answer": answer,
            "payload": {},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_direct_compatibility_and_guided_backend_disclosure(api, app) -> None:
    direct_session = api.create_session()
    direct = submit_power(
        api,
        direct_session["id"],
        options={"teaching_mode": "direct_answer"},
    )
    guided_session = api.create_session()
    guided = submit_power(
        api,
        guided_session["id"],
        options={"teaching_mode": "guided_learning"},
    )
    direct_result = direct["result_content"]
    guided_result = guided["result_content"]
    loop = guided_result["structured_result"]["teaching_loop"]
    assert direct_result["metrics"]["additional_model_calls"] == 0
    assert direct_result["metrics"]["student_verification_executed"] is False
    assert direct_result["metrics"]["hint_level"] == ""
    assert loop["execution_plan"]["path"] == "guided"
    assert loop["hint"]["hint_level"] in {"H0", "H1"}
    assert loop["next_check"]["question_text"]
    assert loop["disclosure_policy"]["reveal_final_answer"] is False
    assert "20 W" not in guided_result["answer"]
    assert guided_result["structured_result"]["solution_packet"]["final_answer"] is None
    assert "final_answer" not in guided_result["structured_result"]
    assert (
        api.client.get(
            f"/api/v1/tasks/{guided['id']}",
            params={"user_id": "another-user"},
        ).status_code
        == 404
    )

    async def raw_internal() -> dict:
        async with app.state.session_factory() as db:
            task = await db.get(TaskModel, guided["id"])
            assert task is not None
            return task.result_content["structured_result"]

    raw = asyncio.run(raw_internal())
    assert INTERNAL_TEACHING_KEY in raw
    assert raw[INTERNAL_TEACHING_KEY]["full_solution_packet"]["final_answer"]


def test_check_more_hint_switch_direct_and_refresh_restore(api, app) -> None:
    session = api.create_session()
    checked = submit_power(
        api,
        session["id"],
        options={
            "teaching_mode": "check_my_work",
            "student_attempt": {
                "raw_text": "P=u*i=20",
                "final_answer": "P=20",
            },
        },
    )
    result = checked["result_content"]
    structured = result["structured_result"]
    report = structured["verification_report_v1"]
    assert report["overall_status"] == "verified_incorrect"
    assert report["first_confirmed_error_step"] == "student-final"
    assert report["step_results"][0]["error_type"] == "unit_missing"
    assert structured["teaching_loop"]["hint"]["hint_level"] == "H1"
    assert structured["teaching_loop"]["disclosure_policy"]["mode"] == "withhold_final"
    assert "20 W" not in result["answer"]
    original_model_calls = result["metrics"]["model_calls"]

    anonymous = api.client.get(f"/api/v1/tasks/{checked['id']}").json()
    anonymous_structured = anonymous["result_content"]["structured_result"]
    assert "verification_report_v1" not in anonymous_structured

    more = teaching_action(api, checked["id"], "request_more_hint")
    assert more["teaching"]["hint"]["hint_level"] == "H2"
    owner = api.client.get(
        f"/api/v1/tasks/{checked['id']}",
        params={"user_id": "user-test"},
    ).json()
    assert owner["result_content"]["metrics"]["model_calls"] == original_model_calls
    assert owner["result_content"]["metrics"]["additional_model_calls"] == 0

    switched = teaching_action(api, checked["id"], "switch_to_direct_answer")
    assert switched["teaching"]["solution_packet_reused"] is True
    restored = api.client.get(
        f"/api/v1/tasks/{checked['id']}",
        params={"user_id": "user-test"},
    ).json()
    restored_result = restored["result_content"]
    assert restored_result["metrics"]["model_calls"] == original_model_calls
    assert restored_result["metrics"]["solution_packet_reused"] is True
    assert restored_result["structured_result"]["solution_packet"]["final_answer"]
    assert restored_result["structured_result"]["teaching_loop"][
        "full_solution_disclosed"
    ] is True

    async def load_state():
        async with app.state.session_factory() as db:
            return await SessionWorkingStateService(db).get(session["id"])

    state = asyncio.run(load_state())
    assert state.teaching_state is not None
    assert state.teaching_state.full_solution_disclosed is True
    assert state.teaching_state.solution_packet_task_id == checked["id"]
    messages = api.client.get(
        f"/api/v1/sessions/{session['id']}/messages",
        params={"user_id": "user-test"},
    ).json()
    assert messages[-1]["content_data"]["teaching_loop"][
        "full_solution_disclosed"
    ] is True
    events = api.client.get(f"/api/v1/tasks/{checked['id']}/events").json()
    teaching_events = [
        item
        for item in events
        if item["event_data"]["data"].get("stage") == "teaching_state_updated"
    ]
    assert [item["sequence"] for item in events] == sorted(
        item["sequence"] for item in events
    )
    assert teaching_events[-1]["event_data"]["data"]["learning_action"] == (
        "switch_to_direct_answer"
    )
    assert teaching_events[-1]["event_data"]["data"][
        "full_solution_disclosed"
    ] is True


def test_phase2_feedback_action_uses_durable_runtime(api, app) -> None:
    app.state.teaching_interaction_runtime.enabled = True
    session = api.create_session()
    checked = submit_power(
        api,
        session["id"],
        options={"teaching_mode": "check_my_work"},
    )

    response = teaching_action(api, checked["id"], "request_more_hint")
    assert response["status"] == "completed"
    assert response["runtime_status"] == "completed"
    assert response["runtime_run_id"]
    assert response["approval_required"] is False

    async def load_runtime() -> tuple[AgentRunModel, AgentRun]:
        async with app.state.session_factory() as db:
            model = await db.get(AgentRunModel, response["runtime_run_id"])
            assert model is not None
            restored = await AgentRunRepository(db).restore(model.id)
            assert restored is not None
            return model, restored

    runtime_model, restored = asyncio.run(load_runtime())
    assert runtime_model.run_kind == "teaching_interaction"
    assert runtime_model.status == "completed"
    assert runtime_model.plan_version == "teaching-interaction-v1"
    assert restored.nodes["teaching.feedback.observe"].status.value == "succeeded"
    assert restored.nodes["teaching.feedback.apply"].status.value == "succeeded"
    assert restored.nodes["teaching.feedback.verify"].status.value == "succeeded"
    assert restored.nodes["teaching.feedback.approval"].status.value == "skipped"

    events = api.client.get(f"/api/v1/tasks/{checked['id']}/events").json()
    runtime_events = [
        item
        for item in events
        if item["event_data"]["data"].get("runtime_run_id")
        == response["runtime_run_id"]
    ]
    assert runtime_events
    assert [item["sequence"] for item in runtime_events] == sorted(
        item["sequence"] for item in runtime_events
    )


def test_teaching_runtime_waits_for_and_resumes_after_teacher_approval(
    api, app
) -> None:
    app.state.teaching_interaction_runtime.enabled = True
    session = api.create_session()
    checked = submit_power(
        api,
        session["id"],
        options={"teaching_mode": "check_my_work"},
    )

    response = api.client.post(
        "/api/v1/learning/actions",
        json={
            "source_task_id": checked["id"],
            "user_id": "user-test",
            "action": "submit_check_response",
            "idempotency_key": "runtime-approval-0001",
            "student_answer": "I used another method without a numeric result.",
            "payload": {},
        },
    )
    assert response.status_code == 200, response.text
    accepted = response.json()
    assert accepted["status"] == "accepted", accepted
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


def test_check_my_work_enrichment_error_completes_with_safe_fallback(
    api, app, monkeypatch
) -> None:
    def fail_enrichment(*_args, **_kwargs):
        raise RuntimeError("unexpected teaching adapter failure")

    monkeypatch.setattr(
        app.state.teaching_foundation,
        "enrich",
        fail_enrichment,
    )
    session = api.create_session()

    checked = submit_power(
        api,
        session["id"],
        options={
            "teaching_mode": "check_my_work",
            "student_attempt": {
                "raw_text": "根据欧姆定律，I=U/R=10/2=5。",
            },
        },
    )

    result = checked["result_content"]
    loop = result["structured_result"]["teaching_loop"]
    assert checked["status"] == "completed"
    assert result["answer"]
    assert "20 W" not in result["answer"]
    assert loop["status"] == "degraded"
    assert loop["error_type"] == "teaching_enrichment_unexpected_error"
    assert result["metrics"]["full_solution_disclosed"] is False
