from __future__ import annotations

from apps.api.tests.phase3_helpers import learning_action, submit_power


def test_p3_01_first_attempt_and_p3_02_revision_are_immutable(api) -> None:
    session = api.create_session()
    task = submit_power(
        api,
        session["id"],
        student_attempt={"raw_text": "P=20", "final_answer": "20"},
    )
    first_list = api.client.get(
        "/api/v1/learning/attempts",
        params={"user_id": "user-test", "source_task_id": task["id"]},
    )
    assert first_list.status_code == 200
    first = first_list.json()[0]
    assert first["attempt_sequence"] == 1
    assert first["revision_of_attempt_id"] is None

    response = learning_action(
        api,
        task["id"],
        "submit_attempt_revision",
        key="phase3-revision-0001",
        answer="P=20 W",
    )
    assert response.status_code == 200, response.text
    second = response.json()["attempt"]
    assert second["attempt_sequence"] == 2
    assert second["revision_of_attempt_id"] == first["attempt_id"]
    old = api.client.get(
        f"/api/v1/learning/attempts/{first['attempt_id']}",
        params={"user_id": "user-test"},
    ).json()
    assert old["status"] == "superseded"
    assert old["raw_text"] == "P=20"


def test_p3_03_idempotent_revision_and_p3_04_cross_user_isolation(api) -> None:
    session = api.create_session()
    task = submit_power(
        api,
        session["id"],
        student_attempt={"raw_text": "P=20"},
    )
    first = learning_action(
        api,
        task["id"],
        "submit_attempt_revision",
        key="phase3-idempotent-0001",
        answer="P=20 W",
    )
    second = learning_action(
        api,
        task["id"],
        "submit_attempt_revision",
        key="phase3-idempotent-0001",
        answer="P=20 W",
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    rows = api.client.get(
        "/api/v1/learning/attempts",
        params={"user_id": "user-test", "source_task_id": task["id"]},
    ).json()
    assert [item["attempt_sequence"] for item in rows] == [2, 1]

    attempt_id = rows[0]["attempt_id"]
    hidden = api.client.get(
        f"/api/v1/learning/attempts/{attempt_id}",
        params={"user_id": "another-user"},
    )
    assert hidden.status_code == 404
    rejected = learning_action(
        api,
        task["id"],
        "submit_attempt_revision",
        key="phase3-cross-user-0001",
        answer="P=20 W",
        payload={"revision_of_attempt_id": attempt_id},
        user_id="another-user",
    )
    assert rejected.status_code == 404
