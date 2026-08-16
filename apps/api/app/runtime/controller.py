from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, cast

from app.runtime.contracts import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    RuntimeDecision,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimePlanProposal,
    RuntimePlanProposalStatus,
    RuntimeRunStatus,
)
from app.runtime.executor import PlanExecutor
from app.runtime.state_machine import RuntimeStateMachine

DecisionProvider = Callable[
    [AgentRun], RuntimeDecision | Awaitable[RuntimeDecision]
]
Verifier = Callable[
    [AgentRun], RuntimeObservation | None | Awaitable[RuntimeObservation | None]
]
ReplanProvider = Callable[
    [AgentRun, RuntimeDecision], AgentRunPlan | Awaitable[AgentRunPlan]
]
PlanProposalProvider = Callable[
    [AgentRun, RuntimeDecision, AgentRunPlan],
    RuntimePlanProposal | Awaitable[RuntimePlanProposal],
]
CheckpointHook = Callable[[AgentRun], Any]
ControlProvider = Callable[
    [AgentRun], RuntimeDecision | None | Awaitable[RuntimeDecision | None]
]
DecisionEventHook = Callable[[AgentRun, RuntimeDecision], Any]


class RuntimeRunSuspended(RuntimeError):
    """Signal that a worker should exit while a durable Run awaits control."""

    def __init__(self, run: AgentRun) -> None:
        super().__init__(f"runtime run suspended: {run.status.value}")
        self.run_id = run.run_id
        self.status = run.status


class RuntimeController:
    """Drive the observe-decide-act-verify loop around PlanExecutor."""

    def __init__(
        self,
        executor: PlanExecutor,
        decision_provider: DecisionProvider,
        *,
        verifier: Verifier | None = None,
        replan_provider: ReplanProvider | None = None,
        plan_proposal_provider: PlanProposalProvider | None = None,
        checkpoint_hook: CheckpointHook | None = None,
        control_provider: ControlProvider | None = None,
        decision_event_hook: DecisionEventHook | None = None,
        max_decisions: int = 100,
    ) -> None:
        self.executor = executor
        self.decision_provider = decision_provider
        self.verifier = verifier
        self.replan_provider = replan_provider
        self.plan_proposal_provider = plan_proposal_provider
        self.checkpoint_hook = checkpoint_hook
        self.control_provider = control_provider
        self.decision_event_hook = decision_event_hook
        self.max_decisions = max_decisions

    async def run(self, agent_run: AgentRun) -> AgentRun:
        decisions = 0
        while decisions < self.max_decisions:
            control = await self._control(agent_run)
            if control is not None:
                RuntimeStateMachine.apply_decision(agent_run, control)
                await self._emit_decision(agent_run, control)
                await self._checkpoint(agent_run)
                if control.action in {
                    DecisionAction.PAUSE,
                    DecisionAction.ASK_USER,
                    DecisionAction.REQUEST_APPROVAL,
                }:
                    return agent_run
            verification = await self._verify(agent_run)
            if verification is not None:
                RuntimeStateMachine.record_verification(agent_run, verification)
                await self._checkpoint(agent_run)
            decision = await _resolve(self.decision_provider(agent_run))
            decisions += 1
            RuntimeStateMachine.apply_decision(agent_run, decision)
            await self._emit_decision(agent_run, decision)

            if decision.action == DecisionAction.REPLAN:
                if self.replan_provider is None:
                    raise ValueError("replan decision requires replan_provider")
                plan = await _resolve(
                    self.replan_provider(agent_run, decision)
                )
                if self.plan_proposal_provider is not None:
                    proposal = await _resolve(
                        self.plan_proposal_provider(
                            agent_run,
                            decision,
                            plan,
                        )
                    )
                    if proposal.status == RuntimePlanProposalStatus.PENDING:
                        control_data = dict(agent_run.control_data)
                        control_data["plan_proposal_id"] = (
                            proposal.proposal_id
                        )
                        control_data["plan_proposal_status"] = "pending"
                        agent_run.control_data = control_data
                        agent_run.status = RuntimeRunStatus.WAITING_APPROVAL
                        await self._checkpoint(agent_run)
                        return agent_run
                    if proposal.status == RuntimePlanProposalStatus.REJECTED:
                        agent_run.status = RuntimeRunStatus.PAUSED
                        await self._checkpoint(agent_run)
                        return agent_run
                    plan = proposal.proposed_plan
                RuntimeStateMachine.replace_plan(agent_run, plan)
                await self._checkpoint(agent_run)
                continue
            if decision.action == DecisionAction.EXECUTE:
                await self.executor.execute(
                    agent_run,
                    node_ids=decision.node_ids,
                )
                # ``PARTIAL`` is a terminal node state, but not a terminal
                # Runtime outcome: the decision provider still needs to
                # choose fail, ask-user, or replan from the verification
                # facts. Returning here would silently turn an unverified
                # result into a successful task.
                has_partial_node = any(
                    state.status == RuntimeNodeStatus.PARTIAL
                    for state in agent_run.nodes.values()
                )
                if (
                    agent_run.status.value == "completed"
                    and not has_partial_node
                ):
                    await self._checkpoint_after_executor(agent_run)
                    return agent_run
                if (
                    agent_run.status.value == "failed"
                    and self.replan_provider is None
                ):
                    await self._checkpoint_after_executor(agent_run)
                    return agent_run
                if agent_run.status.value in {
                    "waiting_input",
                    "waiting_approval",
                    "paused",
                }:
                    await self._checkpoint_after_executor(agent_run)
                    return agent_run
                continue
            await self._checkpoint(agent_run)
            if decision.action in {
                DecisionAction.ASK_USER,
                DecisionAction.REQUEST_APPROVAL,
                DecisionAction.PAUSE,
                DecisionAction.FINISH,
                DecisionAction.FAIL,
            }:
                return agent_run

        agent_run.status = RuntimeRunStatus.FAILED
        await self._checkpoint(agent_run)
        return agent_run

    async def _control(self, agent_run: AgentRun) -> RuntimeDecision | None:
        if self.control_provider is None:
            return None
        value = await _resolve(self.control_provider(agent_run))
        return cast(RuntimeDecision | None, value)

    async def _verify(self, agent_run: AgentRun) -> RuntimeObservation | None:
        if self.verifier is None:
            return None
        result = self.verifier(agent_run)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _checkpoint(self, agent_run: AgentRun) -> None:
        if self.checkpoint_hook is None:
            return
        await _resolve(self.checkpoint_hook(agent_run))

    async def _checkpoint_after_executor(self, agent_run: AgentRun) -> None:
        """Keep a fallback checkpoint for executors without persistence.

        Production Runtime wires the same checkpoint boundary into both the
        controller and PlanExecutor.  The executor has already persisted the
        terminal/waiting transition, so repeating it here only adds a durable
        snapshot and transaction.  Standalone callers that provide a
        controller-only hook retain the older safety behavior.
        """

        if self.executor.checkpoint_hook is None:
            await self._checkpoint(agent_run)

    async def _emit_decision(
        self, agent_run: AgentRun, decision: RuntimeDecision
    ) -> None:
        if self.decision_event_hook is None:
            return
        await _resolve(self.decision_event_hook(agent_run, decision))


async def _resolve(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value
