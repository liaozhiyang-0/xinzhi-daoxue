from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.contracts import AgentRequest, AgentResult, RuntimeInputSubmission
from app.services.runtime_launch_policy import RuntimeLaunchPolicy


class RecordingInternalAgents:
    """Provider-free fake for the Runtime's typed subagent boundary."""

    def __init__(self, answer: str = "runtime-owned answer") -> None:
        self.answer = answer
        self.requests: list[AgentRequest] = []

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        del context
        self.requests.append(request.model_copy(deep=True))
        return AgentResult(
            agent_id=agent_id,
            provider="local_test",
            answer=self.answer,
        )


class SequencedKnowledgeQA:
    """Deterministic retrieval fake used by the real TaskRunner path."""

    def __init__(self, *evidence_statuses: str) -> None:
        self.evidence_statuses = list(evidence_statuses)
        self.requests: list[AgentRequest] = []

    async def run_with_generation(
        self,
        _agent_id: str,
        request: AgentRequest,
    ) -> SimpleNamespace:
        self.requests.append(request.model_copy(deep=True))
        evidence_status = self.evidence_statuses.pop(0)
        sufficient = evidence_status in {"sufficient", "complete"}
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


def _general_payload(
    api: Any, session_id: str, *, options: dict[str, Any]
) -> dict[str, Any]:
    payload = api.task_payload(
        session_id,
        options=options,
        intent="unknown",
    )
    payload.update(
        {
            "scene": "dispatch",
            "course_id": "UNKNOWN",
            "canonical_input": {"text": "Explain the Runtime handoff."},
        }
    )
    return payload


def _configure_general_runtime(app: Any, mode: str) -> Any:
    runner = app.state.task_runner
    runner.runtime_launch_policy = RuntimeLaunchPolicy(
        f"GENERAL_QUESTION_V1={mode}"
    )
    runner.runtime_lifecycle.enabled = True
    assert runner.general_question_runtime is not None
    runner.general_question_runtime.enabled = True
    return runner


def test_taskrunner_default_runtime_owns_terminal_handoff(api, app) -> None:
    runner = _configure_general_runtime(app, "default")
    fake = RecordingInternalAgents()
    assert runner.internal_agents is not None
    original_run = runner.internal_agents.run
    runner.internal_agents.run = fake.run  # type: ignore[method-assign]

    try:
        session = api.create_session()
        response = api.client.post(
            "/api/v1/tasks",
            json=_general_payload(api, session["id"], options={}),
        )
        assert response.status_code == 202, response.text
        completed = api.wait_for_task(response.json()["id"], timeout=15)
    finally:
        runner.internal_agents.run = original_run  # type: ignore[method-assign]

    assert completed["status"] == "completed"
    assert len(fake.requests) == 1
    debug = api.client.get(f"/api/v1/debug/execution/{completed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["launch_decision"]["mode"] == "default"
    assert runtime["status"] == "completed"
    assert all(
        node["node_id"] != "legacy.execution" for node in runtime["nodes"]
    )
    events = api.client.get(f"/api/v1/tasks/{completed['id']}/events")
    assert events.status_code == 200
    assert not any(
        event["event_data"].get("stage_id") == "model_generation"
        for event in events.json()
    )


def test_taskrunner_canary_runtime_does_not_repeat_legacy_after_success(
    api, app
) -> None:
    runner = _configure_general_runtime(app, "canary")
    fake = RecordingInternalAgents()
    assert runner.internal_agents is not None
    original_run = runner.internal_agents.run
    runner.internal_agents.run = fake.run  # type: ignore[method-assign]

    try:
        session = api.create_session()
        response = api.client.post(
            "/api/v1/tasks",
            json=_general_payload(
                api,
                session["id"],
                options={"general_question_runtime": {"execute": True}},
            ),
        )
        assert response.status_code == 202, response.text
        completed = api.wait_for_task(response.json()["id"], timeout=15)
    finally:
        runner.internal_agents.run = original_run  # type: ignore[method-assign]

    assert completed["status"] == "completed"
    assert len(fake.requests) == 1
    debug = api.client.get(f"/api/v1/debug/execution/{completed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["launch_decision"]["mode"] == "canary"
    assert runtime["status"] == "completed"
    assert all(
        node["node_id"] != "legacy.execution" for node in runtime["nodes"]
    )
    events = api.client.get(f"/api/v1/tasks/{completed['id']}/events")
    assert events.status_code == 200
    assert not any(
        event["event_data"].get("stage_id") == "model_generation"
        for event in events.json()
    )


def test_taskrunner_resume_uses_checkpointed_request_and_plan(api, app) -> None:
    runner = app.state.task_runner
    runner.runtime_launch_policy = RuntimeLaunchPolicy(
        "LEARN_01_LOCAL_RETRIEVAL_V1=default"
    )
    runner.runtime_lifecycle.enabled = True
    assert runner.knowledge_qa_runtime is not None
    runner.knowledge_qa_runtime.enabled = True
    fake = SequencedKnowledgeQA("insufficient", "sufficient")
    runner.knowledge_qa_runtime.knowledge_qa = fake  # type: ignore[assignment]

    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        options={
            "knowledge_qa_runtime": {
                "execute": True,
                "replan_on_verification_failure": True,
            }
        },
        intent="general_qa",
    )
    payload.update(
        {
            "scene": "learning",
            "course_id": "CT",
            "canonical_input": {"text": "Original checkpoint question"},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    task_id = response.json()["id"]
    waiting = api.wait_for_task(
        task_id,
        statuses={"waiting_user"},
        timeout=15,
    )
    assert waiting["status"] == "waiting_user"

    waiting_debug = api.client.get(f"/api/v1/debug/execution/{task_id}")
    assert waiting_debug.status_code == 200
    waiting_runtime = waiting_debug.json()["runtime"]
    assert waiting_runtime["status"] == "waiting_input"
    initial_plan_id = waiting_runtime["plan_id"]
    initial_state_version = waiting_runtime["state_version"]
    assert initial_plan_id == "knowledge-qa-runtime"

    submitted = api.client.post(
        f"/api/v1/tasks/{task_id}/input",
        json=RuntimeInputSubmission(
            data={"query": "Checkpointed follow-up question"},
            expected_state_version=initial_state_version,
        ).model_dump(mode="json"),
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
    assert fake.requests[1].canonical_input["query"] == (
        "Checkpointed follow-up question"
    )
    final_debug = api.client.get(f"/api/v1/debug/execution/{task_id}")
    assert final_debug.status_code == 200
    runtime = final_debug.json()["runtime"]
    assert runtime["status"] == "completed"
    assert runtime["plan_id"] == initial_plan_id
    assert runtime["iteration"] == 1
    assert any(
        node["node_id"] == "knowledge.execute.replan.1"
        and node["status"] == "succeeded"
        for node in runtime["nodes"]
    )


def test_failed_default_runtime_cannot_be_masked_by_legacy_completion(api, app) -> None:
    runner = app.state.task_runner
    runner.runtime_launch_policy = RuntimeLaunchPolicy(
        "RESEARCH_03_DATA_ANALYSIS_V1=default"
    )
    runner.runtime_lifecycle.enabled = True
    assert runner.research_analysis_runtime is not None
    runner.research_analysis_runtime.enabled = True

    async def forbidden_provider_call(*_: object, **__: object) -> None:
        raise AssertionError("failed default Runtime must not invoke Legacy Provider")

    original_provider_run = runner.provider.run
    runner.provider.run = forbidden_provider_call  # type: ignore[method-assign]
    try:
        session = api.create_session()
        question = "Compare treatment and control outcome scores."
        payload = api.task_payload(
            session["id"],
            options={
                "research_analysis_v2": {
                    "execute": False,
                    "request": {
                        "research_question": question,
                        "analysis_goal": "estimate_effect",
                        "design": "experimental_comparison",
                        "estimand": "treatment minus control mean score",
                        "unit_of_analysis": "one row per participant",
                        "exploratory": True,
                    },
                },
                "scenario_agent_id": "RESEARCH_03_DATA_ANALYSIS_V1",
                "_scenario_catalog_bound": True,
            },
            intent="data_analysis",
        )
        payload.update(
            {
                "scene": "dispatch",
                "scenario_id": "research_data_workbench_v1",
                "canonical_input": {"text": question},
            }
        )
        response = api.client.post("/api/v1/tasks", json=payload)
        assert response.status_code == 202, response.text
        failed = api.wait_for_task(response.json()["id"], timeout=15)
    finally:
        runner.provider.run = original_provider_run  # type: ignore[method-assign]

    assert failed["status"] == "failed"
    debug = api.client.get(f"/api/v1/debug/execution/{failed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["launch_decision"]["mode"] == "default"
    assert runtime["status"] == "failed"
    assert runtime["handoff"].get("status") != "legacy_fallback"
    events = api.client.get(f"/api/v1/tasks/{failed['id']}/events")
    assert events.status_code == 200
    event_data = [event["event_data"] for event in events.json()]
    assert not any(data.get("type") == "task.completed" for data in event_data)
    assert not any(
        data.get("stage_id") == "model_generation" for data in event_data
    )
