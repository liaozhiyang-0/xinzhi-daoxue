"""Runtime adapter for the local, evidence-grounded Knowledge QA Agent."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.contracts import AgentRequest, AgentResult, AgentResultStatus
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
from app.services.knowledge_qa_service import KnowledgeQAService


class KnowledgeQARuntimeService:
    """Execute retrieval-only QA through a durable execute/verify Plan."""

    agent_id = "LEARN_01_LOCAL_RETRIEVAL_V1"
    runtime_option_key = "knowledge_qa_runtime"
    runtime_plan_version = "knowledge-qa-v1"
    execute_node_id = "knowledge.execute"
    verify_node_id = "knowledge.verify"

    def __init__(self, knowledge_qa: KnowledgeQAService, *, enabled: bool) -> None:
        self.knowledge_qa = knowledge_qa
        self.enabled = enabled

    def supports(self, agent_id: str, request: AgentRequest) -> bool:
        options = request.options.get(self.runtime_option_key)
        return (
            self.enabled
            and agent_id == self.agent_id
            and isinstance(options, dict)
            and options.get("execute", True) is True
        )

    def build_plan(
        self, request: AgentRequest, *, iteration: int = 0
    ) -> AgentRunPlan:
        del request
        suffix = "" if iteration == 0 else f".replan.{iteration}"
        execute_node_id = f"{self.execute_node_id}{suffix}"
        verify_node_id = f"{self.verify_node_id}{suffix}"
        return AgentRunPlan(
            plan_id="knowledge-qa-runtime",
            version="knowledge-qa-v1",
            goal="answer the learner using bounded local evidence",
            nodes=[
                RuntimeNode(
                    node_id=execute_node_id,
                    node_type="workflow",
                    handler_id="knowledge.qa.execute",
                    timeout_ms=900_000,
                    max_retries=0,
                ),
                RuntimeNode(
                    node_id=verify_node_id,
                    node_type="verification",
                    handler_id="knowledge.qa.verify",
                    depends_on=[execute_node_id],
                    timeout_ms=30_000,
                ),
            ],
            success_criteria=[
                "knowledge_answer_present",
                "knowledge_result_contract_verified",
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

    @staticmethod
    def _evidence_count(run: AgentRun, result: AgentResult) -> int:
        """Recover the retrieval count without changing the result contract."""
        observations = [*run.observations]
        for state in run.nodes.values():
            if state.observation is not None:
                observations.append(state.observation)
        for observation in reversed(observations):
            count = observation.facts.get("evidence_count")
            if isinstance(count, int) and count >= 0:
                return count
        structured_count = result.structured_result.get("evidence_count")
        if isinstance(structured_count, int) and structured_count >= 0:
            return structured_count
        return len(result.citations)

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
        result_holder: dict[str, AgentResult] = {}
        restored = self._restore_result(run)
        if restored is not None:
            result_holder["result"] = restored
        registry = RuntimeHandlerRegistry()

        async def execute_handler(
            _run: AgentRun, _node: RuntimeNode
        ) -> RuntimeObservation:
            execution = await self.knowledge_qa.run_with_generation(
                self.agent_id, request
            )
            result_holder["result"] = execution.result
            return RuntimeObservation(
                node_id=_node.node_id,
                artifact_ids=[
                    item.artifact_id for item in execution.result.artifacts
                ],
                facts={
                    "result_status": execution.result.status.value,
                    "mode": str(
                        execution.result.structured_result.get("mode", "")
                    ),
                    "evidence_status": execution.context.evidence_status,
                    "evidence_count": len(execution.context.evidence),
                    "result_payload": execution.result.model_dump(mode="json"),
                },
                warnings=list(execution.result.warnings[:8]),
            )

        def verify_handler(
            _run: AgentRun, _node: RuntimeNode
        ) -> RuntimeObservation:
            result = result_holder.get("result")
            if result is None:
                raise RuntimeNodeError(
                    "knowledge_result_missing",
                    "knowledge verification requires an execution result",
                )
            mode = str(result.structured_result.get("mode", ""))
            evidence_status = result.evidence_status.strip().lower()
            evidence_count = self._evidence_count(_run, result)
            citation_count = len(result.citations)
            has_artifact = bool(result.artifacts)
            passed = (
                result.status != AgentResultStatus.FAILED
                and bool(result.answer.strip())
                and mode in {"retrieval_only", "local_rag_model_generation"}
            )
            facts = {
                "passed": passed,
                "result_status": result.status.value,
                "mode": mode,
                "evidence_status": evidence_status,
                "evidence_count": evidence_count,
                "citation_count": citation_count,
            }
            if evidence_status in {"sufficient", "complete"} and not (
                citation_count or has_artifact
            ):
                return RuntimeObservation(
                    node_id=_node.node_id,
                    terminal_status=RuntimeNodeStatus.PARTIAL,
                    artifact_ids=[],
                    facts={
                        **facts,
                        "passed": False,
                        "needs_review": True,
                        "reason_code": "knowledge_citations_missing",
                    },
                    warnings=list(result.warnings[:8]),
                )
            if evidence_status in {"insufficient", "none"}:
                return RuntimeObservation(
                    node_id=_node.node_id,
                    terminal_status=RuntimeNodeStatus.PARTIAL,
                    artifact_ids=[item.artifact_id for item in result.artifacts],
                    facts={
                        **facts,
                        "passed": False,
                        "needs_review": True,
                        "reason_code": "knowledge_evidence_insufficient",
                    },
                    warnings=list(result.warnings[:8]),
                )
            if not passed:
                return RuntimeObservation(
                    node_id=_node.node_id,
                    terminal_status=RuntimeNodeStatus.PARTIAL,
                    artifact_ids=[item.artifact_id for item in result.artifacts],
                    facts={**facts, "passed": False, "replan_required": False},
                    warnings=list(result.warnings[:8]),
                )
            return RuntimeObservation(
                node_id=_node.node_id,
                artifact_ids=[item.artifact_id for item in result.artifacts],
                facts={**facts, "passed": True},
            )

        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="knowledge.qa.execute",
                kind="workflow",
                max_timeout_ms=900_000,
            ),
            execute_handler,
        )
        registry.register(
            RuntimeHandlerDescriptor(
                handler_id="knowledge.qa.verify",
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
                    reason_codes=["knowledge_execution_required"],
                )
            if verify_state.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                if verify_state.status == RuntimeNodeStatus.PARTIAL:
                    return RuntimeDecision(
                        action=DecisionAction.FAIL,
                        reason_codes=["knowledge_verification_failed"],
                    )
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[verify_node_id],
                    reason_codes=["knowledge_verification_required"],
                )
            return RuntimeDecision(
                action=DecisionAction.FINISH,
                reason_codes=["knowledge_runtime_verified"],
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
            raise RuntimeNodeError("knowledge_result_missing")
        return result
