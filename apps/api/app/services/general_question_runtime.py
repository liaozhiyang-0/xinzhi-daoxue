from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping
from typing import Any

from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentResultStatus,
    KnowledgeHit,
)
from app.infrastructure import register_subagent_handlers
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
    RuntimeSubagentDefinition,
    RuntimeSubagentRegistry,
    RuntimeSubagentRegistryError,
)
from app.services.internal_agent_execution import InternalAgentExecutionService
from app.services.rag_retrieval import RAGRetrievalService
from app.services.retrieval_context import RetrievalContextService
from app.services.runtime_child_run import RuntimeChildRunService
from app.tools.registry import ToolRegistry


class GeneralQuestionRuntimeService:
    """Execute general Q&A through an auditable observe/act/verify DAG."""

    agent_id = "GENERAL_QUESTION_V1"
    observe_node_id = "general.observe"
    retrieve_node_id = "general.retrieve"
    tool_node_id = "general.tool"
    execute_node_id = "general.execute"
    verify_node_id = "general.verify"
    runtime_option_key = "general_question_runtime"
    runtime_plan_prefix = "general-runtime"
    runtime_plan_version = "general-qa-v1"
    runtime_name = "general"
    observe_handler_id = "general.question.observe"
    retrieve_handler_id = "general.question.retrieve"
    tool_handler_prefix = "general.question.tool"
    execute_handler_id = "general.question.execute"
    verify_handler_id = "general.question.verify"
    use_typed_subagent = True

    def __init__(
        self,
        internal_agents: InternalAgentExecutionService,
        *,
        enabled: bool,
        auto_enabled: bool = False,
        canary_enabled: bool = False,
        tool_registry: ToolRegistry | None = None,
        rag_retrieval: RAGRetrievalService | None = None,
        retrieval_context: RetrievalContextService | None = None,
        subagent_registry: RuntimeSubagentRegistry | None = None,
        child_run_service: RuntimeChildRunService | None = None,
    ) -> None:
        self.internal_agents = internal_agents
        self.enabled = enabled
        self.auto_enabled = auto_enabled
        self.canary_enabled = canary_enabled
        self.tool_registry = tool_registry
        self.rag_retrieval = rag_retrieval
        self.retrieval_context = retrieval_context
        self.subagent_registry = subagent_registry
        self.child_run_service = child_run_service

    def supports(self, agent_id: str, request: AgentRequest) -> bool:
        options = request.options.get(self.runtime_option_key)
        if options is None:
            return (
                self.enabled
                and self.auto_enabled
                and self.canary_enabled
                and agent_id == self.agent_id
            )
        return (
            self.enabled
            and agent_id == self.agent_id
            and isinstance(options, dict)
            and options.get("execute", True) is True
        )

    def build_plan(
        self,
        request: AgentRequest,
        *,
        iteration: int = 0,
    ) -> AgentRunPlan:
        suffix = "" if iteration == 0 else f".replan.{iteration}"
        execute_node_id = f"{self.execute_node_id}{suffix}"
        verify_node_id = f"{self.verify_node_id}{suffix}"
        observe_node_id = f"{self.observe_node_id}{suffix}"
        tool_id = self._requested_tool_id(request)
        retrieve_requested = self._retrieval_requested(request)
        question = self._question(request)
        nodes = [
            RuntimeNode(
                node_id=observe_node_id,
                node_type="verification",
                handler_id=self.observe_handler_id,
                timeout_ms=10_000,
            )
        ]
        execute_dependencies = [observe_node_id]
        if retrieve_requested:
            self._validate_retrieval_available()
            retrieve_node_id = f"{self.retrieve_node_id}{suffix}"
            nodes.append(
                RuntimeNode(
                    node_id=retrieve_node_id,
                    node_type="tool",
                    handler_id=self.retrieve_handler_id,
                    depends_on=[observe_node_id],
                    timeout_ms=60_000,
                )
            )
            execute_dependencies.append(retrieve_node_id)
        if tool_id:
            self._validate_tool_available(tool_id)
            tool_node_id = f"{self.tool_node_id}{suffix}"
            nodes.append(
                RuntimeNode(
                    node_id=tool_node_id,
                    node_type="tool",
                    handler_id=self._tool_handler_id(tool_id),
                    target_id=tool_id,
                    depends_on=[
                        f"{self.retrieve_node_id}{suffix}"
                        if retrieve_requested
                        else observe_node_id
                    ],
                    timeout_ms=self._tool_timeout_ms(tool_id),
                )
            )
            execute_dependencies = [tool_node_id]
        nodes.extend(
            [
                RuntimeNode(
                    node_id=execute_node_id,
                    node_type=(
                        "subagent" if self.use_typed_subagent else "provider"
                    ),
                    handler_id=(
                        self._subagent_handler_id()
                        if self.use_typed_subagent
                        else self.execute_handler_id
                    ),
                    target_id=self.agent_id if self.use_typed_subagent else "",
                    depends_on=execute_dependencies,
                    timeout_ms=self._subagent_timeout_ms()
                    if self.use_typed_subagent
                    else 120_000,
                    max_retries=1,
                ),
                RuntimeNode(
                    node_id=verify_node_id,
                    node_type="verification",
                    handler_id=self.verify_handler_id,
                    depends_on=[execute_node_id],
                    timeout_ms=30_000,
                ),
            ]
        )
        return AgentRunPlan(
            plan_id=(
                f"{self.runtime_plan_prefix}:{(request.task_id or 'request')[-80:]}"
            ),
            version=self.runtime_plan_version,
            goal=question[:8_000],
            nodes=nodes,
            success_criteria=[
                "answer_present",
                "answer_passes_runtime_verification",
            ],
        )

    def _current_node_ids(
        self,
        run: AgentRun,
    ) -> tuple[str, str | None, str | None, str, str]:
        observe_node = next(
            node
            for node in run.plan.nodes
            if node.handler_id.endswith(".observe")
        )
        execute_node = next(
            node
            for node in run.plan.nodes
            if node.node_id == self.execute_node_id
            or node.node_id.startswith(f"{self.execute_node_id}.")
        )
        verify_node = next(
            node
            for node in run.plan.nodes
            if node.handler_id.endswith(".verify")
        )
        tool_node = next(
            (
                node
                for node in run.plan.nodes
                if node.node_type == "tool"
                and node.handler_id.startswith(f"{self.tool_handler_prefix}.")
            ),
            None,
        )
        retrieve_node = next(
            (
                node
                for node in run.plan.nodes
                if node.handler_id == self.retrieve_handler_id
            ),
            None,
        )
        return (
            observe_node.node_id,
            retrieve_node.node_id if retrieve_node is not None else None,
            tool_node.node_id if tool_node is not None else None,
            execute_node.node_id,
            verify_node.node_id,
        )

    @staticmethod
    def _question(request: AgentRequest) -> str:
        return next(
            (
                str(request.canonical_input[key]).strip()
                for key in ("text", "question", "problem", "query", "prompt")
                if request.canonical_input.get(key)
            ),
            "general question",
        )

    @classmethod
    def _requested_tool_id(cls, request: AgentRequest) -> str:
        runtime_options = request.options.get(cls.runtime_option_key)
        if not isinstance(runtime_options, dict):
            return ""
        return str(runtime_options.get("tool_id", "")).strip()

    @classmethod
    def _retrieval_requested(cls, request: AgentRequest) -> bool:
        runtime_options = request.options.get(cls.runtime_option_key)
        if isinstance(runtime_options, Mapping) and "retrieve" in runtime_options:
            return runtime_options.get("retrieve") is True
        execution_plan = request.options.get("_execution_plan")
        return isinstance(execution_plan, Mapping) and bool(
            execution_plan.get("use_rag", False)
        )

    def _validate_retrieval_available(self) -> None:
        if self.rag_retrieval is None or self.retrieval_context is None:
            raise ValueError("runtime_retrieval_unavailable")

    def _validate_tool_available(self, tool_id: str) -> None:
        if self.tool_registry is None:
            raise ValueError("runtime_tool_registry_unavailable")
        try:
            definition = self.tool_registry.describe(tool_id)
        except KeyError as exc:
            raise ValueError(f"runtime_tool_not_registered:{tool_id}") from exc
        if not definition.enabled:
            raise ValueError(f"runtime_tool_disabled:{tool_id}")

    def _tool_handler_id(self, tool_id: str) -> str:
        return f"{self.tool_handler_prefix}.{tool_id}"

    def _tool_timeout_ms(self, tool_id: str) -> int:
        if self.tool_registry is None:
            return 30_000
        definition = self.tool_registry.describe(tool_id)
        return max(100, min(900_000, int(definition.timeout_seconds * 1000)))

    def _subagent_handler_id(self) -> str:
        return f"subagent.{self.agent_id}"

    def _subagent_timeout_ms(self) -> int:
        """Use the registered local Agent timeout for typed sub-agent nodes."""

        if self.subagent_registry is not None:
            try:
                definition = self.subagent_registry.describe(self.agent_id)
            except RuntimeSubagentRegistryError:
                pass
            else:
                return max(100, min(900_000, int(definition.max_timeout_ms)))
        return 120_000

    def _register_typed_subagent_handler(
        self,
        registry: RuntimeHandlerRegistry,
        event_hook: Callable[[str, AgentRun, str], Any] | None = None,
    ) -> None:
        subagent_registry = self.subagent_registry
        if subagent_registry is None:
            subagent_registry = RuntimeSubagentRegistry()
            subagent_registry.register(
                RuntimeSubagentDefinition(
                    subagent_id=self.agent_id,
                    target_agent_id=self.agent_id,
                    max_timeout_ms=120_000,
                )
            )
        else:
            try:
                subagent_registry.describe(self.agent_id)
            except RuntimeSubagentRegistryError:
                # Isolated service tests may not provide the application-wide
                # registry. Do not mutate an injected production registry.
                subagent_registry = RuntimeSubagentRegistry()
                subagent_registry.register(
                    RuntimeSubagentDefinition(
                        subagent_id=self.agent_id,
                        target_agent_id=self.agent_id,
                        max_timeout_ms=120_000,
                    )
                )
        register_subagent_handlers(
            registry,
            self.internal_agents,
            subagent_registry,
            self.child_run_service,
            event_hook,
        )

    @staticmethod
    def _sync_request(run: AgentRun, request: AgentRequest) -> None:
        control_data = dict(run.control_data)
        control_data["request"] = request.model_dump(mode="json")
        run.control_data = control_data

    @staticmethod
    def _bounded_value(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value if not isinstance(value, str) else value[:8_000]
        if isinstance(value, Mapping):
            return {
                str(key)[:120]: GeneralQuestionRuntimeService._bounded_value(item)
                for key, item in list(value.items())[:32]
            }
        if isinstance(value, (list, tuple)):
            return [
                GeneralQuestionRuntimeService._bounded_value(item)
                for item in value[:32]
            ]
        return repr(value)[:8_000]

    @staticmethod
    def _restore_result(run: AgentRun) -> AgentResult | None:
        for observation in reversed(run.observations):
            payload = observation.facts.get("result_payload")
            if isinstance(payload, dict):
                try:
                    return AgentResult.model_validate(payload)
                except ValueError:
                    continue
        return None

    def _apply_retrieval_metadata(
        self, result: AgentResult, run: AgentRun
    ) -> AgentResult:
        _, retrieve_node_id, _, _, _ = self._current_node_ids(run)
        if retrieve_node_id is None:
            return result
        retrieval_observation = run.nodes[retrieve_node_id].observation
        if retrieval_observation is None:
            return result
        retrieval_facts = retrieval_observation.facts
        metrics = result.metrics.model_copy(
            update={"retrieval_calls": max(1, result.metrics.retrieval_calls)}
        )
        return result.model_copy(
            update={
                "metrics": metrics,
                "rag_status": str(
                    retrieval_facts.get("evidence_status", "partial")
                ),
                "evidence_status": str(
                    retrieval_facts.get("evidence_status", "partial")
                ),
                "retrieval_trace_id": str(
                    retrieval_facts.get("retrieval_trace_id", "")
                ),
                "index_version": str(retrieval_facts.get("index_version", "")),
            }
        )

    def _apply_retrieval_presentation(
        self, result: AgentResult, request: AgentRequest
    ) -> AgentResult:
        """Persist typed-Runtime hits so the task UI can render evidence cards.

        The frozen solver keeps its existing provider contract. Typed business
        runtimes, however, need to carry the bounded local hits across approval
        and checkpoint recovery because the presentation layer cannot inspect a
        live retrieval service after the run has completed.
        """

        if not self.use_typed_subagent:
            return result
        raw_hits = request.options.get("runtime_retrieved_knowledge_hits", [])
        if not isinstance(raw_hits, list):
            return result
        hits: list[dict[str, Any]] = []
        for raw_hit in raw_hits[:20]:
            if not isinstance(raw_hit, Mapping):
                continue
            try:
                hit = KnowledgeHit.model_validate(raw_hit)
            except ValueError:
                continue
            hits.append(hit.model_dump(mode="json"))
        if not hits:
            return result
        structured = dict(result.structured_result)
        knowledge = structured.get("knowledge", {})
        knowledge = dict(knowledge) if isinstance(knowledge, Mapping) else {}
        knowledge["hits"] = hits
        for option_key, knowledge_key in (
            ("runtime_retrieval_trace_id", "retrieval_trace_id"),
            ("runtime_retrieval_index_version", "index_version"),
        ):
            value = request.options.get(option_key)
            if value:
                knowledge[knowledge_key] = str(value)
        structured["knowledge"] = knowledge
        structured["knowledge_hit_count"] = len(hits)
        return result.model_copy(update={"structured_result": structured})

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
        requested_tool_id = self._requested_tool_id(request_for_attempt)
        retrieved_context_holder: dict[str, Any] = {}

        async def observe_handler(
            current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            nonlocal request_for_attempt
            user_input = current.control_data.get("user_input")
            user_input_applied = isinstance(user_input, dict)
            if isinstance(user_input, dict):
                options = dict(request_for_attempt.options)
                options["runtime_user_input"] = dict(user_input)
                request_for_attempt = request_for_attempt.model_copy(
                    update={"options": options}
                )
                self._sync_request(current, request_for_attempt)
            return RuntimeObservation(
                node_id=node.node_id,
                facts={
                    "phase": "observe",
                    "question": self._question(request_for_attempt)[:8_000],
                    "context_present": context is not None,
                    "user_input_applied": user_input_applied,
                    "tool_requested": self._requested_tool_id(request_for_attempt),
                    "response_depth": str(
                        request_for_attempt.options.get(
                            "response_depth", "standard"
                        )
                    ),
                },
            )

        if self._retrieval_requested(request_for_attempt):
            self._validate_retrieval_available()
            retrieval_service = self.rag_retrieval
            retrieval_context = self.retrieval_context
            assert retrieval_service is not None
            assert retrieval_context is not None

            async def execute_retrieval(
                current: AgentRun, node: RuntimeNode
            ) -> RuntimeObservation:
                nonlocal request_for_attempt
                runtime_options = request_for_attempt.options.get(
                    self.runtime_option_key, {}
                )
                if not isinstance(runtime_options, dict):
                    raise RuntimeNodeError("runtime_retrieval_options_invalid")
                top_k_value = runtime_options.get("retrieval_top_k")
                top_k = (
                    max(1, min(20, int(top_k_value)))
                    if top_k_value is not None
                    else None
                )
                try:
                    retrieval = await asyncio.to_thread(
                        retrieval_service.search,
                        query_text=self._question(request_for_attempt),
                        course_id=request_for_attempt.course_id,
                        intent=request_for_attempt.intent.value,
                        target_agent_id=self.agent_id,
                        top_k=top_k,
                        include_images=False,
                        session_context=str(
                            request_for_attempt.options.get(
                                "conversation_summary", ""
                            )
                        ),
                    )
                    packet = retrieval_context.build(
                        retrieval,
                        course_id=request_for_attempt.course_id,
                        intent=request_for_attempt.intent.value,
                        query_override=self._question(request_for_attempt),
                    )
                except Exception as exc:
                    raise RuntimeNodeError(
                        "runtime_retrieval_failed", str(exc)
                    ) from exc
                options = dict(request_for_attempt.options)
                options["retrieved_context"] = packet.to_retrieved_context()
                options["runtime_retrieval_evidence_status"] = packet.evidence_status
                options["runtime_retrieval_warnings"] = list(packet.warnings[:8])
                options["runtime_retrieval_trace_id"] = packet.retrieval_trace_id
                options["runtime_retrieval_evidence_ids"] = [
                    hit.evidence_id for hit in packet.evidence if hit.evidence_id
                ]
                options["runtime_retrieved_knowledge_hits"] = [
                    hit.model_dump(mode="json") for hit in packet.evidence
                ]
                options["runtime_retrieval_index_version"] = packet.index_version
                retrieved_context_holder["packet"] = packet
                request_for_attempt = request_for_attempt.model_copy(
                    update={"options": options}
                )
                self._sync_request(current, request_for_attempt)
                evidence_ids = [
                    hit.evidence_id for hit in packet.evidence if hit.evidence_id
                ]
                return RuntimeObservation(
                    node_id=node.node_id,
                    evidence_ids=evidence_ids,
                    facts={
                        "phase": "retrieve",
                        "evidence_status": packet.evidence_status,
                        "source_refs": list(packet.source_refs[:32]),
                        "retrieval_trace_id": packet.retrieval_trace_id,
                        "index_version": packet.index_version,
                        "context_chars": len(packet.to_retrieved_context()),
                    },
                    warnings=list(packet.warnings[:8]),
                    confidence=retrieval.confidence,
                )

            registry.register(
                RuntimeHandlerDescriptor(
                    handler_id=self.retrieve_handler_id,
                    kind="tool",
                    max_timeout_ms=60_000,
                ),
                execute_retrieval,
            )

        if requested_tool_id:
            self._validate_tool_available(requested_tool_id)
            assert self.tool_registry is not None
            tool_definition = self.tool_registry.describe(requested_tool_id)
            tool_handler = self.tool_registry.get(requested_tool_id)
            tool_requires_approval = (
                tool_definition.side_effect_level not in {"none", "read_only"}
                or tool_definition.requires_sandbox
            )

            async def execute_tool(
                current: AgentRun, node: RuntimeNode
            ) -> RuntimeObservation:
                nonlocal request_for_attempt
                runtime_options = request_for_attempt.options.get(
                    self.runtime_option_key, {}
                )
                if not isinstance(runtime_options, dict):
                    raise RuntimeNodeError("runtime_tool_options_invalid")
                raw_input = runtime_options.get("tool_input", {})
                if not isinstance(raw_input, Mapping):
                    raise RuntimeNodeError("runtime_tool_input_invalid")
                args = raw_input.get("args", [])
                kwargs = raw_input.get("kwargs", raw_input)
                if not isinstance(args, list) or not isinstance(kwargs, Mapping):
                    raise RuntimeNodeError("runtime_tool_input_call_shape_invalid")
                output = tool_handler(*args, **dict(kwargs))
                if inspect.isawaitable(output):
                    output = await output
                options = dict(request_for_attempt.options)
                options["runtime_tool_id"] = requested_tool_id
                options["runtime_tool_result"] = self._bounded_value(output)
                request_for_attempt = request_for_attempt.model_copy(
                    update={"options": options}
                )
                self._sync_request(current, request_for_attempt)
                return RuntimeObservation(
                    node_id=node.node_id,
                    facts={
                        "phase": "tool",
                        "tool_id": requested_tool_id,
                        "execution_key": current.nodes[node.node_id].execution_key,
                        "output": self._bounded_value(output),
                    },
                )

            registry.register(
                RuntimeHandlerDescriptor(
                    handler_id=self._tool_handler_id(requested_tool_id),
                    kind="tool",
                    requires_approval=tool_requires_approval,
                    side_effecting=tool_requires_approval,
                    replay_safe=(
                        tool_definition.deterministic and not tool_requires_approval
                    ),
                    max_timeout_ms=self._tool_timeout_ms(requested_tool_id),
                ),
                execute_tool,
            )

        async def execute_handler(
            current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            nonlocal request_for_attempt
            options = dict(request_for_attempt.options)
            options["runtime_node_id"] = node.node_id
            options["runtime_execution_key"] = current.nodes[
                node.node_id
            ].execution_key
            _, retrieve_node_id, tool_node_id, _, _ = self._current_node_ids(
                current
            )
            if retrieve_node_id is not None:
                retrieve_observation = current.nodes[retrieve_node_id].observation
                if retrieve_observation is not None:
                    options["runtime_retrieval_evidence_ids"] = list(
                        retrieve_observation.evidence_ids
                    )
                    options["runtime_retrieval_trace_id"] = (
                        retrieve_observation.facts.get("retrieval_trace_id", "")
                    )
            if tool_node_id is not None:
                tool_observation = current.nodes[tool_node_id].observation
                if tool_observation is not None:
                    options["runtime_tool_id"] = tool_observation.facts.get(
                        "tool_id", ""
                    )
                    options["runtime_tool_result"] = tool_observation.facts.get(
                        "output"
                    )
            request_for_attempt = request_for_attempt.model_copy(
                update={"options": options}
            )
            provider_context = self._provider_context(
                context, retrieved_context_holder.get("packet")
            )
            result = await self.internal_agents.run(
                self.agent_id, request_for_attempt, provider_context
            )
            if retrieve_node_id is not None:
                retrieval_observation = current.nodes[retrieve_node_id].observation
                if retrieval_observation is not None:
                    retrieval_facts = retrieval_observation.facts
                    metrics = result.metrics.model_copy(
                        update={
                            "retrieval_calls": max(
                                1, result.metrics.retrieval_calls
                            )
                        }
                    )
                    result = result.model_copy(
                        update={
                            "metrics": metrics,
                            "rag_status": str(
                                retrieval_facts.get("evidence_status", "partial")
                            ),
                            "evidence_status": str(
                                retrieval_facts.get("evidence_status", "partial")
                            ),
                            "retrieval_trace_id": str(
                                retrieval_facts.get("retrieval_trace_id", "")
                            ),
                            "index_version": str(
                                retrieval_facts.get("index_version", "")
                            ),
                        }
                    )
            result_holder["result"] = result
            return RuntimeObservation(
                node_id=node.node_id,
                artifact_ids=[item.artifact_id for item in result.artifacts],
                facts={
                    "phase": "act",
                    "result_status": result.status.value,
                    "provider": result.provider,
                    "execution_key": current.nodes[node.node_id].execution_key,
                    "answer_present": bool(result.answer.strip()),
                    "result_payload": result.model_dump(mode="json"),
                },
                warnings=list(result.warnings[:8]),
            )

        def verify_handler(
            current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            # A resumed Run may carry an old partial result in memory. Prefer
            # the latest durable observation so a successful recovery cannot
            # be shadowed by the previous attempt's cached result.
            result = self._restore_result(current)
            if result is not None:
                result = self._apply_retrieval_metadata(result, current)
                result_holder["result"] = result
            else:
                result = result_holder.get("result")
            if result is None:
                raise RuntimeNodeError(
                    f"{self.runtime_name}_result_missing",
                    "general answer verification requires an execution result",
                )
            if not self._is_valid_result(result):
                return RuntimeObservation(
                    node_id=node.node_id,
                    terminal_status=RuntimeNodeStatus.PARTIAL,
                    artifact_ids=[item.artifact_id for item in result.artifacts],
                    facts={
                        "phase": "verify",
                        "passed": False,
                        "replan_required": True,
                        "result_status": result.status.value,
                        "answer_present": bool(result.answer.strip()),
                    },
                    warnings=list(result.warnings[:8]),
                )
            return RuntimeObservation(
                node_id=node.node_id,
                facts={
                    "phase": "verify",
                    "passed": True,
                    "result_status": result.status.value,
                    "answer_present": True,
                },
            )

        registry.register(
            RuntimeHandlerDescriptor(
                handler_id=self.observe_handler_id,
                kind="tool",
                max_timeout_ms=10_000,
            ),
            observe_handler,
        )
        if self.use_typed_subagent:
            self._register_typed_subagent_handler(registry, event_hook)
        else:
            registry.register(
                RuntimeHandlerDescriptor(
                    handler_id=self.execute_handler_id,
                    kind="provider",
                    max_timeout_ms=120_000,
                ),
                execute_handler,
            )
        registry.register(
            RuntimeHandlerDescriptor(
                handler_id=self.verify_handler_id,
                kind="tool",
                max_timeout_ms=30_000,
            ),
            verify_handler,
        )

        def decide(current: AgentRun) -> RuntimeDecision:
            (
                observe_node_id,
                retrieve_node_id,
                tool_node_id,
                execute_node_id,
                verify_node_id,
            ) = (
                self._current_node_ids(current)
            )
            observe_state = current.nodes[observe_node_id]
            retrieve_state = (
                current.nodes[retrieve_node_id] if retrieve_node_id else None
            )
            tool_state = current.nodes[tool_node_id] if tool_node_id else None
            execute_state = current.nodes[execute_node_id]
            verify_state = current.nodes[verify_node_id]
            if observe_state.status == RuntimeNodeStatus.FAILED:
                if current.iteration >= current.budget.max_iterations - 1:
                    return RuntimeDecision(
                        action=DecisionAction.FAIL,
                        reason_codes=[f"{self.runtime_name}_observation_failed"],
                    )
                return RuntimeDecision(
                    action=DecisionAction.REPLAN,
                    reason_codes=[f"{self.runtime_name}_observation_failed"],
                )
            if observe_state.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[observe_node_id],
                    reason_codes=[f"{self.runtime_name}_observation_required"],
                )
            if (
                retrieve_state is not None
                and retrieve_state.status == RuntimeNodeStatus.FAILED
            ):
                if current.iteration >= current.budget.max_iterations - 1:
                    return RuntimeDecision(
                        action=DecisionAction.FAIL,
                        reason_codes=[f"{self.runtime_name}_retrieval_failed"],
                    )
                return RuntimeDecision(
                    action=DecisionAction.REPLAN,
                    reason_codes=[f"{self.runtime_name}_retrieval_failed"],
                )
            if retrieve_state is not None and retrieve_state.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                assert retrieve_node_id is not None
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[retrieve_node_id],
                    reason_codes=[f"{self.runtime_name}_retrieval_required"],
                )
            if tool_state is not None and tool_state.status == RuntimeNodeStatus.FAILED:
                if current.iteration >= current.budget.max_iterations - 1:
                    return RuntimeDecision(
                        action=DecisionAction.FAIL,
                        reason_codes=[f"{self.runtime_name}_tool_failed"],
                    )
                return RuntimeDecision(
                    action=DecisionAction.REPLAN,
                    reason_codes=[f"{self.runtime_name}_tool_failed"],
                )
            if tool_state is not None and tool_state.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                assert tool_node_id is not None
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[tool_node_id],
                    reason_codes=[f"{self.runtime_name}_tool_required"],
                )
            if execute_state.status in {
                RuntimeNodeStatus.FAILED,
                RuntimeNodeStatus.PARTIAL,
            }:
                if current.iteration >= current.budget.max_iterations - 1:
                    return RuntimeDecision(
                        action=DecisionAction.FAIL,
                        reason_codes=[f"{self.runtime_name}_execution_failed"],
                    )
                return RuntimeDecision(
                    action=DecisionAction.REPLAN,
                    reason_codes=[f"{self.runtime_name}_execution_failed"],
                )
            if execute_state.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[execute_node_id],
                    reason_codes=[f"{self.runtime_name}_execution_required"],
                )
            if verify_state.status == RuntimeNodeStatus.PARTIAL:
                approval_decision = self._verification_approval_decision(current)
                if approval_decision is not None:
                    return approval_decision
                if current.iteration >= current.budget.max_iterations - 1:
                    return RuntimeDecision(
                        action=DecisionAction.FAIL,
                        reason_codes=[
                            f"{self.runtime_name}_replan_budget_exhausted"
                        ],
                    )
                return RuntimeDecision(
                    action=DecisionAction.REPLAN,
                    reason_codes=[
                        f"{self.runtime_name}_verification_requires_replan"
                    ],
                )
            if verify_state.status not in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }:
                return RuntimeDecision(
                    action=DecisionAction.EXECUTE,
                    node_ids=[verify_node_id],
                    reason_codes=[f"{self.runtime_name}_verification_required"],
                )
            return RuntimeDecision(
                action=DecisionAction.FINISH,
                reason_codes=[f"{self.runtime_name}_runtime_verified"],
            )

        async def replan(
            current: AgentRun, _decision: RuntimeDecision
        ) -> AgentRunPlan:
            nonlocal request_for_attempt
            options = dict(request_for_attempt.options)
            runtime_options = dict(options.get(self.runtime_option_key, {}))
            runtime_options["runtime_replan_iteration"] = current.iteration
            options[self.runtime_option_key] = runtime_options
            request_for_attempt = request_for_attempt.model_copy(
                update={"options": options}
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
            result = self._restore_result(run)
            if result is not None:
                result = self._apply_retrieval_metadata(result, run)
                result_holder["result"] = result
        if result is None:
            failure_code = next(
                (
                    node_state.error_code
                    for node_state in run.nodes.values()
                    if node_state.status == RuntimeNodeStatus.FAILED
                    and node_state.error_code
                ),
                "",
            )
            raise RuntimeNodeError(
                failure_code or f"{self.runtime_name}_result_missing",
                (
                    f"{self.runtime_name} execution failed: {failure_code}"
                    if failure_code
                    else f"{self.runtime_name} runtime produced no result"
                ),
            )
        # The first execution result is held in memory through verification,
        # so the verify handler may not restore it from a durable observation.
        # Apply the same retrieval metadata in both paths before the result is
        # projected into the task presentation payload.
        result = self._apply_retrieval_metadata(result, run)
        result = self._apply_retrieval_presentation(result, request_for_attempt)
        if (
            run.status.value != "completed"
            and result.status != AgentResultStatus.FAILED
        ):
            raise RuntimeNodeError(
                f"{self.runtime_name}_runtime_failed",
                f"{self.runtime_name} runtime ended with {run.status.value}",
            )
        return result

    def _verification_approval_decision(
        self, run: AgentRun
    ) -> RuntimeDecision | None:
        """Allow business runtimes to turn a quality gate into approval.

        A quality approval is distinct from an adaptive plan replacement. The
        default Runtime keeps the existing bounded replan behavior; business
        adapters can opt into a direct human gate when the current result is
        usable but requires explicit review.
        """

        del run
        return None

    def _is_valid_result(self, result: AgentResult) -> bool:
        return (
            result.status != AgentResultStatus.FAILED
            and bool(result.answer.strip())
        )

    def _provider_context(
        self, context: Any, retrieved_context: Any = None
    ) -> Any:
        """Choose the context passed to the legacy business implementation."""

        del retrieved_context
        return context
