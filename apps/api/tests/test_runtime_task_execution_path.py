from __future__ import annotations

import time
from datetime import UTC, datetime

from app.contracts import (
    AgentExecutionPlan,
    AgentRequest,
    AgentResult,
    ExecutionTimeBudget,
    ExternalEvidenceItem,
    ExternalRetrievalResult,
    ExternalSourceScope,
    ExternalSourceType,
)
from app.contracts.external_retrieval import ExternalEvidenceSupport
from app.runtime import (
    RuntimeCanaryEvidence,
    RuntimeCanaryReport,
    RuntimeCanaryThresholds,
)
from app.runtime.semantic_evidence import (
    RuntimeSemanticDimensions,
    RuntimeSemanticEvidence,
)
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from app.services.runtime_launch_policy import RuntimeLaunchMode, RuntimeLaunchPolicy
from app.services.task_runner import TaskRunner
from pydantic import AnyHttpUrl, TypeAdapter


class FakeLessonRuntimeAgents:
    async def run(
        self,
        agent_id: str,
        request: object,
        context: object = None,
    ) -> AgentResult:
        del request, context
        return AgentResult(
            agent_id=agent_id,
            provider="local_agent",
            answer="## Lesson plan",
            business_data={
                "learning_objectives": ["Explain the concept"],
                "lesson_flow": ["Introduce", "Practice"],
                "activities": ["Practice"],
                "formative_assessment": ["Exit ticket"],
            },
        )


class FakeAssignmentRuntimeAgents:
    async def run(
        self,
        agent_id: str,
        request: object,
        context: object = None,
    ) -> AgentResult:
        del request, context
        return AgentResult(
            agent_id=agent_id,
            provider="local_agent",
            answer="## Assignment review",
            business_data={
                "correctness": "mostly_correct",
                "correct_parts": ["The circuit current is correct."],
                "errors": [],
                "teacher_feedback": "The review is ready for the teacher.",
                "review_required": False,
            },
        )


def _passing_runtime_release_registry(
    *,
    agent_id: str,
    agent_version: str,
    runtime_plan_version: str,
) -> RuntimeCanaryReleaseRegistry:
    """Provide a fully bound release fixture for the Task API handoff test."""

    suite_id = f"{agent_id.casefold()}-runtime-task-api-release"
    captured_at = datetime(2026, 8, 10, tzinfo=UTC)
    report = RuntimeCanaryReport(
        suite_id=suite_id,
        suite_version="1",
        canary_eligible=True,
        release_eligible=True,
        thresholds=RuntimeCanaryThresholds(),
        evidence=RuntimeCanaryEvidence(
            kind="authorized_paired",
            agent_id=agent_id,
            agent_version=agent_version,
            runtime_plan_version=runtime_plan_version,
            authorization_ref="task-api-release-fixture",
            captured_at=captured_at,
            redaction_status="redacted",
        ),
    )
    semantic = RuntimeSemanticEvidence(
        suite_id=suite_id,
        case_id=f"{agent_id.casefold()}-runtime-task-api-case",
        agent_id=agent_id,
        agent_version=agent_version,
        runtime_plan_version=runtime_plan_version,
        input_sha256="0" * 64,
        legacy_output_sha256="1" * 64,
        runtime_output_sha256="2" * 64,
        dimensions=RuntimeSemanticDimensions(
            task_fulfillment=1.0,
            factual_correctness=1.0,
            safety=1.0,
        ),
        decision="pass",
        judge_type="human",
        rubric_version="general-question-v1",
        reviewer_ref="task-api-review-fixture",
        reviewed_at=captured_at,
        redaction_status="redacted",
        authorization_ref="task-api-release-fixture",
    )
    return RuntimeCanaryReleaseRegistry(
        {agent_id: report},
        semantic_evidence={agent_id: semantic},
    )


def test_runtime_resume_restores_serialized_execution_plan() -> None:
    plan = AgentExecutionPlan(
        agent_id="GENERAL_QUESTION_V1",
        provider_type="local_agent",
        route_status="selected",
        use_rag=False,
        retrieval_policy_name="none",
        retrieval_mode="none",
        use_images=False,
        reranker_mode="none",
        context_budget=1_000,
        cloud_timeout_seconds=30,
        fallback_type="none",
        fallback_handler="no_fallback",
        input_mode="text",
        configured=True,
        published=True,
        debug_enabled=False,
        budget=ExecutionTimeBudget.create(cloud_timeout_seconds=30),
    )
    request = AgentRequest(
        task_id="task-resume",
        session_id="session-resume",
        user_id="user-resume",
        options={"_execution_plan": plan.model_dump(mode="json")},
    )

    restored = TaskRunner._execution_plan_from_request(request)

    assert restored is not None
    assert restored.agent_id == plan.agent_id
    assert restored.budget.deadline == plan.budget.deadline

def test_research_analysis_runtime_plan_only_fails_closed_before_legacy_generation(
    api, app
) -> None:
    """A plan-only Runtime candidate cannot claim completion or use Legacy."""

    app.state.task_runner.runtime_lifecycle.enabled = True
    assert app.state.task_runner.research_analysis_runtime is not None
    app.state.task_runner.research_analysis_runtime.enabled = True
    session = api.create_session()
    question = (
        "Compare treatment and control outcome scores and report the effect "
        "with uncertainty and limitations."
    )
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
    completed = api.wait_for_task(response.json()["id"], timeout=15)

    assert completed["status"] == "failed"
    debug = api.client.get(f"/api/v1/debug/execution/{completed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["status"] == "failed"
    assert [node["node_id"] for node in runtime["nodes"]] == [
        "analysis.execute",
        "analysis.prepare",
        "analysis.verify",
    ]
    assert [node["status"] for node in runtime["nodes"]] == [
        "succeeded",
        "succeeded",
        "partial",
    ]
    events = api.client.get(f"/api/v1/tasks/{completed['id']}/events")
    assert events.status_code == 200
    assert not any(
        event["event_data"].get("stage_id") == "model_generation"
        for event in events.json()
    )


def test_external_research_runtime_owns_research_path(api, app, monkeypatch) -> None:
    class FakeSearch:
        async def search(self, query: str, **_: object) -> ExternalRetrievalResult:
            item = ExternalEvidenceItem(
                evidence_id="runtime-paper",
                source_type=ExternalSourceType.ACADEMIC_PAPER,
                provider="fake",
                source_ref="doi:10.1000/runtime",
                title="Runtime research paper",
                canonical_url=TypeAdapter(AnyHttpUrl).validate_python(
                    "https://example.org/runtime-paper"
                ),
                content_excerpt="A bounded runtime abstract.",
                retrieved_at=datetime.now(UTC),
                support_level=ExternalEvidenceSupport.RETRIEVED,
            )
            return ExternalRetrievalResult(
                query=query,
                normalized_query=query,
                source_scopes=[ExternalSourceScope.ACADEMIC],
                items=[item],
                provider_status={"fake": "completed"},
            )

    settings = app.state.task_runner.knowledge_base.settings
    settings.external_retrieval_enabled = True
    settings.agent_runtime_external_research_enabled = True
    app.state.task_runner.runtime_lifecycle.enabled = True
    app.state.task_runner.external_search = FakeSearch()
    app.state.task_runner.external_paper_reviewer = None
    async def require_external_research(_request: AgentRequest):
        from app.contracts.research import ResearchIntentDecision

        return ResearchIntentDecision(
            goal="frontier_brief",
            topic="agent planning",
            requires_web=True,
        )

    assert app.state.task_runner.research_frontier is not None
    monkeypatch.setattr(
        app.state.task_runner.research_frontier,
        "classify_intent",
        require_external_research,
    )
    assert app.state.task_runner.external_research_runtime is not None
    app.state.task_runner.external_research_runtime.enabled = True
    app.state.task_runner.external_research_runtime.external_enabled = True

    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        intent="academic_search",
        options={"external_research_runtime": {"execute": True}},
    )
    payload.update(
        {
            "scene": "research",
            "canonical_input": {"text": "Find the latest agent planning papers."},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    completed = api.wait_for_task(response.json()["id"], timeout=20)

    assert completed["status"] == "completed"
    debug = api.client.get(f"/api/v1/debug/execution/{completed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert [node["node_id"] for node in runtime["nodes"]] == [
        "research.answer",
        "research.fetch",
        "research.intent",
        "research.verify",
    ]
    assert all(node["status"] == "succeeded" for node in runtime["nodes"])
    assert runtime["nodes"][1]["observation"]["facts"]["item_count"] == 1
    result = completed["result_content"]
    assert result["structured_result"]["external_citation_validation"]["status"] == (
        "passed"
    )
    events = api.client.get(f"/api/v1/tasks/{completed['id']}/events")
    assert events.status_code == 200
    names = [event["event_type"] for event in events.json()]
    started = names.index("external_retrieval.started")
    retrieved = names.index("external_retrieval.completed")
    assert started < retrieved < names.index("task.completed")


def test_general_question_runtime_path_uses_registry_plan(api, app) -> None:
    app.state.task_runner.runtime_lifecycle.enabled = True
    assert app.state.task_runner.general_question_runtime is not None
    app.state.task_runner.general_question_runtime.enabled = True
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        options={"general_question_runtime": {"execute": True}},
        intent="unknown",
    )
    payload.update(
        {
            "scene": "dispatch",
            "course_id": "UNKNOWN",
            "canonical_input": {"text": "Explain what an agent is."},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    completed = api.wait_for_task(response.json()["id"], timeout=15)

    assert completed["status"] == "completed"
    debug = api.client.get(f"/api/v1/debug/execution/{completed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["status"] == "completed"
    assert [node["node_id"] for node in runtime["nodes"]] == [
        "general.execute",
        "general.observe",
        "general.verify",
    ]
    observability = runtime["observability"]
    assert observability["schema_version"] == "1"
    assert observability["decisions"]
    assert observability["observations"]
    assert any(
        item["facts"].get("phase") == "verify"
        for item in observability["verifications"]
    )
    assert all(node["status"] == "succeeded" for node in runtime["nodes"])
    execute_node = next(
        node for node in runtime["nodes"] if node["node_id"] == "general.execute"
    )
    assert execute_node["node_type"] == "subagent"
    assert execute_node["handler_id"] == "subagent.GENERAL_QUESTION_V1"
    assert runtime["budget"]["subagent_runs"] == 1
    assert execute_node["effect_status"] == "completed"
    child_facts = execute_node["observation"]["facts"]
    assert child_facts["subagent_id"] == "GENERAL_QUESTION_V1"
    assert child_facts["parent_runtime_run_id"] == runtime["run_id"]
    assert child_facts["child_run_id"]
    assert child_facts["subagent_run_id"].startswith(
        f"{runtime['run_id']}:subagent:"
    )
    assert len(runtime["children"]) == 1
    child_summary = runtime["children"][0]
    assert child_summary["run_id"] == child_facts["child_run_id"]
    assert child_summary["run_kind"] == "subagent"
    assert child_summary["parent_node_id"] == "general.execute"
    assert child_summary["agent_id"] == "GENERAL_QUESTION_V1"
    assert child_summary["status"] == "completed"
    assert child_summary["state_version"] >= 1
    events = api.client.get(f"/api/v1/tasks/{completed['id']}/events")
    assert events.status_code == 200
    assert any(
        event["event_data"].get("data", {}).get("runtime_run_id")
        == child_facts["child_run_id"]
        and event["event_data"].get("data", {}).get("node_id")
        == "subagent.execute"
        for event in events.json()
    )
    assert not any(
        event["event_data"].get("stage_id") == "model_generation"
        for event in events.json()
    )


def test_general_runtime_proposal_gate_resumes_same_task_after_approval(
    api, app, monkeypatch
) -> None:
    """Exercise the real TaskRunner callback, approval API, and recovery path."""

    app.state.task_runner.runtime_lifecycle.enabled = True
    settings = app.state.task_runner.knowledge_base.settings
    settings.agent_runtime_plan_proposals_enabled = True
    assert app.state.task_runner.general_question_runtime is not None
    app.state.task_runner.general_question_runtime.enabled = True
    runner = app.state.task_runner
    launch_preparation_calls = 0
    original_prepare_request_for_launch = (
        runner.runtime_boundary.prepare_request_for_launch
    )

    def record_launch_preparation(
        agent_id: str,
        request: AgentRequest,
        mode: RuntimeLaunchMode,
        *,
        runtime_resume: bool = False,
    ) -> AgentRequest:
        nonlocal launch_preparation_calls
        launch_preparation_calls += 1
        return original_prepare_request_for_launch(
            agent_id,
            request,
            mode,
            runtime_resume=runtime_resume,
        )

    monkeypatch.setattr(
        runner.runtime_boundary,
        "prepare_request_for_launch",
        record_launch_preparation,
    )
    calls = 0

    async def fake_internal_run(
        agent_id: str,
        _request: object,
        _context: object = None,
    ) -> AgentResult:
        nonlocal calls
        calls += 1
        return AgentResult(
            agent_id=agent_id,
            provider="mock",
            answer="" if calls == 1 else "recovered after plan approval",
        )

    assert app.state.task_runner.internal_agents is not None
    monkeypatch.setattr(
        app.state.task_runner.internal_agents,
        "run",
        fake_internal_run,
    )
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        options={"general_question_runtime": {"execute": True}},
        intent="unknown",
    )
    payload.update(
        {
            "scene": "dispatch",
            "course_id": "UNKNOWN",
            "canonical_input": {"text": "Trigger an adaptive plan."},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    task_id = response.json()["id"]

    for _ in range(300):
        current = api.client.get(f"/api/v1/tasks/{task_id}").json()
        if current["status"] == "waiting_review":
            break
        assert current["status"] not in {"failed", "cancelled"}
        time.sleep(0.05)
    else:
        raise AssertionError("task did not reach proposal review")

    initial_launch_preparation_calls = launch_preparation_calls
    assert initial_launch_preparation_calls == 1

    proposals = api.client.get(
        f"/api/v1/tasks/{task_id}/runtime-plan-proposals"
    )
    assert proposals.status_code == 200, proposals.text
    proposal = proposals.json()[0]
    assert proposal["status"] == "pending"
    assert proposal["target_iteration"] == 1
    assert proposal["affected_node_ids"]

    approval = api.client.post(
        f"/api/v1/tasks/{task_id}/runtime-plan-proposals/"
        f"{proposal['proposal_id']}/decision",
        json={
            "decision": "approved",
            "reason": "The recovery action is authorized.",
            "expected_state_version": proposal["state_version"],
        },
    )
    assert approval.status_code == 202, approval.text
    duplicate = api.client.post(
        f"/api/v1/tasks/{task_id}/runtime-plan-proposals/"
        f"{proposal['proposal_id']}/decision",
        json={
            "decision": "approved",
            "reason": "The recovery action is authorized.",
            "expected_state_version": proposal["state_version"],
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    completed = api.wait_for_task(task_id, timeout=15)
    assert completed["status"] == "completed"
    assert calls == 2
    assert launch_preparation_calls == initial_launch_preparation_calls

    debug = api.client.get(f"/api/v1/debug/execution/{task_id}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["status"] == "completed"
    assert runtime["iteration"] == 1
    assert any(
        node["node_id"] == "general.execute.replan.1"
        and node["status"] == "succeeded"
        for node in runtime["nodes"]
    )
    events = api.client.get(f"/api/v1/tasks/{task_id}/events")
    assert events.status_code == 200
    event_data = [event["event_data"] for event in events.json()]
    assert any(
        data.get("data", {}).get("stage_id") == "runtime_plan_proposal"
        and data.get("data", {}).get("status") == "approval_required"
        for data in event_data
    )
    assert any(
        data.get("data", {}).get("stage_id") == "runtime_plan_proposal"
        and data.get("data", {}).get("status") == "applied"
        for data in event_data
    )
    approval_events = [
        data["data"]
        for data in event_data
        if data.get("data", {}).get("stage_id") == "runtime_approval"
    ]
    assert len(approval_events) == 1
    approval_event = approval_events[0]
    assert approval_event["stage_id"] == "runtime_approval"
    assert approval_event["status"] == "approved_submitted"
    assert approval_event["proposal_id"] == proposal["proposal_id"]
    assert approval_event["decision"] == "approved"
    assert approval_event["approver_id"] == "anonymous"
    assert approval_event["approver_role"] == "anonymous"
    assert approval_event["scope"] == "runtime.plan_proposal"
    assert approval_event["state_version"] >= proposal["state_version"]
    assert approval_event["approval"]["state_version"] == approval_event[
        "state_version"
    ]


def test_academic_solver_runtime_path_keeps_solver_graph_behind_runtime(
    api, app
) -> None:
    app.state.task_runner.runtime_lifecycle.enabled = True
    assert app.state.task_runner.academic_solver_runtime is not None
    app.state.task_runner.academic_solver_runtime.enabled = True
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        options={"academic_solver_runtime": {"execute": True}},
        intent="solve_problem",
    )
    payload.update(
        {
            "scene": "solving",
            "course_id": "CT",
            "canonical_input": {"text": "Find the equivalent resistance."},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    completed = api.wait_for_task(response.json()["id"], timeout=15)

    assert completed["status"] == "completed"
    debug = api.client.get(f"/api/v1/debug/execution/{completed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["status"] == "completed"
    assert [node["node_id"] for node in runtime["nodes"]] == [
        "solver.observe",
        "solver.retrieve",
        "solver.execute",
        "solver.verify",
    ]
    assert all(node["status"] == "succeeded" for node in runtime["nodes"])
    events = api.client.get(f"/api/v1/tasks/{completed['id']}/events")
    assert events.status_code == 200
    assert not any(
        event["event_data"].get("stage_id") == "model_generation"
        for event in events.json()
    )


def test_general_question_runtime_auto_candidate_uses_default_route(api, app) -> None:
    app.state.task_runner.runtime_lifecycle.enabled = True
    assert app.state.task_runner.general_question_runtime is not None
    app.state.task_runner.general_question_runtime.enabled = True
    app.state.task_runner.general_question_runtime.auto_enabled = True
    app.state.task_runner.general_question_runtime.canary_enabled = True
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        options={},
        intent="unknown",
    )
    payload.update(
        {
            "scene": "dispatch",
            "course_id": "UNKNOWN",
            "canonical_input": {"text": "Explain what an autonomous agent does."},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    completed = api.wait_for_task(response.json()["id"], timeout=15)

    assert completed["status"] == "completed"
    debug = api.client.get(f"/api/v1/debug/execution/{completed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["status"] == "completed"
    assert [node["node_id"] for node in runtime["nodes"]] == [
        "general.execute",
        "general.observe",
        "general.verify",
    ]
    events = api.client.get(f"/api/v1/tasks/{completed['id']}/events")
    assert events.status_code == 200
    assert not any(
        event["event_data"].get("stage_id") == "model_generation"
        for event in events.json()
    )


def test_general_question_runtime_default_launch_mode_requires_no_runtime_option(
    api, app
) -> None:
    runner = app.state.task_runner
    definition = runner.agent_registry.get("GENERAL_QUESTION_V1")
    runtime_plan_version = runner.runtime_boundary.runtime_plan_version(
        definition.agent_id
    )
    assert runtime_plan_version is not None
    runner.runtime_canary_release = _passing_runtime_release_registry(
        agent_id=definition.agent_id,
        agent_version=definition.version,
        runtime_plan_version=runtime_plan_version,
    )
    runner.runtime_launch_policy = RuntimeLaunchPolicy(
        "GENERAL_QUESTION_V1=default",
        release_registry=runner.runtime_canary_release,
        release_gate_required=True,
    )
    runner.runtime_lifecycle.enabled = True
    assert runner.general_question_runtime is not None
    runner.general_question_runtime.enabled = True
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        options={},
        intent="unknown",
    )
    payload.update(
        {
            "scene": "dispatch",
            "course_id": "UNKNOWN",
            "canonical_input": {"text": "Use the default Runtime launch."},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    completed = api.wait_for_task(response.json()["id"], timeout=15)

    assert completed["status"] == "completed"
    debug = api.client.get(f"/api/v1/debug/execution/{completed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["status"] == "completed"
    assert runtime["launch_decision"]["mode"] == "default"
    assert runtime["launch_decision"]["source"] == "configured_launch_mode"
    compatibility = runtime["compatibility_snapshot"]
    assert compatibility["preparation_status"] == "prepared"
    assert compatibility["agent_id"] == "GENERAL_QUESTION_V1"
    assert compatibility["execution_plan_agent_id"] == "GENERAL_QUESTION_V1"
    assert {node["node_id"] for node in runtime["nodes"]} == {
        "general.observe",
        "general.execute",
        "general.verify",
    }
    events = api.client.get(f"/api/v1/tasks/{completed['id']}/events")
    assert events.status_code == 200
    assert not any(
        event["event_data"].get("stage_id") == "model_generation"
        for event in events.json()
    )


def test_local_retrieval_runtime_default_launch_fails_closed_without_evidence(
    api, app
) -> None:
    runner = app.state.task_runner
    runner.runtime_launch_policy = RuntimeLaunchPolicy(
        "LEARN_01_LOCAL_RETRIEVAL_V1=default"
    )
    runner.runtime_lifecycle.enabled = True
    runner.knowledge_qa_runtime.enabled = True
    session = api.create_session()
    payload = api.task_payload(session["id"], options={}, intent="general_qa")
    payload.update(
        {
            "scene": "learning",
            "course_id": "CT",
            "canonical_input": {"question": "什么是戴维南定理？"},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    failed = api.wait_for_task(response.json()["id"], timeout=15)

    assert failed["status"] == "failed"
    debug = api.client.get(f"/api/v1/debug/execution/{failed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["launch_decision"]["mode"] == "default"
    assert runtime["status"] == "failed"
    events = api.client.get(f"/api/v1/tasks/{failed['id']}/events")
    assert events.status_code == 200
    assert not any(
        event["event_data"].get("stage_id") == "local_retrieval"
        for event in events.json()
    )


def test_local_retrieval_runtime_default_launch_owns_learning_task(
    api, app
) -> None:
    runner = app.state.task_runner
    definition = runner.agent_registry.get("LEARN_01_LOCAL_RETRIEVAL_V1")
    runtime_plan_version = runner.runtime_boundary.runtime_plan_version(
        definition.agent_id
    )
    assert runtime_plan_version is not None
    runner.runtime_canary_release = _passing_runtime_release_registry(
        agent_id=definition.agent_id,
        agent_version=definition.version,
        runtime_plan_version=runtime_plan_version,
    )
    runner.runtime_launch_policy = RuntimeLaunchPolicy(
        "LEARN_01_LOCAL_RETRIEVAL_V1=default",
        release_registry=runner.runtime_canary_release,
        release_gate_required=True,
    )
    runner.runtime_lifecycle.enabled = True
    runner.knowledge_qa_runtime.enabled = True
    knowledge_path = runner.knowledge_base.settings.knowledge_ct_path
    knowledge_path.mkdir(parents=True, exist_ok=True)
    (knowledge_path / "runtime-kcl.md").write_text(
        "# 基尔霍夫电流定律\n\n"
        "基尔霍夫电流定律说明：任一节点流入电流之和等于流出电流之和。\n",
        encoding="utf-8",
    )
    session = api.create_session()
    payload = api.task_payload(session["id"], options={}, intent="general_qa")
    payload.update(
        {
            "scene": "learning",
            "course_id": "CT",
            "canonical_input": {"text": "请解释基尔霍夫电流定律。"},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    completed = api.wait_for_task(response.json()["id"], timeout=20)
    debug = api.client.get(f"/api/v1/debug/execution/{completed['id']}")
    assert debug.status_code == 200

    assert completed["status"] == "completed"
    assert completed["result_content"]["citations"]
    runtime = debug.json()["runtime"]
    assert runtime["status"] == "completed"
    assert runtime["launch_decision"]["mode"] == "default"
    assert runtime["launch_decision"]["source"] == "configured_launch_mode"
    assert [node["node_id"] for node in runtime["nodes"]] == [
        "knowledge.execute",
        "knowledge.verify",
    ]
    assert all(node["status"] == "succeeded" for node in runtime["nodes"])
    events = api.client.get(f"/api/v1/tasks/{completed['id']}/events")
    assert events.status_code == 200
    assert any(
        event["event_data"].get("data", {}).get("runtime_run_id")
        == runtime["run_id"]
        for event in events.json()
    )


def test_lesson_prep_runtime_default_launch_uses_registry_plan(api, app) -> None:
    runner = app.state.task_runner
    definition = runner.agent_registry.get("TEACH_01_LESSON_PREP_V1")
    runtime_plan_version = runner.runtime_boundary.runtime_plan_version(
        definition.agent_id
    )
    assert runtime_plan_version is not None
    runner.runtime_canary_release = _passing_runtime_release_registry(
        agent_id=definition.agent_id,
        agent_version=definition.version,
        runtime_plan_version=runtime_plan_version,
    )
    runner.runtime_launch_policy = RuntimeLaunchPolicy(
        "TEACH_01_LESSON_PREP_V1=default",
        release_registry=runner.runtime_canary_release,
        release_gate_required=True,
    )
    runner.runtime_lifecycle.enabled = True
    assert runner.lesson_prep_runtime is not None
    runner.lesson_prep_runtime.enabled = True
    runner.lesson_prep_runtime.internal_agents = (
        FakeLessonRuntimeAgents()
    )
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        options={
            "scenario_agent_id": "TEACH_01_LESSON_PREP_V1",
            "_scenario_catalog_bound": True,
        },
        intent="lesson_prep",
    )
    payload.update(
        {
            "scene": "teaching",
            "scenario_id": "faculty_course_copilot_v1",
            "canonical_input": {"text": "Prepare a lesson on circuit theory."},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    completed = api.wait_for_task(response.json()["id"], timeout=15)

    assert completed["status"] == "completed"
    debug = api.client.get(f"/api/v1/debug/execution/{completed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["status"] == "completed"
    assert runtime["launch_decision"]["mode"] == "default"
    assert runtime["launch_decision"]["source"] == "configured_launch_mode"
    assert [node["node_id"] for node in runtime["nodes"]] == [
        "lesson.observe",
        "lesson.execute",
        "lesson.verify",
    ]
    assert all(node["status"] == "succeeded" for node in runtime["nodes"])


def test_assignment_review_runtime_default_launch_uses_registry_plan(
    api, app
) -> None:
    runner = app.state.task_runner
    definition = runner.agent_registry.get("TEACH_02_ASSIGNMENT_REVIEW_V1")
    runtime_plan_version = runner.runtime_boundary.runtime_plan_version(
        definition.agent_id
    )
    assert runtime_plan_version is not None
    runner.runtime_canary_release = _passing_runtime_release_registry(
        agent_id=definition.agent_id,
        agent_version=definition.version,
        runtime_plan_version=runtime_plan_version,
    )
    runner.runtime_launch_policy = RuntimeLaunchPolicy(
        "TEACH_02_ASSIGNMENT_REVIEW_V1=default",
        release_registry=runner.runtime_canary_release,
        release_gate_required=True,
    )
    runner.runtime_lifecycle.enabled = True
    assert runner.assignment_review_runtime is not None
    runner.assignment_review_runtime.enabled = True
    runner.assignment_review_runtime.internal_agents = FakeAssignmentRuntimeAgents()
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        options={
            "scenario_agent_id": "TEACH_02_ASSIGNMENT_REVIEW_V1",
            "_scenario_catalog_bound": True,
        },
        intent="assignment_review",
        user_role="teacher",
    )
    payload.update(
        {
            "scene": "teaching",
            "scenario_id": "assessment_diagnosis_v1",
            "canonical_input": {
                "text": "Review this circuit assignment using the rubric."
            },
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    completed = api.wait_for_task(response.json()["id"], timeout=15)

    assert completed["status"] == "completed"
    debug = api.client.get(f"/api/v1/debug/execution/{completed['id']}")
    assert debug.status_code == 200
    runtime = debug.json()["runtime"]
    assert runtime["status"] == "completed"
    assert runtime["launch_decision"]["mode"] == "default"
    assert runtime["launch_decision"]["source"] == "configured_launch_mode"
    assert [node["node_id"] for node in runtime["nodes"]] == [
        "assignment.observe",
        "assignment.execute",
        "assignment.verify",
    ]
    assert all(node["status"] == "succeeded" for node in runtime["nodes"])
