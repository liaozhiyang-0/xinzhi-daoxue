from __future__ import annotations

import asyncio

from app.services.session_working_state import SessionWorkingStateService


def test_legacy_request_defaults_to_direct_answer_without_extra_model_call(api) -> None:
    implicit_session = api.create_session()
    implicit = api.wait_for_task(api.create_task(implicit_session["id"])["id"])
    explicit_session = api.create_session()
    explicit = api.wait_for_task(
        api.create_task(
            explicit_session["id"],
            options={"teaching_mode": "direct_answer"},
        )["id"]
    )
    assert implicit["input_content"]["options"]["teaching_mode"] == "direct_answer"
    assert (
        implicit["result_content"]["structured_result"]["teaching"][
            "teaching_mode"
        ]
        == "direct_answer"
    )
    assert (
        implicit["result_content"]["metrics"]["model_calls"]
        == explicit["result_content"]["metrics"]["model_calls"]
    )


def test_check_my_work_persists_attempt_without_long_term_memory(api, app) -> None:
    session = api.create_session()
    options = {
        "teaching_mode": "check_my_work",
        "student_attempt": {
            "raw_text": "I=10/5=2",
            "final_answer": "I=2",
            "confidence": 0.6,
        },
    }
    completed = api.wait_for_task(
        api.create_task(session["id"], options=options)["id"]
    )
    persisted = completed["input_content"]["options"]
    assert persisted["teaching_mode"] == "check_my_work"
    assert persisted["student_attempt"]["raw_text"] == "I=10/5=2"
    structured = completed["result_content"]["structured_result"]
    assert structured["teaching"]["student_attempt_present"] is True
    assert structured["teaching"]["diagnostic_scope"]
    assert "solution_packet" in structured
    assert "evidence_packet" in structured
    assert completed["result_content"]["metrics"]["student_attempt_present"] is True

    messages = api.client.get(
        f"/api/v1/sessions/{session['id']}/messages",
        params={"user_id": "user-test"},
    ).json()
    assert messages[0]["content_data"]["student_attempt"]["raw_text"] == "I=10/5=2"
    assert (
        api.client.get("/api/v1/memories", params={"user_id": "user-test"}).json()
        == []
    )
    learning_states = api.client.get(
        "/api/v1/learning/states",
        params={"user_id": "user-test", "course_id": "CT"},
    ).json()
    assert learning_states
    assert all(item["course_id"] == "CT" for item in learning_states)

    async def load_state():
        async with app.state.session_factory() as db:
            return await SessionWorkingStateService(db).get(session["id"])

    state = asyncio.run(load_state())
    assert state.teaching_state is not None
    assert state.teaching_state.teaching_mode.value == "check_my_work"
    assert state.teaching_state.student_attempt_present is True
    assert state.teaching_state.source_task_id == completed["id"]


def test_guided_mode_is_available_and_review_remains_foundation_only(api) -> None:
    session = api.create_session()
    completed = api.wait_for_task(
        api.create_task(
            session["id"], options={"teaching_mode": "guided_learning"}
        )["id"]
    )
    teaching = completed["result_content"]["structured_result"]["teaching"]
    assert teaching["teaching_mode"] == "guided_learning"
    assert teaching["mode_status"] == "available"
    loop = completed["result_content"]["structured_result"]["teaching_loop"]
    assert loop["execution_plan"]["path"] == "guided"
    assert loop["hint"]["hint_level"] in {"H0", "H1"}
    review_session = api.create_session()
    review = api.wait_for_task(
        api.create_task(
            review_session["id"], options={"teaching_mode": "review"}
        )["id"]
    )
    review_teaching = review["result_content"]["structured_result"]["teaching"]
    assert review_teaching["mode_status"] == "foundation_only"
    assert "后续阶段" in review_teaching["warning"]
