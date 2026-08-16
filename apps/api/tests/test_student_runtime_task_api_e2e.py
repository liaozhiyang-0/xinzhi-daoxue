from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.contracts import AgentRequest, AgentResult
from app.services.runtime_launch_policy import RuntimeLaunchPolicy


class SequencedKnowledgeQA:
    def __init__(self) -> None:
        self.requests: list[AgentRequest] = []
        self._statuses = iter(("insufficient", "sufficient"))

    async def run_with_generation(
        self,
        _agent_id: str,
        request: AgentRequest,
    ) -> SimpleNamespace:
        self.requests.append(request.model_copy(deep=True))
        evidence_status = next(self._statuses)
        sufficient = evidence_status == "sufficient"
        result = AgentResult(
            agent_id="LEARN_01_LOCAL_RETRIEVAL_V1",
            provider="local_test",
            answer="evidence-backed answer" if sufficient else "",
            structured_result={"mode": "retrieval_only"},
            citations=["kb://CT/fake.md"] if sufficient else [],
            evidence_status=evidence_status,
        )
        return SimpleNamespace(
            result=result,
            context=SimpleNamespace(
                evidence_status=evidence_status,
                evidence=["fake-hit"] if sufficient else [],
            ),
        )


def test_student_task_api_exposes_waiting_input_and_resumes_checkpoint(
    api, app
) -> None:
    runner = app.state.task_engine
    runner.runtime_launch_policy = RuntimeLaunchPolicy(
        "LEARN_01_LOCAL_RETRIEVAL_V1=default"
    )
    runner.runtime_lifecycle.enabled = True
    assert runner.knowledge_qa_runtime is not None
    runner.knowledge_qa_runtime.enabled = True
    fake = SequencedKnowledgeQA()
    runner.knowledge_qa_runtime.knowledge_qa = fake  # type: ignore[assignment]

    session = api.create_session()
    payload: dict[str, Any] = api.task_payload(
        session["id"],
        options={
            "knowledge_qa_runtime": {
                "execute": True,
                "replan_on_verification_failure": True,
            }
        },
        intent="general_qa",
        user_role="student",
    )
    payload.update(
        {
            "scene": "learning",
            "course_id": "CT",
            "canonical_input": {"text": "Original checkpoint question"},
        }
    )
    created = api.client.post("/api/v1/tasks", json=payload)
    assert created.status_code == 202, created.text
    task_id = created.json()["id"]

    waiting = api.wait_for_task(
        task_id,
        statuses={"waiting_user"},
        timeout=15,
    )
    assert waiting["status"] == "waiting_user"

    controls = api.client.get(f"/api/v1/tasks/{task_id}/runtime-controls")
    assert controls.status_code == 200, controls.text
    projection = controls.json()
    assert projection["status"] == "waiting_input"
    assert projection["control_scope"] == "runtime"
    assert any(
        item["action"] == "input" and item["available"]
        for item in projection["controls"]
    )

    submitted = api.client.post(
        f"/api/v1/tasks/{task_id}/input",
        json={
            "data": {"query": "Checkpointed follow-up question"},
            "expected_state_version": projection["state_version"],
        },
    )
    assert submitted.status_code == 200, submitted.text

    completed = api.wait_for_task(task_id, timeout=15)
    assert completed["status"] == "completed"
    assert len(fake.requests) == 2
    assert fake.requests[0].canonical_input["text"] == (
        "Original checkpoint question"
    )
    assert fake.requests[1].canonical_input["text"] == (
        "Checkpointed follow-up question"
    )

    final_controls = api.client.get(f"/api/v1/tasks/{task_id}/runtime-controls")
    assert final_controls.status_code == 200
    assert not any(item["available"] for item in final_controls.json()["controls"])

    events = api.client.get(f"/api/v1/tasks/{task_id}/events")
    assert events.status_code == 200
    sequences = [event["sequence"] for event in events.json()]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))
