from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from app.contracts import AgentRequest, AgentResult, AgentResultStatus, Intent
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    PlanExecutor,
    RuntimeBudget,
    RuntimeCanaryEvidence,
    RuntimeCanaryPair,
    RuntimeCanarySuite,
    RuntimeCheckpointRecord,
    RuntimeController,
    RuntimeDecision,
    RuntimeEvaluationCase,
    RuntimeGoal,
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeLaunchSnapshot,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
    RuntimeRunSuspended,
    RuntimeSubagentDefinition,
    RuntimeSubagentRegistry,
    audit_checkpoint_trace,
    evaluate_runtime_canary_suite,
    evaluate_runtime_run,
    register_subagent_handlers,
)
from app.services.general_question_runtime import GeneralQuestionRuntimeService
from app.services.generic_goal_runtime import GenericGoalRuntimeService
from app.services.runtime_goal_intake import RuntimeGoalIntakePolicy
from app.tools import ToolDefinition, ToolRegistry

GENERAL_AGENT_ID = "GENERAL_QUESTION_V1"
HELPER_AGENT_ID = "SYNTHETIC_HELPER_V1"


class SyntheticInternalAgents:
    """Typed sub-agent double; this matrix never invokes a real Provider."""

    def __init__(
        self, statuses: list[AgentResultStatus] | None = None
    ) -> None:
        self.statuses = statuses or [AgentResultStatus.COMPLETED]
        self.calls = 0
        self.requests: list[AgentRequest] = []

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: Any = None,
    ) -> AgentResult:
        assert context is None
        self.calls += 1
        self.requests.append(request)
        status = self.statuses[min(self.calls - 1, len(self.statuses) - 1)]
        return AgentResult(
            status=status,
            agent_id=agent_id,
            provider="synthetic-internal-agent",
            answer=(
                "synthetic verified answer"
                if status == AgentResultStatus.COMPLETED
                else ""
            ),
            mock_used=True,
            mock_profile="true-agent-contract-matrix",
        )


def general_request(*, tool: bool = False) -> AgentRequest:
    runtime_options: dict[str, Any] = {"execute": True}
    if tool:
        runtime_options.update(
            {
                "tool_id": "fixture.calculator",
                "tool_input": {"kwargs": {"expression": "2 + 2"}},
            }
        )
    return AgentRequest(
        task_id="true-agent-general-task",
        session_id="true-agent-general-session",
        user_id="synthetic-user",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": "What is a true agent?"},
        options={"general_question_runtime": runtime_options},
    )


def general_service(
    internal_agents: SyntheticInternalAgents,
) -> GeneralQuestionRuntimeService:
    tools = ToolRegistry()
    tools.register(
        ToolDefinition(
            tool_id="fixture.calculator",
            name="synthetic calculator",
            supported_capabilities=frozenset({"algebra"}),
            input_schema={"type": "object"},
            output_schema={"type": "integer"},
        ),
        lambda expression: 4 if expression == "2 + 2" else 0,
    )
    return GeneralQuestionRuntimeService(
        internal_agents,
        enabled=True,
        tool_registry=tools,
    )


def runtime_run(
    request: AgentRequest,
    plan: AgentRunPlan,
    *,
    run_id: str,
    budget: RuntimeBudget | None = None,
) -> AgentRun:
    return AgentRun(
        run_id=run_id,
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
        budget=budget or RuntimeBudget(),
        request_snapshot=request.model_dump(mode="json"),
        launch_decision=RuntimeLaunchSnapshot(
            agent_id=str(request.options.get("runtime_agent_id", GENERAL_AGENT_ID)),
            mode="synthetic",
            source="true-agent-contract-matrix",
            reason="contract fixture only",
        ),
    )


def test_general_question_covers_observe_decide_act_verify_tool_and_subagent() -> None:
    internal = SyntheticInternalAgents()
    service = general_service(internal)
    request = general_request(tool=True)
    run = runtime_run(request, service.build_plan(request), run_id="true-agent-general")
    events: list[str] = []
    decisions: list[DecisionAction] = []

    def event_hook(event: str, _run: AgentRun, node_id: str) -> None:
        events.append(f"{event}:{node_id}")

    def decision_hook(_run: AgentRun, decision: RuntimeDecision) -> None:
        decisions.append(decision.action)

    result = asyncio.run(
        service.run(
            request,
            run,
            event_hook=event_hook,
            decision_event_hook=decision_hook,
        )
    )

    assert result.status == AgentResultStatus.COMPLETED
    assert run.status == RuntimeRunStatus.COMPLETED
    assert DecisionAction.EXECUTE in decisions
    assert events[0] == "node_started:general.observe"
    assert "node_completed:general.tool" in events
    assert "node_completed:general.execute" in events
    assert events[-1] == "node_completed:general.verify"
    assert run.nodes["general.tool"].observation is not None
    assert run.nodes["general.tool"].observation.facts["output"] == 4
    execute = run.nodes["general.execute"].observation
    assert execute is not None
    assert execute.facts["subagent_id"] == GENERAL_AGENT_ID
    assert run.nodes["general.verify"].observation is not None
    assert run.nodes["general.verify"].observation.facts["passed"] is True
    assert run.budget.tool_calls == 1
    assert run.budget.subagent_runs == 1
    assert internal.calls == 1


def test_general_question_replans_dynamically_and_fails_closed_at_budget() -> None:
    internal = SyntheticInternalAgents(
        [AgentResultStatus.FAILED, AgentResultStatus.COMPLETED]
    )
    service = general_service(internal)
    request = general_request()
    run = runtime_run(
        request,
        service.build_plan(request),
        run_id="true-agent-general-replan",
        budget=RuntimeBudget(max_iterations=2),
    )
    decisions: list[DecisionAction] = []

    result = asyncio.run(
        service.run(
            request,
            run,
            decision_event_hook=lambda _run, decision: decisions.append(
                decision.action
            ),
        )
    )

    assert result.status == AgentResultStatus.COMPLETED
    assert run.status == RuntimeRunStatus.COMPLETED
    assert run.iteration == 1
    assert DecisionAction.REPLAN in decisions
    assert "general.execute.replan.1" in run.nodes
    assert run.nodes["general.verify.replan.1"].status == RuntimeNodeStatus.SUCCEEDED
    assert internal.calls == 2

    failing = SyntheticInternalAgents(
        [AgentResultStatus.FAILED, AgentResultStatus.FAILED]
    )
    failing_service = general_service(failing)
    failing_request = general_request()
    failing_run = runtime_run(
        failing_request,
        failing_service.build_plan(failing_request),
        run_id="true-agent-general-fail-closed",
        budget=RuntimeBudget(max_iterations=2),
    )

    failed_result = asyncio.run(
        failing_service.run(failing_request, failing_run)
    )
    assert failed_result.status == AgentResultStatus.FAILED
    assert failing_run.status == RuntimeRunStatus.FAILED
    assert failing_run.nodes["general.verify.replan.1"].status == (
        RuntimeNodeStatus.PENDING
    )


def _register_goal_handler(
    registry: RuntimeHandlerRegistry,
    handler_id: str,
    handler: Any,
    *,
    kind: str = "tool",
    requires_approval: bool = False,
) -> None:
    registry.register(
        RuntimeHandlerDescriptor(
            handler_id=handler_id,
            kind=kind,  # type: ignore[arg-type]
            requires_approval=requires_approval,
            max_timeout_ms=30_000,
        ),
        handler,
    )


def test_generic_goal_compiles_structured_goal_and_calls_tool_and_subagent() -> None:
    registry = RuntimeHandlerRegistry()
    tool_calls: list[str] = []

    async def observe_tool(_run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        tool_calls.append(node.node_id)
        return RuntimeObservation(
            node_id=node.node_id,
            facts={"tool_observed": True, "output": "synthetic context"},
        )

    _register_goal_handler(registry, "tool.fixture.observe", observe_tool)
    subagents = RuntimeSubagentRegistry()
    subagents.register(
        RuntimeSubagentDefinition(
            subagent_id="HELPER",
            target_agent_id=HELPER_AGENT_ID,
            version="helper-v1",
        )
    )
    internal = SyntheticInternalAgents()
    register_subagent_handlers(registry, internal, subagents)
    service = GenericGoalRuntimeService(
        registry,
        intake_policy=RuntimeGoalIntakePolicy(
            {
                "GENERIC_GOAL_V1": frozenset(
                    {"tool.fixture.observe", "subagent.HELPER"}
                )
            }
        ),
    )
    request = AgentRequest(
        task_id="true-agent-goal-task",
        session_id="true-agent-goal-session",
        user_id="synthetic-user",
        options={
            "runtime_agent_id": "GENERIC_GOAL_V1",
            "runtime_goal_runtime": {
                "execute": True,
                "goal": RuntimeGoal(
                    objective="ground a structured answer",
                    success_criteria=["tool_observed", "subagent_answer"],
                    required_capabilities=[
                        "fixture.observe",
                        "subagent.HELPER",
                    ],
                    context={"fixture": True},
                ).model_dump(mode="json"),
            },
        },
    )
    plan = service.build_plan(request)
    run = runtime_run(request, plan, run_id="true-agent-generic-goal")
    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert run.goal_contract is not None
    assert run.goal_contract.objective == "ground a structured answer"
    assert [node.node_type for node in run.plan.nodes] == ["tool", "subagent"]
    assert tool_calls == ["goal.step.1.fixture-observe"]
    assert internal.calls == 1
    subagent_node = run.nodes["goal.step.2.subagent-HELPER"].observation
    assert subagent_node is not None
    assert subagent_node.facts["subagent_id"] == "HELPER"
    assert subagent_node.facts["target_agent_id"] == HELPER_AGENT_ID
    assert all(
        state.status == RuntimeNodeStatus.SUCCEEDED
        for state in run.nodes.values()
    )
    assert result.structured_result["node_statuses"] == {
        node_id: RuntimeNodeStatus.SUCCEEDED.value for node_id in run.nodes
    }


def test_generic_goal_replans_to_declared_fallback_capability() -> None:
    registry = RuntimeHandlerRegistry()
    calls: list[str] = []

    async def primary(_run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        calls.append("primary")
        return RuntimeObservation(
            node_id=node.node_id,
            terminal_status=RuntimeNodeStatus.PARTIAL,
            errors=["synthetic verification failure"],
        )

    async def fallback(_run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        calls.append("fallback")
        return RuntimeObservation(node_id=node.node_id, facts={"output": "ok"})

    _register_goal_handler(registry, "tool.primary", primary)
    _register_goal_handler(registry, "tool.fallback", fallback)
    service = GenericGoalRuntimeService(registry)
    request = AgentRequest(
        task_id="true-agent-goal-replan-task",
        session_id="true-agent-goal-replan-session",
        user_id="synthetic-user",
        options={
            "runtime_goal_runtime": {
                "execute": True,
                "goal": {
                    "objective": "recover a goal",
                    "required_capabilities": ["primary"],
                    "constraints": {"fallback_capabilities": ["fallback"]},
                },
            }
        },
    )
    run = runtime_run(
        request,
        service.build_plan(request),
        run_id="true-agent-generic-replan",
        budget=RuntimeBudget(max_iterations=2),
    )
    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert run.iteration == 1
    assert calls == ["primary", "fallback"]
    assert run.plan.version == "goal-runtime-v1.r1"
    assert "goal.step.1.fallback" in run.nodes
    assert run.last_decision is not None
    assert run.last_decision.action == DecisionAction.EXECUTE


def test_runtime_enforces_budget_approval_pause_and_resume() -> None:
    registry = RuntimeHandlerRegistry()
    approved_calls: list[str] = []

    async def approved_handler(_run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        approved_calls.append(node.node_id)
        return RuntimeObservation(node_id=node.node_id, facts={"approved": True})

    _register_goal_handler(
        registry,
        "tool.approved",
        approved_handler,
        requires_approval=True,
    )
    approval_service = GenericGoalRuntimeService(registry)
    approval_request = AgentRequest(
        task_id="true-agent-approval-task",
        session_id="true-agent-approval-session",
        user_id="synthetic-user",
        options={
            "runtime_goal_runtime": {
                "execute": True,
                "goal": {
                    "objective": "run approved capability",
                    "required_capabilities": ["approved"],
                },
            }
        },
    )
    approval_run = runtime_run(
        approval_request,
        approval_service.build_plan(approval_request),
        run_id="true-agent-approval",
    )
    with pytest.raises(RuntimeRunSuspended):
        asyncio.run(approval_service.run(approval_request, approval_run))
    assert approval_run.status == RuntimeRunStatus.WAITING_APPROVAL
    assert approved_calls == []
    approval_run.control_data["approved"] = True
    result = asyncio.run(approval_service.run(approval_request, approval_run))
    assert result.status == AgentResultStatus.COMPLETED
    assert approved_calls == ["goal.step.1.approved"]

    def simple_handler(_run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        return RuntimeObservation(node_id=node.node_id, facts={"done": True})

    simple_plan = AgentRunPlan(
        plan_id="true-agent-control-plan",
        goal="pause and resume",
        nodes=[
            RuntimeNode(
                node_id="control.step",
                node_type="tool",
                handler_id="tool.simple",
            )
        ],
    )
    simple_registry = RuntimeHandlerRegistry()
    _register_goal_handler(simple_registry, "tool.simple", simple_handler)
    control_run = AgentRun(
        run_id="true-agent-control",
        task_id="true-agent-control-task",
        goal="pause and resume",
        plan=simple_plan,
    )
    asyncio.run(
        RuntimeController(
            PlanExecutor(simple_registry),
            lambda _run: RuntimeDecision(
                action=DecisionAction.EXECUTE,
                node_ids=["control.step"],
            ),
            control_provider=lambda _run: RuntimeDecision(
                action=DecisionAction.PAUSE,
                reason_codes=["synthetic_pause"],
            ),
        ).run(control_run)
    )
    assert control_run.status == RuntimeRunStatus.PAUSED
    asyncio.run(
        RuntimeController(
            PlanExecutor(simple_registry),
            lambda _run: RuntimeDecision(
                action=DecisionAction.EXECUTE,
                node_ids=["control.step"],
            ),
        ).run(control_run)
    )
    assert control_run.status == RuntimeRunStatus.COMPLETED
    assert control_run.nodes["control.step"].status == RuntimeNodeStatus.SUCCEEDED

    budget_run = AgentRun(
        run_id="true-agent-budget",
        task_id="true-agent-budget-task",
        goal="bounded tool",
        plan=simple_plan,
        budget=RuntimeBudget(max_tool_calls=0),
    )
    asyncio.run(PlanExecutor(simple_registry).execute(budget_run))
    assert budget_run.status == RuntimeRunStatus.FAILED
    assert budget_run.nodes["control.step"].error_code == "tool_call_budget_exceeded"


def test_checkpoint_and_evidence_identity_are_auditable_but_synthetic() -> None:
    registry = RuntimeHandlerRegistry()

    def handler(_run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        return RuntimeObservation(node_id=node.node_id, facts={"answer": "ok"})

    _register_goal_handler(registry, "tool.identity", handler)
    plan = AgentRunPlan(
        plan_id="identity-plan",
        version="identity-v1",
        goal="audit identity",
        nodes=[
            RuntimeNode(
                node_id="identity.step",
                node_type="tool",
                handler_id="tool.identity",
            )
        ],
    )
    run = AgentRun(
        run_id="identity-run",
        task_id="identity-task",
        goal="audit identity",
        plan=plan,
        launch_decision=RuntimeLaunchSnapshot(
            agent_id="GENERIC_GOAL_V1",
            mode="synthetic",
            source="true-agent-contract-matrix",
            reason="fixture",
        ),
    )
    checkpoints: list[RuntimeCheckpointRecord] = []

    def checkpoint(current: AgentRun) -> None:
        current.state_version += 1
        checkpoints.append(
            RuntimeCheckpointRecord(
                sequence=len(checkpoints) + 1,
                state_version=current.state_version,
                event_sequence=len(checkpoints) + 1,
                state_data=current.model_dump(mode="json"),
            )
        )

    asyncio.run(
        RuntimeController(
            PlanExecutor(registry, checkpoint_hook=checkpoint),
            lambda current: RuntimeDecision(
                action=(
                    DecisionAction.FINISH
                    if current.nodes["identity.step"].status
                    == RuntimeNodeStatus.SUCCEEDED
                    else DecisionAction.EXECUTE
                ),
                node_ids=[]
                if current.nodes["identity.step"].status
                == RuntimeNodeStatus.SUCCEEDED
                else ["identity.step"],
            ),
            checkpoint_hook=checkpoint,
        ).run(run)
    )

    trace = audit_checkpoint_trace(checkpoints)
    assert trace.valid is True
    assert trace.run_id == "identity-run"
    assert trace.agent_ids == ["GENERIC_GOAL_V1"]
    assert trace.plan_versions == ["identity-v1"]
    evaluation = evaluate_runtime_run(
        run,
        RuntimeEvaluationCase(
            case_id="identity-contract",
            expected_status=RuntimeRunStatus.COMPLETED,
            required_node_statuses={
                "identity.step": RuntimeNodeStatus.SUCCEEDED
            },
            required_handler_ids={"tool.identity"},
        ),
        checkpoint_count=len(checkpoints),
    )
    assert evaluation.passed is True

    evidence = RuntimeCanaryEvidence(
        kind="synthetic",
        agent_id="GENERIC_GOAL_V1",
        agent_version="identity-v1",
        runtime_plan_version="identity-v1",
        redaction_status="not_applicable",
    )
    report = evaluate_runtime_canary_suite(
        RuntimeCanarySuite(
            suite_id="true-agent-contract-matrix",
            evidence=evidence,
            pairs=[
                RuntimeCanaryPair(
                    case_id="synthetic-identity",
                    legacy_payload={
                        "agent_id": "GENERIC_GOAL_V1",
                        "status": "completed",
                        "provider": "synthetic",
                        "answer": "ok",
                    },
                    runtime_payload={
                        "agent_id": "GENERIC_GOAL_V1",
                        "run_id": "identity-run",
                        "status": "completed",
                        "provider": "synthetic",
                        "answer": "ok",
                    },
                    runtime_checkpoints=[
                        item.model_dump(mode="json") for item in checkpoints
                    ],
                )
            ],
        )
    )
    assert report.canary_eligible is True
    assert report.release_eligible is False


def test_checkpoint_identity_mismatch_is_fail_closed() -> None:
    now = datetime.now(UTC)
    evidence = RuntimeCanaryEvidence(
        kind="authorized_paired",
        agent_id="EXPECTED_AGENT",
        agent_version="v1",
        runtime_plan_version="plan-v1",
        authorization_ref="fixture-only",
        captured_at=now,
        redaction_status="unknown",
    )
    run = AgentRun(
        run_id="mismatch-run",
        task_id="mismatch-task",
        goal="identity mismatch",
        plan=AgentRunPlan(
            plan_id="mismatch-plan",
            version="plan-v1",
            goal="identity mismatch",
            nodes=[
                RuntimeNode(
                    node_id="step",
                    node_type="tool",
                    handler_id="tool.synthetic",
                )
            ],
        ),
        launch_decision=RuntimeLaunchSnapshot(
            agent_id="EXPECTED_AGENT",
            mode="synthetic",
            source="matrix",
            reason="fixture",
        ),
    )
    checkpoint = RuntimeCheckpointRecord(
        sequence=1,
        state_version=1,
        state_data=run.model_dump(mode="json"),
    )
    report = evaluate_runtime_canary_suite(
        RuntimeCanarySuite(
            suite_id="identity-mismatch",
            evidence=evidence,
            pairs=[
                RuntimeCanaryPair(
                    case_id="mismatch",
                    legacy_payload={
                        "agent_id": "EXPECTED_AGENT",
                        "status": "completed",
                        "provider": "synthetic",
                        "answer": "ok",
                    },
                    runtime_payload={
                        "agent_id": "WRONG_AGENT",
                        "status": "completed",
                        "provider": "synthetic",
                        "answer": "ok",
                    },
                    runtime_checkpoints=[checkpoint.model_dump(mode="json")],
                )
            ],
        )
    )
    assert report.release_eligible is False
    assert "mismatch:runtime_agent_identity_mismatch" in report.release_failed_checks
