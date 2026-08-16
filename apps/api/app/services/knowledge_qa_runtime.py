"""Runtime adapter for evidence-grounded Knowledge QA and synthesis."""

from __future__ import annotations

from collections.abc import Callable, Mapping
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
    """Execute bounded retrieval and configured model synthesis through Runtime."""

    agent_id = "LEARN_01_LOCAL_RETRIEVAL_V1"
    supported_agent_ids = frozenset(
        {"LEARN_01_LOCAL_RETRIEVAL_V1", "LEARN_01_KNOWLEDGE_QA_V1"}
    )
    runtime_option_key = "knowledge_qa_runtime"
    runtime_plan_version = "knowledge-qa-v1"
    # The public task route may use retrieval-only mode without an explicit
    # Runtime option.  In that default path an empty local index is a useful,
    # reviewable answer rather than a transport failure; explicit Runtime
    # callers keep the stricter evidence contract below.
    allow_default_incomplete_evidence = True
    execute_node_id = "knowledge.execute"
    verify_node_id = "knowledge.verify"
    max_user_input_chars = 2_000
    replan_failure_reasons = frozenset(
        {
            "knowledge_evidence_insufficient",
            "knowledge_citations_missing",
        }
    )

    def __init__(self, knowledge_qa: KnowledgeQAService, *, enabled: bool) -> None:
        self.knowledge_qa = knowledge_qa
        self.enabled = enabled

    def supports(self, agent_id: str, request: AgentRequest) -> bool:
        options = request.options.get(self.runtime_option_key)
        return (
            self.enabled
            and agent_id in self.supported_agent_ids
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
            goal="answer using bounded course evidence and configured synthesis",
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

    @classmethod
    def _runtime_options(cls, request: AgentRequest) -> dict[str, Any]:
        options = request.options.get(cls.runtime_option_key)
        return dict(options) if isinstance(options, dict) else {}

    @classmethod
    def _replan_enabled(cls, request: AgentRequest) -> bool:
        return cls._runtime_options(request).get(
            "replan_on_verification_failure"
        ) is True

    @classmethod
    def _validated_user_input(
        cls, raw_input: Any
    ) -> tuple[str, str] | None:
        """Return one bounded query/text value, rejecting all other shapes."""

        if not isinstance(raw_input, Mapping):
            return None
        if set(raw_input) - {"query", "text"}:
            return None
        values: list[tuple[str, str]] = []
        for field in ("query", "text"):
            if field not in raw_input:
                continue
            value = raw_input[field]
            if not isinstance(value, str):
                return None
            normalized = value.strip()
            if not normalized or len(normalized) > cls.max_user_input_chars:
                return None
            values.append((field, normalized))
        if len(values) != 1:
            return None
        return values[0]

    @staticmethod
    def _sync_request(run: AgentRun, request: AgentRequest) -> None:
        control_data = dict(run.control_data)
        control_data["request"] = request.model_dump(mode="json")
        run.control_data = control_data

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
        request_for_attempt = request
        was_waiting_for_input = run.status == RuntimeRunStatus.WAITING_INPUT
        stored_request = run.control_data.get("request")
        if isinstance(stored_request, Mapping):
            try:
                request_for_attempt = AgentRequest.model_validate(stored_request)
            except ValueError:
                request_for_attempt = request
        self._sync_request(run, request_for_attempt)
        restored = self._restore_result(run)
        if restored is not None:
            result_holder["result"] = restored
        registry = RuntimeHandlerRegistry()

        async def execute_handler(
            _run: AgentRun, _node: RuntimeNode
        ) -> RuntimeObservation:
            execution = await self.knowledge_qa.run_with_generation(
                self.agent_id, request_for_attempt
            )
            result_holder["result"] = execution.result
            routed_agent_id = (
                _run.launch_decision.agent_id
                if _run.launch_decision is not None
                else self.agent_id
            )
            if execution.result.agent_id != routed_agent_id:
                result_holder["result"] = execution.result.model_copy(
                    update={"agent_id": routed_agent_id}
                )
            return RuntimeObservation(
                node_id=_node.node_id,
                artifact_ids=[
                    item.artifact_id
                    for item in result_holder["result"].artifacts
                ],
                facts={
                    "result_status": result_holder["result"].status.value,
                    "mode": str(
                        result_holder["result"].structured_result.get("mode", "")
                    ),
                    "evidence_status": execution.context.evidence_status,
                    "evidence_count": len(execution.context.evidence),
                    "result_payload": result_holder["result"].model_dump(
                        mode="json"
                    ),
                },
                warnings=list(result_holder["result"].warnings[:8]),
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
                and mode
                in {
                    "retrieval_only",
                    "local_rag_model_generation",
                    "learning_path_model_generation",
                    "governance_model_generation",
                }
            )
            # Governance and learning-path synthesis have a valid evidence
            # boundary even when the local course index contributes no hit:
            # the former audits asset records in the prompt and the latter
            # audits user-supplied learning evidence.  Keep the result
            # completed-with-gaps so the user can review it, rather than
            # converting a useful model synthesis into a generic task failure.
            incomplete_synthesis = mode in {
                "learning_path_model_generation",
                "governance_model_generation",
            }
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
            if evidence_status in {"insufficient", "none"} and not (
                passed and incomplete_synthesis
            ):
                if (
                    passed
                    and mode == "retrieval_only"
                    and self._runtime_options(request_for_attempt).get(
                        "allow_incomplete_evidence"
                    ) is True
                ):
                    return RuntimeObservation(
                        node_id=_node.node_id,
                        terminal_status=RuntimeNodeStatus.SUCCEEDED,
                        artifact_ids=[item.artifact_id for item in result.artifacts],
                        facts={
                            **facts,
                            "passed": True,
                            "evidence_incomplete": True,
                            "needs_review": True,
                            "reason_code": "knowledge_evidence_incomplete_review",
                        },
                        warnings=list(result.warnings[:8]),
                    )
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
            if passed and incomplete_synthesis and evidence_status in {
                "insufficient",
                "none",
                "partial",
            }:
                return RuntimeObservation(
                    node_id=_node.node_id,
                    terminal_status=RuntimeNodeStatus.SUCCEEDED,
                    artifact_ids=[item.artifact_id for item in result.artifacts],
                    facts={
                        **facts,
                        "passed": True,
                        "evidence_incomplete": True,
                        "needs_review": True,
                        "reason_code": "knowledge_evidence_incomplete_review",
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
                    observation = verify_state.observation
                    reason_code = (
                        str(observation.facts.get("reason_code", ""))
                        if observation is not None
                        else ""
                    )
                    if (
                        self._replan_enabled(request_for_attempt)
                        and reason_code in self.replan_failure_reasons
                    ):
                        if not was_waiting_for_input:
                            return RuntimeDecision(
                                action=DecisionAction.ASK_USER,
                                user_prompt=(
                                    "请补充一个更具体的问题或检索关键词，"
                                    "以便重新检索本地课程证据。"
                                ),
                                reason_codes=[
                                    "knowledge_verification_input_required"
                                ],
                            )
                        user_input = self._validated_user_input(
                            current.control_data.get("user_input")
                        )
                        if user_input is None:
                            return RuntimeDecision(
                                action=DecisionAction.FAIL,
                                reason_codes=["knowledge_user_input_invalid"],
                            )
                        if (
                            current.iteration > 0
                            or current.iteration
                            >= current.budget.max_iterations - 1
                        ):
                            return RuntimeDecision(
                                action=DecisionAction.FAIL,
                                reason_codes=[
                                    "knowledge_replan_budget_exhausted"
                                ],
                            )
                        return RuntimeDecision(
                            action=DecisionAction.REPLAN,
                            reason_codes=[
                                "knowledge_verification_requires_replan"
                            ],
                        )
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

        async def replan(
            current: AgentRun, _decision: RuntimeDecision
        ) -> AgentRunPlan:
            nonlocal request_for_attempt
            user_input = self._validated_user_input(
                current.control_data.get("user_input")
            )
            if user_input is None:
                # The decision provider already rejects this path. Keep the
                # replan boundary defensive in case a future controller calls
                # the provider directly or a checkpoint is malformed.
                raise RuntimeNodeError("knowledge_user_input_invalid")
            field, value = user_input
            canonical_input = dict(request_for_attempt.canonical_input)
            canonical_input["text"] = value
            canonical_input[field] = value
            options = dict(request_for_attempt.options)
            runtime_options = self._runtime_options(request_for_attempt)
            runtime_options["runtime_replan_iteration"] = current.iteration
            options[self.runtime_option_key] = runtime_options
            options["runtime_user_input"] = {field: value}
            request_for_attempt = request_for_attempt.model_copy(
                update={
                    "canonical_input": canonical_input,
                    "options": options,
                }
            )
            self._sync_request(current, request_for_attempt)
            return self.build_plan(request_for_attempt, iteration=current.iteration)

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
            replan_provider=replan,
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
