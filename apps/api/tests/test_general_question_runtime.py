from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentResultStatus,
    Intent,
    KnowledgeCourseId,
    KnowledgeHit,
    RetrievalResult,
)
from app.runtime import (
    AgentRun,
    RuntimeBudget,
    RuntimeEvaluationCase,
    RuntimeNodeError,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunSuspended,
    RuntimeStateMachine,
    evaluate_runtime_run,
)
from app.services.general_question_runtime import GeneralQuestionRuntimeService
from app.services.retrieval_context import RetrievalContextService
from app.tools import ToolDefinition, ToolRegistry, default_tool_registry


class FakeInternalAgents:
    def __init__(self, results: list[AgentResult]) -> None:
        self.results = results
        self.calls = 0
        self.last_request: AgentRequest | None = None

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        assert agent_id == GeneralQuestionRuntimeService.agent_id
        assert request.task_id == "task-general-runtime"
        assert context is None
        self.last_request = request
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return result


class FakeRetrieval:
    def __init__(self, *, with_hit: bool = False) -> None:
        self.calls = 0
        self.with_hit = with_hit

    def search(self, **kwargs: object) -> RetrievalResult:
        self.calls += 1
        hits = (
            [
                KnowledgeHit(
                    evidence_id="S1",
                    course_id=KnowledgeCourseId.CIRCUIT_THEORY,
                    course_name="电路理论",
                    chapter="第七章",
                    document_path="CT/chapter-7.md",
                    title="电容电压连续性",
                    content="有限电流条件下，电容电压保持连续。",
                    content_type="concept",
                    score=0.9,
                    source_ref="kb://CT/chapter-7.md#chunk-1",
                )
            ]
            if self.with_hit
            else []
        )
        return RetrievalResult(
            query=str(kwargs.get("query_text", "")),
            normalized_query=str(kwargs.get("query_text", "")),
            course_ids=[str(kwargs.get("course_id", "UNKNOWN"))],
            hits=hits,
            confidence=0.9 if hits else None,
            latency_ms=3,
            retrieval_trace_id="trace-general-runtime",
            index_version="index-test-v1",
        )


def make_request() -> AgentRequest:
    return AgentRequest(
        task_id="task-general-runtime",
        session_id="session-1",
        user_id="user-1",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": "What is an agent?"},
        options={"general_question_runtime": {"execute": True}},
    )


def make_result(status: AgentResultStatus = AgentResultStatus.COMPLETED) -> AgentResult:
    return AgentResult(
        status=status,
        agent_id=GeneralQuestionRuntimeService.agent_id,
        provider="local_agent",
        answer=(
            "An agent observes and acts."
            if status == AgentResultStatus.COMPLETED
            else ""
        ),
    )


def test_general_runtime_executes_verifies_and_replans() -> None:
    fake = FakeInternalAgents(
        [make_result(AgentResultStatus.FAILED), make_result()]
    )
    service = GeneralQuestionRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = AgentRun(
        run_id="run-general-runtime",
        task_id=request.task_id,
        goal="answer the question",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 2
    assert run.iteration == 1
    assert run.budget.subagent_runs == 2
    assert run.status.value == "completed"
    assert run.nodes[service.observe_node_id + ".replan.1"].observation is not None
    assert (
        run.nodes[service.observe_node_id + ".replan.1"]
        .observation.facts["phase"]
        == "observe"
    )
    assert run.nodes[service.execute_node_id + ".replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )
    execute_observation = run.nodes[
        service.execute_node_id + ".replan.1"
    ].observation
    assert execute_observation is not None
    assert execute_observation.facts["subagent_id"] == "GENERAL_QUESTION_V1"
    assert execute_observation.facts["parent_runtime_run_id"] == (
        "run-general-runtime"
    )
    assert execute_observation.facts["subagent_run_id"] == (
        "run-general-runtime:subagent:general.execute.replan.1"
    )
    assert fake.last_request is not None
    assert fake.last_request.options["runtime_subagent_id"] == (
        "GENERAL_QUESTION_V1"
    )
    assert run.nodes[service.verify_node_id + ".replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )


def test_general_runtime_plan_exposes_typed_subagent_action_boundary() -> None:
    service = GeneralQuestionRuntimeService(
        FakeInternalAgents([make_result()]), enabled=True  # type: ignore[arg-type]
    )

    nodes = service.build_plan(make_request()).nodes

    assert [node.node_id for node in nodes] == [
        "general.observe",
        "general.execute",
        "general.verify",
    ]
    assert nodes[0].node_type == "verification"
    assert nodes[1].node_type == "subagent"
    assert nodes[1].handler_id == "subagent.GENERAL_QUESTION_V1"
    assert nodes[1].target_id == "GENERAL_QUESTION_V1"
    assert nodes[1].depends_on == ["general.observe"]
    assert nodes[2].depends_on == ["general.execute"]


def test_general_runtime_retrieval_follows_execution_plan_by_default() -> None:
    service = GeneralQuestionRuntimeService(
        FakeInternalAgents([make_result()]),  # type: ignore[arg-type]
        enabled=True,
        rag_retrieval=FakeRetrieval(),  # type: ignore[arg-type]
        retrieval_context=RetrievalContextService(2_000),
    )
    request = make_request().model_copy(
        update={
            "options": {
                "general_question_runtime": {"execute": True},
                "_execution_plan": {"use_rag": True},
            }
        }
    )

    nodes = service.build_plan(request).nodes

    assert [node.node_id for node in nodes] == [
        "general.observe",
        "general.retrieve",
        "general.execute",
        "general.verify",
    ]


def test_general_runtime_matches_versioned_offline_evaluation_case() -> None:
    fake = FakeInternalAgents([make_result()])
    service = GeneralQuestionRuntimeService(
        fake, enabled=True  # type: ignore[arg-type]
    )
    request = make_request()
    run = AgentRun(
        run_id="run-general-case",
        task_id=request.task_id,
        goal="answer the question",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))
    case_path = (
        Path(__file__).resolve().parents[3]
        / "evaluation"
        / "runtime_cases"
        / "general_question_v1.json"
    )
    case = RuntimeEvaluationCase.model_validate(
        json.loads(case_path.read_text(encoding="utf-8"))
    )
    evaluation = evaluate_runtime_run(run, case, checkpoint_count=1)

    assert result.status == AgentResultStatus.COMPLETED
    assert evaluation.passed is True
    assert evaluation.failed_checks == []


def test_provider_nodes_consume_model_budget() -> None:
    budget = RuntimeBudget(max_model_calls=1, max_tool_calls=1)

    assert budget.reserve("provider") == "model"
    assert budget.model_calls == 1
    assert budget.tool_calls == 0


def test_general_runtime_can_execute_an_explicit_registered_tool() -> None:
    fake = FakeInternalAgents([make_result()])
    service = GeneralQuestionRuntimeService(
        fake,  # type: ignore[arg-type]
        enabled=True,
        tool_registry=default_tool_registry(),
    )
    request = make_request().model_copy(
        update={
            "options": {
                "general_question_runtime": {
                    "execute": True,
                    "tool_id": "calculator",
                    "tool_input": {"expression": "2 + 2"},
                }
            }
        }
    )
    run = AgentRun(
        run_id="run-general-tool",
        task_id=request.task_id,
        goal="answer with a tool",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert [node.node_id for node in run.plan.nodes] == [
        "general.observe",
        "general.tool",
        "general.execute",
        "general.verify",
    ]
    assert run.nodes["general.tool"].observation is not None
    assert run.nodes["general.tool"].observation.facts["output"] == 4
    assert run.budget.tool_calls == 1
    assert run.budget.model_calls == 0
    assert run.budget.subagent_runs == 1
    assert fake.last_request is not None
    assert fake.last_request.options["runtime_tool_id"] == "calculator"
    assert fake.last_request.options["runtime_tool_result"] == 4


def test_general_runtime_can_execute_explicit_retrieval_node() -> None:
    fake = FakeInternalAgents([make_result()])
    retrieval = FakeRetrieval()
    service = GeneralQuestionRuntimeService(
        fake,  # type: ignore[arg-type]
        enabled=True,
        rag_retrieval=retrieval,  # type: ignore[arg-type]
        retrieval_context=RetrievalContextService(2_000),
    )
    request = make_request().model_copy(
        update={
            "options": {
                "general_question_runtime": {
                    "execute": True,
                    "retrieve": True,
                }
            }
        }
    )
    run = AgentRun(
        run_id="run-general-retrieve",
        task_id=request.task_id,
        goal="answer with retrieved evidence",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert retrieval.calls == 1
    assert [node.node_id for node in run.plan.nodes] == [
        "general.observe",
        "general.retrieve",
        "general.execute",
        "general.verify",
    ]
    assert run.nodes["general.retrieve"].observation is not None
    assert (
        run.nodes["general.retrieve"].observation.facts["retrieval_trace_id"]
        == "trace-general-runtime"
    )
    assert fake.last_request is not None
    assert "evidence_status: insufficient" in str(
        fake.last_request.options["retrieved_context"]
    )
    assert result.evidence_status == "insufficient"
    assert result.metrics.retrieval_calls == 1


def test_general_runtime_persists_retrieved_hits_for_result_presentation() -> None:
    fake = FakeInternalAgents([make_result()])
    retrieval = FakeRetrieval(with_hit=True)
    service = GeneralQuestionRuntimeService(
        fake,  # type: ignore[arg-type]
        enabled=True,
        rag_retrieval=retrieval,  # type: ignore[arg-type]
        retrieval_context=RetrievalContextService(2_000),
    )
    request = make_request().model_copy(
        update={
            "canonical_input": {"text": "电容电压连续性"},
            "options": {
                "general_question_runtime": {
                    "execute": True,
                    "retrieve": True,
                }
            }
        }
    )
    run = AgentRun(
        run_id="run-general-presentation",
        task_id=request.task_id,
        goal="answer with durable evidence",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.structured_result["knowledge"]["hits"][0]["evidence_id"] == "S1"
    assert result.structured_result["knowledge_hit_count"] == 1
    assert result.evidence_status == "partial"
    assert fake.last_request is not None
    assert fake.last_request.options["runtime_retrieved_knowledge_hits"]


def test_general_runtime_retrieval_path_emits_ordered_events_and_checkpoints() -> None:
    fake = FakeInternalAgents([make_result()])
    service = GeneralQuestionRuntimeService(
        fake,  # type: ignore[arg-type]
        enabled=True,
        rag_retrieval=FakeRetrieval(),  # type: ignore[arg-type]
        retrieval_context=RetrievalContextService(2_000),
    )
    request = make_request().model_copy(
        update={
            "options": {
                "general_question_runtime": {
                    "execute": True,
                    "retrieve": True,
                }
            }
        }
    )
    run = AgentRun(
        run_id="run-general-events",
        task_id=request.task_id,
        goal="audit runtime events",
        plan=service.build_plan(request),
    )
    events: list[str] = []
    checkpoints: list[tuple[str, int]] = []

    def record_event(event: str, _run: AgentRun, node_id: str) -> None:
        events.append(f"{event}:{node_id}")

    def record_checkpoint(current: AgentRun) -> None:
        checkpoints.append((current.status.value, len(current.observations)))

    asyncio.run(
        service.run(
            request,
            run,
            checkpoint_hook=record_checkpoint,
            event_hook=record_event,
        )
    )

    assert events == [
        "node_started:general.observe",
        "node_completed:general.observe",
        "node_started:general.retrieve",
        "node_completed:general.retrieve",
        "node_started:general.execute",
        "node_completed:general.execute",
        "node_started:general.verify",
        "node_completed:general.verify",
    ]
    assert checkpoints
    assert run.status.value == "completed"


def test_general_runtime_resumes_after_observe_checkpoint_without_repeating_it(
) -> None:
    fake = FakeInternalAgents([make_result()])
    service = GeneralQuestionRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = make_request()
    run = AgentRun(
        run_id="run-general-resume-observe",
        task_id=request.task_id,
        goal="resume after observation",
        plan=service.build_plan(request),
    )
    RuntimeStateMachine.mark_ready(run)
    RuntimeStateMachine.start_node(run, service.observe_node_id)
    RuntimeStateMachine.complete_node(
        run,
        service.observe_node_id,
        status=RuntimeNodeStatus.SUCCEEDED,
        observation=RuntimeObservation(
            node_id=service.observe_node_id,
            facts={"phase": "observe", "question": "What is an agent?"},
        ),
    )
    events: list[str] = []

    def record_event(_event: str, _run: AgentRun, node_id: str) -> None:
        events.append(node_id)

    result = asyncio.run(service.run(request, run, event_hook=record_event))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 1
    assert service.observe_node_id not in events
    assert events[0] == service.execute_node_id


def test_general_runtime_requires_approval_for_non_replay_safe_tool() -> None:
    tool_registry = ToolRegistry()
    tool_registry.register(
        ToolDefinition(
            tool_id="write_tool",
            name="write tool",
            supported_capabilities=frozenset({"write"}),
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            side_effect_level="write",
            deterministic=False,
        ),
        lambda value: {"accepted": value},
    )
    fake = FakeInternalAgents([make_result()])
    service = GeneralQuestionRuntimeService(
        fake,  # type: ignore[arg-type]
        enabled=True,
        tool_registry=tool_registry,
    )
    request = make_request().model_copy(
        update={
            "options": {
                "general_question_runtime": {
                    "execute": True,
                    "tool_id": "write_tool",
                    "tool_input": {"value": "approved input"},
                }
            }
        }
    )
    run = AgentRun(
        run_id="run-general-approval",
        task_id=request.task_id,
        goal="approval-gated tool",
        plan=service.build_plan(request),
    )

    try:
        asyncio.run(service.run(request, run))
    except RuntimeRunSuspended:
        pass
    else:
        raise AssertionError("expected the non-replay-safe tool to pause")

    assert run.status.value == "waiting_approval"
    assert fake.calls == 0
    run.control_data = {"approved": True}

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 1
    assert run.nodes["general.tool"].observation is not None
    assert run.nodes["general.tool"].observation.facts["output"] == {
        "accepted": "approved input"
    }


def test_general_runtime_applies_registered_tool_schema_before_invocation() -> None:
    tool_registry = default_tool_registry()
    fake = FakeInternalAgents([make_result()])
    service = GeneralQuestionRuntimeService(
        fake,  # type: ignore[arg-type]
        enabled=True,
        tool_registry=tool_registry,
    )
    request = make_request().model_copy(
        update={
            "options": {
                "general_question_runtime": {
                    "execute": True,
                    "tool_id": "calculator",
                    "tool_input": {},
                }
            }
        }
    )
    run = AgentRun(
        run_id="run-general-tool-schema",
        task_id=request.task_id,
        goal="tool schema validation",
        plan=service.build_plan(request),
    )

    with pytest.raises(RuntimeNodeError, match="node_input_schema_required"):
        asyncio.run(service.run(request, run))

    assert run.status.value == "failed"
    assert any(
        state.error_code == "node_input_schema_required"
        for state in run.nodes.values()
    )
    assert fake.calls == 0


def test_general_runtime_requires_explicit_runtime_option() -> None:
    service = GeneralQuestionRuntimeService(
        FakeInternalAgents([make_result()]), enabled=True  # type: ignore[arg-type]
    )
    request = make_request().model_copy(update={"options": {}})

    assert not service.supports(service.agent_id, request)


def test_general_runtime_auto_mode_requires_its_separate_gate() -> None:
    service = GeneralQuestionRuntimeService(
        FakeInternalAgents([make_result()]),  # type: ignore[arg-type]
        enabled=True,
        auto_enabled=True,
    )
    request = make_request().model_copy(update={"options": {}})

    assert not service.supports(service.agent_id, request)
    service.canary_enabled = True
    assert service.supports(service.agent_id, request)
    disabled = request.model_copy(
        update={"options": {"general_question_runtime": {"execute": False}}}
    )
    assert not service.supports(service.agent_id, disabled)
