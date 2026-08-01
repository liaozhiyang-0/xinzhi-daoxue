from __future__ import annotations

import asyncio

from app.services.session_working_state import SessionWorkingStateService

from apps.api.tests.phase3_helpers import learning_action, submit_power


def test_p3_17_refresh_restores_compact_attempt_and_retest_ids(api, app) -> None:
    session = api.create_session()
    task = submit_power(
        api,
        session["id"],
        student_attempt={"raw_text": "P=20"},
    )
    learning_action(
        api,
        task["id"],
        "switch_to_direct_answer",
        key="phase3-state-switch-0001",
    )
    revision = learning_action(
        api,
        task["id"],
        "submit_attempt_revision",
        key="phase3-state-revision-0001",
        answer="P=20 W",
    )
    assert revision.status_code == 200, revision.text

    async def load():
        async with app.state.session_factory() as db:
            return await SessionWorkingStateService(db).get(session["id"])

    state = asyncio.run(load())
    teaching = state.teaching_state
    assert teaching is not None
    assert teaching.current_attempt_id == revision.json()["attempt"]["attempt_id"]
    assert teaching.previous_attempt_id
    assert teaching.attempt_sequence == 2
    assert teaching.last_mastery_evidence_type == "full_solution_seen"
    assert len(teaching.pending_retest_plan_ids) == 2
    dumped = teaching.model_dump(mode="json")
    assert "raw_text" not in dumped
    assert "mastery_score" not in dumped
