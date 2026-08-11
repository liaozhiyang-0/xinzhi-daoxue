from __future__ import annotations

import asyncio

import pytest
from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentResultStatus,
    Intent,
    RetrievalResult,
)
from app.core.errors import NotConfiguredError
from app.runtime import (
    AgentRun,
    RuntimeBudget,
    RuntimeCanaryEvidence,
    RuntimeCanarySuite,
    RuntimeDecision,
    RuntimeNodeStatus,
    RuntimeRunStatus,
    evaluate_runtime_canary_suite,
)
from app.services.general_question_runtime import GeneralQuestionRuntimeService
from app.services.research_analysis_runtime import ResearchAnalysisRuntimeService
from app.services.retrieval_context import RetrievalContextService
from app.services.runtime_control_policy import (
    control_policy_for_runtime_kind,
)
from app.services.runtime_execution_boundary import RuntimeExecutionBoundary
from app.services.runtime_launch_policy import (
    RuntimeLaunchDecision,
    RuntimeLaunchMode,
)
from app.tools import ToolDefinition, ToolRegistry

GENERAL_AGENT_ID = "GENERAL_QUESTION_V1"
RESEARCH_AGENT_ID = "RESEARCH_03_DATA_ANALYSIS_V1"


class FakeInternalAgents:
    """Provider-free typed-subagent fake used by every matrix case."""

    def __init__(self, results: list[AgentResult]) -> None:
        self.results = results
        self.calls = 0
        self.requests: list[AgentRequest] = []

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        assert agent_id == GENERAL_AGENT_ID
        assert context is None
        self.requests.append(request)
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return result


class FakeRetrieval:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, **kwargs: object) -> RetrievalResult:
        self.calls += 1
        query = str(kwargs.get("query_text", ""))
        return RetrievalResult(
            query=query,
            normalized_query=query,
            course_ids=[str(kwargs.get("course_id", "CT"))],
            latency_ms=1,
            retrieval_trace_id="synthetic-retrieval-trace",
            index_version="synthetic-index-v1",
        )


class FakeResearchAgent:
    """Minimal fake for inspecting the RESEARCH_03 runtime seam only."""

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        del request, context
        assert agent_id == RESEARCH_AGENT_ID
        return AgentResult(
            agent_id=agent_id,
            provider="synthetic-research-agent",
            answer="synthetic analysis",
        )


def make_result(status: AgentResultStatus = AgentResultStatus.COMPLETED) -> AgentResult:
    return AgentResult(
        status=status,
        agent_id=GENERAL_AGENT_ID,
        provider="synthetic-internal-agent",
        answer="An agent observes, acts, and verifies."
        if status == AgentResultStatus.COMPLETED
        else "",
        mock_used=True,
        mock_profile="runtime-agent-contract-matrix",
    )


def make_request(
    *,
    retrieve: bool = False,
    tool_id: str = "",
) -> AgentRequest:
    runtime_options: dict[str, object] = {"execute": True}
    if retrieve:
        runtime_options["retrieve"] = True
    if tool_id:
        runtime_options.update(
            {
                "tool_id": tool_id,
                "tool_input": {"expression": "2 + 2"},
            }
        )
    return AgentRequest(
        task_id="runtime-agent-contract-task",
        session_id="runtime-agent-contract-session",
        user_id="runtime-agent-contract-user",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": "What makes an agent?"},
        options={"general_question_runtime": runtime_options},
    )


def make_tool_registry(calls: list[str]) -> ToolRegistry:
    registry = ToolRegistry()

    def fixture_calculator(expression: str) -> int:
        calls.append(expression)
        return 4

    registry.register(
        ToolDefinition(
            tool_id="fixture.calculator",
            name="fixture calculator",
            supported_capabilities=frozenset({"algebra"}),
            input_schema={"type": "object"},
            output_schema={"type": "integer"},
        ),
        fixture_calculator,
    )
    return registry


def make_general_service(
    fake: FakeInternalAgents,
    *,
    retrieval: FakeRetrieval | None = None,
    tool_registry: ToolRegistry | None = None,
) -> GeneralQuestionRuntimeService:
    return GeneralQuestionRuntimeService(
        fake,  # type: ignore[arg-type]
        enabled=True,
        rag_retrieval=retrieval,  # type: ignore[arg-type]
        retrieval_context=(
            RetrievalContextService(2_000) if retrieval is not None else None
        ),
        tool_registry=tool_registry,
    )


def make_run(
    service: GeneralQuestionRuntimeService,
    request: AgentRequest,
    *,
    run_id: str,
    budget: RuntimeBudget | None = None,
) -> AgentRun:
    return AgentRun(
        run_id=run_id,
        task_id=request.task_id,
        goal="answer the user question",
        plan=service.build_plan(request),
        budget=budget or RuntimeBudget(),
    )


def test_general_agent_contract_observe_decide_act_verify() -> None:
    fake = FakeInternalAgents([make_result()])
    service = make_general_service(fake)
    request = make_request()
    run = make_run(service, request, run_id="run-contract-phases")
    events: list[str] = []
    decisions: list[str] = []

    def record_event(event: str, _run: AgentRun, node_id: str) -> None:
        events.append(f"{event}:{node_id}")

    def record_decision(_run: AgentRun, decision: RuntimeDecision) -> None:
        decisions.append(str(decision.action))

    result = asyncio.run(
        service.run(
            request,
            run,
            event_hook=record_event,
            decision_event_hook=record_decision,
        )
    )

    assert result.status == AgentResultStatus.COMPLETED
    assert run.status == RuntimeRunStatus.COMPLETED
    assert events == [
        "node_started:general.observe",
        "node_completed:general.observe",
        "node_started:general.execute",
        "node_completed:general.execute",
        "node_started:general.verify",
        "node_completed:general.verify",
    ]
    assert decisions == [
        "execute",
        "execute",
        "execute",
    ]
    assert run.nodes["general.observe"].observation is not None
    assert run.nodes["general.observe"].observation.facts["phase"] == "observe"
    assert run.nodes["general.execute"].observation is not None
    assert run.plan.nodes[1].node_type == "subagent"
    assert (
        run.nodes["general.execute"].observation.facts["subagent_id"]
        == GENERAL_AGENT_ID
    )
    assert run.nodes["general.verify"].observation is not None
    assert run.nodes["general.verify"].observation.facts["passed"] is True


@pytest.mark.parametrize(
    ("retrieve", "tool_id", "expected_nodes"),
    [
        (False, "", ["general.observe", "general.execute", "general.verify"]),
        (
            True,
            "",
            [
                "general.observe",
                "general.retrieve",
                "general.execute",
                "general.verify",
            ],
        ),
        (
            False,
            "fixture.calculator",
            [
                "general.observe",
                "general.tool",
                "general.execute",
                "general.verify",
            ],
        ),
        (
            True,
            "fixture.calculator",
            [
                "general.observe",
                "general.retrieve",
                "general.tool",
                "general.execute",
                "general.verify",
            ],
        ),
    ],
)
def test_general_agent_optional_retrieve_tool_and_subagent_contract(
    retrieve: bool,
    tool_id: str,
    expected_nodes: list[str],
) -> None:
    retrieval = FakeRetrieval() if retrieve else None
    tool_calls: list[str] = []
    fake = FakeInternalAgents([make_result()])
    service = make_general_service(
        fake,
        retrieval=retrieval,
        tool_registry=make_tool_registry(tool_calls) if tool_id else None,
    )
    request = make_request(retrieve=retrieve, tool_id=tool_id)
    run = make_run(
        service,
        request,
        run_id=f"run-contract-{retrieve}-{bool(tool_id)}",
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert [node.node_id for node in run.plan.nodes] == expected_nodes
    execute_node = run.nodes["general.execute"]
    assert execute_node.observation is not None
    assert run.plan.nodes[-2].node_type == "subagent"
    assert execute_node.observation.facts["subagent_id"] == GENERAL_AGENT_ID
    assert execute_node.status == RuntimeNodeStatus.SUCCEEDED
    assert fake.calls == 1
    if retrieval is not None:
        assert retrieval.calls == 1
        assert run.nodes["general.retrieve"].observation is not None
        assert (
            run.nodes["general.retrieve"].observation.facts["phase"]
            == "retrieve"
        )
    if tool_id:
        assert tool_calls == ["2 + 2"]
        assert run.nodes["general.tool"].observation is not None
        assert run.nodes["general.tool"].observation.facts["output"] == 4


def test_general_agent_failure_replans_once_within_budget() -> None:
    fake = FakeInternalAgents([make_result(AgentResultStatus.FAILED), make_result()])
    service = make_general_service(fake)
    request = make_request()
    run = make_run(
        service,
        request,
        run_id="run-contract-replan",
        budget=RuntimeBudget(max_iterations=2),
    )
    decisions: list[str] = []

    def record_decision(_run: AgentRun, decision: RuntimeDecision) -> None:
        decisions.append(str(decision.action))

    result = asyncio.run(
        service.run(request, run, decision_event_hook=record_decision)
    )

    assert result.status == AgentResultStatus.COMPLETED
    assert run.status == RuntimeRunStatus.COMPLETED
    assert run.iteration == 1
    assert fake.calls == 2
    assert "replan" in decisions
    assert "general.execute.replan.1" in run.nodes
    assert run.nodes["general.verify.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )


def test_general_agent_replan_budget_exhaustion_is_terminal_failure() -> None:
    fake = FakeInternalAgents(
        [make_result(AgentResultStatus.FAILED), make_result(AgentResultStatus.FAILED)]
    )
    service = make_general_service(fake)
    request = make_request()
    run = make_run(
        service,
        request,
        run_id="run-contract-failed",
        budget=RuntimeBudget(max_iterations=2),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.FAILED
    assert run.status == RuntimeRunStatus.FAILED
    assert run.iteration == 1
    assert fake.calls == 2
    assert run.nodes["general.execute.replan.1"].status == (
        RuntimeNodeStatus.PARTIAL
    )
    assert run.nodes["general.verify.replan.1"].status == (
        RuntimeNodeStatus.PENDING
    )


def test_default_runtime_handoff_is_fail_closed_for_non_completed_run() -> None:
    service = make_general_service(FakeInternalAgents([make_result()]))
    request = make_request()
    run = make_run(service, request, run_id="run-contract-handoff")
    run.status = RuntimeRunStatus.FAILED
    decision = RuntimeLaunchDecision(
        agent_id=GENERAL_AGENT_ID,
        mode=RuntimeLaunchMode.DEFAULT,
        source="contract-matrix",
        reason="synthetic terminal state",
    )
    result = make_result()

    with pytest.raises(NotConfiguredError, match="status=failed"):
        RuntimeExecutionBoundary.handoff_result(result, decision=decision, run=run)


def test_research03_is_lifecycle_candidate_and_learning_loop_is_approve_only() -> None:
    request = AgentRequest(
        task_id="research03-contract-task",
        session_id="research03-contract-session",
        user_id="research03-contract-user",
        options={
            "research_analysis_v2": {
                "execute": True,
                "mode": "execute",
                "request": {
                    "research_question": "Does the intervention change the outcome?",
                    "analysis_goal": "compare",
                    "design": "experimental_comparison",
                    "data_manifest": {
                        "dataset_id": "research03-contract-fixture",
                        "version": "v1",
                        "format": "csv",
                        "checksum_sha256": "c" * 64,
                        "row_count": 2,
                        "column_count": 3,
                        "authorized": True,
                        "source_ref": "fixture://research03-contract",
                    },
                },
            }
        },
    )
    service = ResearchAnalysisRuntimeService(
        FakeResearchAgent(), enabled=True  # type: ignore[arg-type]
    )
    plan = service.build_plan(request)

    assert [node.node_id for node in plan.nodes] == [
        "analysis.prepare",
        "analysis.execute",
        "analysis.verify",
    ]
    prepare, execute, verify = plan.nodes
    assert prepare.handler_id == "research.analysis.prepare"
    assert execute.handler_id == "research.analysis.execute"
    assert execute.depends_on == [prepare.node_id]
    assert verify.handler_id == "research.analysis.verify"
    assert verify.depends_on == [execute.node_id]
    assert service.runtime_plan_version == "research-v2"
    assert service.supports(RESEARCH_AGENT_ID, request) is True
    assert service.supports(
        RESEARCH_AGENT_ID,
        request.model_copy(update={"options": {}}),
    ) is False
    learning_policy = control_policy_for_runtime_kind("learning_loop")
    assert learning_policy.declared_controls == (
        "pause",
        "resume",
        "approve",
        "input",
    )
    assert learning_policy.available_controls("waiting_approval") == ("approve",)
    assert learning_policy.available_controls("running") == ("pause",)


def test_synthetic_fixture_cannot_be_release_evidence() -> None:
    evidence = RuntimeCanaryEvidence(
        kind="synthetic",
        agent_id=GENERAL_AGENT_ID,
    )
    report = evaluate_runtime_canary_suite(
        RuntimeCanarySuite(
            suite_id="runtime-agent-contract-matrix",
            evidence=evidence,
        )
    )

    assert evidence.release_ready is False
    assert report.release_eligible is False
