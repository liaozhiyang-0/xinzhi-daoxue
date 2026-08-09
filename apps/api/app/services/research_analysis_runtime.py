from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.contracts import AgentRequest, AgentResult, AgentResultStatus
from app.contracts.research_analysis import ResearchAnalysisRequest
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    PlanExecutor,
    PlanProposalProvider,
    RuntimeController,
    RuntimeDecision,
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeNode,
    RuntimeNodeError,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
    RuntimeRunSuspended,
)
from app.services.internal_agent_execution import InternalAgentExecutionService


class ResearchAnalysisRuntimeService:
    """Execute Research Analysis V2 through a small, auditable Runtime DAG."""

    agent_id = "RESEARCH_03_DATA_ANALYSIS_V1"
    runtime_option_key = "research_analysis_v2"
    execute_node_id = "analysis.execute"
    verify_node_id = "analysis.verify"

    def __init__(
        self,
        internal_agents: InternalAgentExecutionService,
        *,
        enabled: bool,
    ) -> None:
        self.internal_agents = internal_agents
        self.enabled = enabled

    def supports(self, agent_id: str, request: AgentRequest) -> bool:
        return (
            self.enabled
            and agent_id == self.agent_id
            and isinstance(request.options.get("research_analysis_v2"), dict)
        )

    def build_plan(
        self,
        request: AgentRequest,
        *,
        iteration: int = 0,
    ) -> AgentRunPlan:
        options = request.options.get("research_analysis_v2")
        if not isinstance(options, dict):
            raise ValueError("research_analysis_v2_options_missing")
        payload = options.get("request", options)
        analysis_request = ResearchAnalysisRequest.model_validate(payload)
        suffix = "" if iteration == 0 else f".replan.{iteration}"
        execute_node_id = f"{self.execute_node_id}{suffix}"
        verify_node_id = f"{self.verify_node_id}{suffix}"
        return AgentRunPlan(
            plan_id=f"research-runtime:{(request.task_id or 'request')[-80:]}",
            version="research-v2",
            goal=analysis_request.research_question,
            nodes=[
                RuntimeNode(
                    node_id=execute_node_id,
                    node_type="workflow",
                    handler_id="research.analysis.execute",
                    timeout_ms=900_000,
                    max_retries=0,
                ),
                RuntimeNode(
                    node_id=verify_node_id,
                    node_type="verification",
                    handler_id="research.analysis.verify",
                    depends_on=[execute_node_id],
                    timeout_ms=30_000,
                ),
            ],
            success_criteria=[
                "analysis_result_present",
                "analysis_result_passes_runtime_verification",
            ],
        )

    @staticmethod
    def _current_node_ids(run: AgentRun) -> tuple[str, str]:
        execute_node = next(
            node for node in run.plan.nodes if node.node_type == "workflow"
        )
        verify_node = next(
            node for node in run.plan.nodes if node.node_type == "verification"
        )
        return execute_node.node_id, verify_node.node_id

    @staticmethod
    def _restore_result(run: AgentRun) -> AgentResult | None:
        """Restore the last durable business result after worker restart."""

        observations = [*run.observations]
        for state in run.nodes.values():
            if state.observation is not None:
                observations.append(state.observation)
        for observation in reversed(observations):
            payload = observation.facts.get("result_payload")
            if not isinstance(payload, dict):
                continue
            try:
                return AgentResult.model_validate(payload)
            except ValueError:
                continue
        return None

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
        result_holder: dict[str, AgentResult] = {}
        request_for_attempt = request
        restored_result = self._restore_result(run)
        if restored_result is not None:
            result_holder["result"] = restored_result
        registry = RuntimeHandlerRegistry()

        async def execute_handler(
            _run: AgentRun, _node: RuntimeNode
        ) -> RuntimeObservation:
            nonlocal request_for_attempt
            user_input = _run.control_data.get("user_input")
            if isinstance(user_input, dict):
                options = dict(request_for_attempt.options)
                options["runtime_user_input"] = dict(user_input)
                request_for_attempt = request_for_attempt.model_copy(
                    update={"options": options}
                )
            result = await self.internal_agents.run(
                self.agent_id,
                request_for_attempt,
                context,
            )
            result_holder["result"] = result
            return RuntimeObservation(
                node_id=_node.node_id,
                artifact_ids=[item.artifact_id for item in result.artifacts],
                facts={
                    "result_status": result.status.value,
                    "provider": result.provider,
                    "analysis_v2": bool(
                        result.structured_result.get("analysis_v2")
                    ),
                    "result_payload": result.model_dump(mode="json"),
                },
                warnings=list(result.warnings[:8]),
            )

        def verify_handler(
            _run: AgentRun, _node: RuntimeNode
        ) -> RuntimeObservation:
            result = result_holder.get("result")
            if result is None:
                raise RuntimeNodeError(
                    "analysis_result_missing",
                    "analysis verification requires an execution result",
                )
            if result.status == AgentResultStatus.FAILED:
                return RuntimeObservation(
                    node_id=_node.node_id,
                    terminal_status=RuntimeNodeStatus.PARTIAL,
                    artifact_ids=[item.artifact_id for item in result.artifacts],
                    facts={
                        "passed": False,
                        "replan_required": True,
                        "result_status": result.status.value,
                    },
                    warnings=list(result.warnings[:8]),
                )
            structured = result.structured_result
            if not bool(structured.get("analysis_v2")):
                raise RuntimeNodeError(
                    "analysis_result_contract_invalid",
                    "research analysis result is missing analysis_v2 marker",
                )
            return RuntimeObservation(
                node_id=_node.node_id,
                artifact_ids=[item.artifact_id for item in result.artifacts],
                facts={
                    "passed": True,
                    "result_status": result.status.value,
                    "business_data_present": bool(result.business_data),
                },
            )

        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="research.analysis.execute",
                kind="workflow",
                max_timeout_ms=900_000,
            ),
            execute_handler,
        )
        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="research.analysis.verify",
                kind="tool",
                max_timeout_ms=30_000,
            ),
            verify_handler,
        )

        def decide(current: AgentRun) -> RuntimeDecision:
            execute_node_id, verify_node_id = self._current_node_ids(current)
            execute_state = current.nodes[execute_node_id]
            verify_state = current.nodes[verify_node_id]
            if execute_state.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[execute_node_id],
                    reason_codes=["analysis_execution_required"],
                )
            if verify_state.status == RuntimeNodeStatus.PARTIAL:
                if current.iteration >= current.budget.max_iterations - 1:
                    return RuntimeDecision(
                        action=DecisionAction.FAIL,
                        reason_codes=["analysis_replan_budget_exhausted"],
                    )
                return RuntimeDecision(
                    action=DecisionAction.REPLAN,
                    reason_codes=["analysis_verification_requires_replan"],
                )
            if verify_state.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[verify_node_id],
                    reason_codes=["analysis_verification_required"],
                )
            return RuntimeDecision(
                action=DecisionAction.FINISH,
                reason_codes=["analysis_runtime_verified"],
            )

        async def replan(
            current: AgentRun, _decision: RuntimeDecision
        ) -> AgentRunPlan:
            nonlocal request_for_attempt
            options = dict(request_for_attempt.options)
            analysis_options = dict(
                options.get("research_analysis_v2", {})
            )
            analysis_options["runtime_replan_iteration"] = current.iteration
            options["research_analysis_v2"] = analysis_options
            request_for_attempt = request_for_attempt.model_copy(
                update={"options": options}
            )
            return self.build_plan(
                request_for_attempt,
                iteration=current.iteration,
            )

        controller = RuntimeController(
            PlanExecutor(
                registry,
                checkpoint_hook=checkpoint_hook,
                event_hook=event_hook,
            ),
            decide,
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
        result = result_holder.get("result")
        if result is None:
            raise RuntimeNodeError("analysis_result_missing")
        if (
            run.status.value != "completed"
            and result.status != AgentResultStatus.FAILED
        ):
            error_code = next(
                (
                    state.error_code
                    for state in run.nodes.values()
                    if state.error_code
                ),
                "analysis_runtime_failed",
            )
            raise RuntimeNodeError(
                error_code,
                f"research analysis runtime ended with {run.status.value}",
            )
        return result
