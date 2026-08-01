from __future__ import annotations

from typing import Any


def power_payload(
    api: Any,
    session_id: str,
    *,
    mode: str = "check_my_work",
    student_attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options: dict[str, Any] = {"teaching_mode": mode}
    if student_attempt is not None:
        options["student_attempt"] = student_attempt
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


def submit_power(
    api: Any,
    session_id: str,
    *,
    mode: str = "check_my_work",
    student_attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = api.client.post(
        "/api/v1/tasks",
        json=power_payload(
            api,
            session_id,
            mode=mode,
            student_attempt=student_attempt,
        ),
    )
    assert response.status_code == 202, response.text
    return api.wait_for_task(response.json()["id"])


def learning_action(
    api: Any,
    task_id: str,
    action: str,
    *,
    key: str,
    answer: str = "",
    payload: dict[str, Any] | None = None,
    user_id: str = "user-test",
) -> Any:
    return api.client.post(
        "/api/v1/learning/actions",
        json={
            "source_task_id": task_id,
            "user_id": user_id,
            "action": action,
            "idempotency_key": key,
            "student_answer": answer,
            "payload": payload or {},
        },
    )
