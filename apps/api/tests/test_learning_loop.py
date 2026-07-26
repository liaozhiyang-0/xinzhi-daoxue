from __future__ import annotations

from app.services.practice_generation import PracticeGenerationService
from app.services.student_answer_review import StudentAnswerReviewService


def test_answer_review_aligns_steps_and_detects_unit_error() -> None:
    review = StudentAnswerReviewService().review(
        "I=10/5=2",
        reference_answer="I=2 A",
        reference_steps=[{"equation": "I=U/R"}, {"substitution": "I=10/5"}],
    )
    assert review.status == "partially_correct"
    assert review.first_error and review.first_error["type"] == "unit"
    assert review.aligned_steps[1]["matched"] is True


def test_practice_generator_only_returns_verified_supported_variant() -> None:
    generated = PracticeGenerationService().generate(
        "task-1", "一个10V电压源串联5Ω电阻，求回路电流。"
    )
    assert generated.status == "ready"
    assert generated.reference_answer == {
        "value": 2.0,
        "unit": "A",
        "equation": "I=U/R",
    }
    assert all(item["status"] == "passed" for item in generated.validation_checks)


def test_learning_action_is_idempotent_and_updates_mastery(api) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])["id"])
    payload = {
        "source_task_id": task["id"],
        "user_id": "user-test",
        "action": "mark_mastered",
        "idempotency_key": "learn-fixed-0001",
        "student_answer": "",
        "payload": {},
    }
    first = api.client.post("/api/v1/learning/actions", json=payload)
    second = api.client.post("/api/v1/learning/actions", json=payload)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
    states = api.client.get(
        "/api/v1/learning/states", params={"user_id": "user-test", "course_id": "CT"}
    )
    assert states.status_code == 200
    assert len(states.json()) == 1
    assert states.json()[0]["correct_count"] == 1


def test_related_knowledge_followup_preserves_source_context(api) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])["id"])
    response = api.client.post(
        "/api/v1/learning/actions",
        json={
            "source_task_id": task["id"],
            "user_id": "user-test",
            "action": "related_knowledge",
            "idempotency_key": "learn-related-0001",
            "student_answer": "",
            "payload": {},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "needs_task"
    assert body["follow_up_context"] == {
        "source_task_id": task["id"],
        "course_id": "CT",
        "intent": "explain_concept",
        "action": "related_knowledge",
    }
    assert task["id"] in body["follow_up_prompt"]
    assert "求电阻两端电压" in body["follow_up_prompt"]
    assert "不要要求用户重新提供题目背景" in body["follow_up_prompt"]
