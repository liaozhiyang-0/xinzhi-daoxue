"""Explicit structured-goal Runtime execution over registered handlers."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from app.contracts import AgentRequest, AgentResult, AgentResultStatus, RunMetrics
from app.core.errors import NotConfiguredError
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    PlanExecutor,
    PlanProposalProvider,
    RuntimeController,
    RuntimeDecision,
    RuntimeGoal,
    RuntimeGoalPlanner,
    RuntimeHandlerRegistry,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
    RuntimeRunSuspended,
)
from app.runtime.executor import RuntimeNodeError
from app.services.runtime_goal_intake import RuntimeGoalIntakePolicy


class GenericGoalRuntimeService:
    """Run only explicitly declared structured goals through the Runtime."""

    agent_id = "*"
    runtime_option_key = "runtime_goal_runtime"
    runtime_plan_version = "goal-runtime-v1"

    def __init__(
        self,
        handler_registry: RuntimeHandlerRegistry,
        *,
        intake_policy: RuntimeGoalIntakePolicy | None = None,
    ) -> None:
        self.handler_registry = handler_registry
        self.planner = RuntimeGoalPlanner(handler_registry)
        self.intake_policy = intake_policy or RuntimeGoalIntakePolicy({})

    def supports(self, _agent_id: str, request: AgentRequest) -> bool:
        options = request.options.get(self.runtime_option_key)
        return isinstance(options, Mapping) and options.get("execute") is True

    def build_plan(self, request: AgentRequest) -> AgentRunPlan:
        return self.build_plan_for_agent(
            self._request_agent_id(request), request
        )

    def build_plan_for_agent(
        self, agent_id: str, request: AgentRequest
    ) -> AgentRunPlan:
        options = self._options(request)
        goal = self._goal(options)
        return self._build_plan_for_goal(
            agent_id,
            request,
            goal,
            max_parallelism=self._max_parallelism(options),
        )

    def _build_plan_for_goal(
        self,
        agent_id: str,
        request: AgentRequest,
        goal: RuntimeGoal,
        *,
        max_parallelism: int = 1,
        iteration: int = 0,
    ) -> AgentRunPlan:
        planned = self.planner.build(
            goal,
            plan_id=f"runtime-goal:{request.task_id}",
            version=f"{self.runtime_plan_version}.r{iteration}",
            max_parallelism=max_parallelism,
        )
        intake = self.intake_policy.validate(
            agent_id, goal, planned.selections
        )
        return planned.plan.model_copy(
            update={
                "goal_contract": goal.model_copy(
                    update={
                        "context": {
                            **goal.context,
                            "intake": intake.model_dump(mode="json"),
                        }
                    }
                )
            }
        )

    async def run(
        self,
        request: AgentRequest,
        run: AgentRun,
        context: Any = None,
        checkpoint_hook: Callable[[AgentRun], Any] | None = None,
        event_hook: Callable[[str, AgentRun, str], Any] | None = None,
        control_provider: Callable[[AgentRun], Any] | None = None,
        decision_event_hook: Callable[[AgentRun, RuntimeDecision], Any]
        | None = None,
        plan_proposal_provider: PlanProposalProvider | None = None,
    ) -> AgentResult:
        del context
        self._sync_request(run, request)
        agent_id = (
            run.launch_decision.agent_id
            if run.launch_decision is not None
            else self._request_agent_id(request)
        )

        def decide(current: AgentRun) -> RuntimeDecision:
            statuses = [state.status for state in current.nodes.values()]
            failed = any(
                status in {RuntimeNodeStatus.FAILED, RuntimeNodeStatus.PARTIAL}
                for status in statuses
            )
            if failed:
                if (
                    current.iteration >= current.budget.max_iterations - 1
                    or not self._fallback_capabilities(current)
                ):
                    return RuntimeDecision(
                        action=DecisionAction.FAIL,
                        reason_codes=["goal_runtime_node_failed"],
                    )
                return RuntimeDecision(
                    action=DecisionAction.REPLAN,
                    reason_codes=["goal_runtime_verification_failed"],
                )
            if statuses and all(
                status
                in {
                    RuntimeNodeStatus.SUCCEEDED,
                    RuntimeNodeStatus.SKIPPED,
                }
                for status in statuses
            ):
                return RuntimeDecision(
                    action=DecisionAction.FINISH,
                    reason_codes=["goal_runtime_verified"],
                )
            return RuntimeDecision(
                action=DecisionAction.EXECUTE,
                node_ids=list(current.nodes),
                reason_codes=["goal_runtime_capabilities_required"],
            )

        async def replan(
            current: AgentRun, _decision: RuntimeDecision
        ) -> AgentRunPlan:
            previous_goal = current.goal_contract or RuntimeGoal(
                objective=current.goal
            )
            fallback = self._fallback_capabilities(current)
            if not fallback:
                raise RuntimeNodeError("goal_runtime_fallback_missing")
            next_goal = previous_goal.model_copy(
                update={
                    "required_capabilities": fallback,
                    "source": "runtime_replan",
                }
            )
            return self._build_plan_for_goal(
                agent_id,
                request,
                next_goal,
                max_parallelism=current.plan.max_parallelism,
                iteration=current.iteration,
            )

        def verify(current: AgentRun) -> RuntimeObservation:
            statuses = {
                node_id: state.status.value
                for node_id, state in current.nodes.items()
            }
            passed = all(
                status in {"succeeded", "skipped"}
                for status in statuses.values()
            )
            return RuntimeObservation(
                node_id="runtime.goal.verify",
                terminal_status=(
                    RuntimeNodeStatus.SUCCEEDED
                    if passed
                    else RuntimeNodeStatus.PARTIAL
                ),
                facts={
                    "goal_contract": current.goal_contract.model_dump(mode="json")
                    if current.goal_contract is not None
                    else {},
                    "node_statuses": statuses,
                    "verified": passed,
                },
            )

        controller = RuntimeController(
            PlanExecutor(
                self.handler_registry,
                checkpoint_hook=checkpoint_hook,
                event_hook=event_hook,
            ),
            decide,
            verifier=verify,
            checkpoint_hook=checkpoint_hook,
            control_provider=control_provider,
            decision_event_hook=decision_event_hook,
            replan_provider=replan,
            plan_proposal_provider=plan_proposal_provider,
        )
        await controller.run(run)
        if run.status in {
            RuntimeRunStatus.WAITING_INPUT,
            RuntimeRunStatus.WAITING_APPROVAL,
            RuntimeRunStatus.PAUSED,
        }:
            raise RuntimeRunSuspended(run)
        if run.status != RuntimeRunStatus.COMPLETED:
            raise RuntimeNodeError(
                "goal_runtime_failed",
                f"structured goal runtime ended with {run.status.value}",
            )
        return self._result(request, run)

    def _result(self, request: AgentRequest, run: AgentRun) -> AgentResult:
        answer = self._answer(run)
        return AgentResult(
            status=AgentResultStatus.COMPLETED,
            agent_id=request.options.get("runtime_agent_id", "RUNTIME_GOAL"),
            provider="runtime",
            answer=answer,
            structured_result={
                "runtime_goal": (
                    run.goal_contract.model_dump(mode="json")
                    if run.goal_contract is not None
                    else {"objective": run.goal}
                ),
                "goal_intake": run.control_data.get("goal_intake", {}),
                "iteration": run.iteration,
                "last_decision": (
                    run.last_decision.model_dump(mode="json")
                    if run.last_decision is not None
                    else None
                ),
                "node_statuses": {
                    node_id: state.status.value
                    for node_id, state in run.nodes.items()
                },
                "observations": [
                    observation.model_dump(mode="json")
                    for observation in run.observations[-16:]
                ],
            },
            metrics=RunMetrics(
                model_calls=run.budget.model_calls,
                tool_calls=run.budget.tool_calls,
                provider_used="runtime",
                quality_status="runtime_verified",
            ),
            trace_id=str(request.options.get("trace_id", "")),
            task_id=request.task_id,
            request_id=str(request.options.get("request_id", "")),
        )

    @classmethod
    def _options(cls, request: AgentRequest) -> dict[str, Any]:
        raw = request.options.get(cls.runtime_option_key)
        if not isinstance(raw, Mapping) or raw.get("execute") is not True:
            raise NotConfiguredError("structured goal Runtime is not enabled")
        return dict(raw)

    @classmethod
    def _goal(cls, options: Mapping[str, Any]) -> RuntimeGoal:
        raw_goal = options.get("goal")
        if isinstance(raw_goal, Mapping):
            return RuntimeGoal.model_validate(dict(raw_goal))
        goal_data = {
            key: value
            for key, value in options.items()
            if key not in {"execute", "node_inputs", "max_parallelism"}
        }
        try:
            return RuntimeGoal.model_validate(goal_data)
        except ValueError as exc:
            raise NotConfiguredError(
                "runtime_goal_runtime requires a structured goal"
            ) from exc

    @staticmethod
    def _max_parallelism(options: Mapping[str, Any]) -> int:
        """Validate request-controlled parallelism before plan compilation."""

        value = options.get("max_parallelism", 1)
        if isinstance(value, bool) or not isinstance(value, int):
            raise NotConfiguredError(
                "runtime_goal_runtime max_parallelism must be an integer"
            )
        if not 1 <= value <= 32:
            raise NotConfiguredError(
                "runtime_goal_runtime max_parallelism must be between 1 and 32"
            )
        return value

    @classmethod
    def _sync_request(cls, run: AgentRun, request: AgentRequest) -> None:
        options = cls._options(request)
        control_data = dict(run.control_data)
        control_data["request"] = request.model_dump(mode="json")
        node_inputs = options.get("node_inputs", {})
        if isinstance(node_inputs, Mapping):
            control_data["node_inputs"] = dict(node_inputs)
        if run.goal_contract is not None:
            control_data["goal_intake"] = run.goal_contract.context.get(
                "intake", {}
            )
        run.control_data = control_data

    @staticmethod
    def _request_agent_id(request: AgentRequest) -> str:
        direct = request.options.get("runtime_agent_id")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        routing = request.options.get("_routing")
        if isinstance(routing, Mapping):
            routed = routing.get("agent_id")
            if isinstance(routed, str) and routed.strip():
                return routed.strip()
        return "request"

    @staticmethod
    def _fallback_capabilities(run: AgentRun) -> list[str]:
        goal = run.goal_contract
        if goal is None:
            return []
        raw = goal.constraints.get("fallback_capabilities")
        if not isinstance(raw, list):
            return []
        if not raw or len(raw) > 16 or not all(
            isinstance(item, str) for item in raw
        ):
            return []
        values = [item.strip() for item in raw]
        return values if all(values) else []

    @staticmethod
    def _answer(run: AgentRun) -> str:
        for node_id in reversed(list(run.nodes)):
            observation = run.nodes[node_id].observation
            if observation is None:
                continue
            facts = observation.facts
            for key in ("answer", "output"):
                value = facts.get(key)
                if isinstance(value, str) and value.strip():
                    return value
                if isinstance(value, (int, float, bool)):
                    return str(value)
                if isinstance(value, (dict, list)):
                    return json.dumps(value, ensure_ascii=False)
        return f"Runtime completed {len(run.nodes)} declared capabilities."
