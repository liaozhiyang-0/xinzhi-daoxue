from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any

from app.contracts import AgentRequest, AgentResult, AgentResultStatus
from app.contracts.research_analysis import (
    ResearchAnalysisRequest,
    ResearchAnalysisResult,
)
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
    """Execute Research Analysis V2 through an auditable Runtime DAG.

    Preparation is intentionally limited to deterministic request validation
    and bounded authorization metadata. Dataset resolution and analysis
    execution remain behind ``InternalAgentExecutionService``.
    """

    agent_id = "RESEARCH_03_DATA_ANALYSIS_V1"
    runtime_option_key = "research_analysis_v2"
    prepare_node_id = "analysis.prepare"
    execute_node_id = "analysis.execute"
    verify_node_id = "analysis.verify"
    prepared_control_key = "research_analysis_prepared"
    prepare_handler_id = "research.analysis.prepare"
    prepared_schema_version = "research-analysis-prepared-v1"
    _execution_modes = frozenset({"local", "plan_only"})
    _execution_mode_aliases = {
        "execute": "local",
        "local": "local",
        "plan": "plan_only",
        "plan_only": "plan_only",
    }

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
        analysis_request = self._analysis_request_from_options(options)
        suffix = "" if iteration == 0 else f".replan.{iteration}"
        prepare_node_id = f"{self.prepare_node_id}{suffix}"
        execute_node_id = f"{self.execute_node_id}{suffix}"
        verify_node_id = f"{self.verify_node_id}{suffix}"
        return AgentRunPlan(
            plan_id=f"research-runtime:{(request.task_id or 'request')[-80:]}",
            version="research-v2",
            goal=analysis_request.research_question,
            nodes=[
                RuntimeNode(
                    node_id=prepare_node_id,
                    node_type="control",
                    handler_id=self.prepare_handler_id,
                    timeout_ms=30_000,
                ),
                RuntimeNode(
                    node_id=execute_node_id,
                    node_type="workflow",
                    handler_id="research.analysis.execute",
                    depends_on=[prepare_node_id],
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
                "analysis_request_prepared",
                "analysis_result_present",
                "analysis_result_passes_runtime_verification",
            ],
        )

    @staticmethod
    def _analysis_request_from_options(
        options: Mapping[str, Any],
    ) -> ResearchAnalysisRequest:
        """Validate only the ResearchAnalysisRequest business payload."""

        payload = options.get("request")
        if payload is None:
            payload = {
                key: value
                for key, value in options.items()
                if key
                not in {
                    "execute",
                    "execution_mode",
                    "mode",
                    "output_dir",
                    "model_direct",
                    "model_assist",
                    "_runtime_error",
                    "runtime_replan_iteration",
                }
            }
        if not isinstance(payload, Mapping):
            raise ValueError("research_analysis_request_payload_invalid")
        return ResearchAnalysisRequest.model_validate(dict(payload))

    @classmethod
    def _build_prepared_record(cls, request: AgentRequest) -> dict[str, Any]:
        """Create the bounded, serializable preparation checkpoint.

        The normalized request payload is retained for the existing internal
        agent boundary. The manifest field is only a reference summary: raw
        paths, arbitrary URLs, credentials, and file contents are excluded.
        """

        options = request.options.get(cls.runtime_option_key)
        if not isinstance(options, Mapping):
            raise ValueError("research_analysis_v2_options_missing")
        analysis_request = cls._analysis_request_from_options(options)
        requested_mode = options.get("execution_mode")
        if requested_mode is None:
            requested_mode = options.get("mode")
        requested_execute = options.get("execute", False)
        if not isinstance(requested_execute, bool):
            raise ValueError("research_analysis_execute_flag_invalid")
        if requested_mode is None or requested_mode == cls.runtime_option_key:
            execution_mode = "local" if requested_execute else "plan_only"
        elif isinstance(requested_mode, str):
            execution_mode = cls._execution_mode_aliases.get(
                requested_mode.strip().lower(), ""
            )
            if "execute" in options and requested_execute != (
                execution_mode == "local"
            ):
                raise ValueError("research_analysis_execution_mode_conflict")
        else:
            raise ValueError("research_analysis_execution_mode_invalid")
        if execution_mode not in cls._execution_modes:
            raise ValueError("research_analysis_execution_mode_invalid")

        execution_options: dict[str, Any] = {"execute": execution_mode == "local"}
        for key in ("model_direct", "model_assist"):
            if key not in options:
                continue
            value = options[key]
            if not isinstance(value, bool):
                raise ValueError("research_analysis_execution_option_invalid")
            execution_options[key] = value
        output_dir = options.get("output_dir")
        if output_dir is not None:
            if not isinstance(output_dir, str) or len(output_dir) > 512:
                raise ValueError("research_analysis_execution_option_invalid")
            if output_dir.strip():
                execution_options["output_dir"] = output_dir
        runtime_error = options.get("_runtime_error")
        if runtime_error is not None:
            if not isinstance(runtime_error, str) or len(runtime_error) > 512:
                raise ValueError("research_analysis_execution_option_invalid")
            if runtime_error.strip():
                execution_options["_runtime_error"] = runtime_error.strip()

        manifest = analysis_request.data_manifest
        authorization_manifest_ref: dict[str, Any] = {
            "present": manifest is not None,
            "dataset_id": manifest.dataset_id if manifest is not None else "",
            "version": manifest.version if manifest is not None else "",
            "format": manifest.format if manifest is not None else "unknown",
            "checksum_sha256": (
                manifest.checksum_sha256 if manifest is not None else ""
            ),
            "authorized": manifest.authorized if manifest is not None else False,
            "contains_sensitive_data": (
                manifest.contains_sensitive_data if manifest is not None else False
            ),
        }
        return {
            "schema_version": cls.prepared_schema_version,
            "payload": analysis_request.model_dump(mode="json"),
            "execution_mode": execution_mode,
            "execution_options": execution_options,
            "authorization_manifest_ref": authorization_manifest_ref,
        }

    @classmethod
    def _prepared_record(
        cls,
        run: AgentRun,
        request: AgentRequest | None = None,
    ) -> dict[str, Any] | None:
        """Read current or pre-prepare checkpoint shapes safely.

        ``research_analysis`` and a direct ``research_analysis_prepared``
        payload were used by earlier development checkpoints. They are read
        conservatively and normalized to the current record shape.
        """

        raw = run.control_data.get(cls.prepared_control_key)
        if not isinstance(raw, Mapping):
            raw = run.control_data.get("research_analysis")
        if not isinstance(raw, Mapping):
            return None
        payload = raw.get("payload")
        if not isinstance(payload, Mapping):
            if "research_question" not in raw:
                return None
            payload = raw
        try:
            normalized = ResearchAnalysisRequest.model_validate(dict(payload))
        except ValueError:
            return None

        mode = raw.get("execution_mode")
        if not isinstance(mode, str):
            mode = raw.get("mode")
        if mode not in cls._execution_modes and request is not None:
            options = request.options.get(cls.runtime_option_key)
            if isinstance(options, Mapping):
                requested_mode = options.get("execution_mode", options.get("mode"))
                if isinstance(requested_mode, str):
                    mode = cls._execution_mode_aliases.get(
                        requested_mode.strip().lower(), ""
                    )
                else:
                    mode = "local" if options.get("execute") is True else "plan_only"
        if mode not in cls._execution_modes:
            return None
        reference = raw.get("authorization_manifest_ref")
        if not isinstance(reference, Mapping):
            reference = raw.get("manifest_ref")
        expected_reference = cls._manifest_reference(normalized)
        if reference is not None and dict(reference) != expected_reference:
            return None
        if reference is None:
            return None
        raw_execution_options = raw.get("execution_options")
        if isinstance(raw_execution_options, Mapping):
            allowed_options = {
                "execute",
                "model_direct",
                "model_assist",
                "output_dir",
                "_runtime_error",
            }
            if set(raw_execution_options) - allowed_options:
                return None
            execution_options = dict(raw_execution_options)
            if execution_options.get("execute") != (mode == "local"):
                return None
        else:
            execution_options = {"execute": mode == "local"}
        return {
            "schema_version": str(
                raw.get("schema_version", cls.prepared_schema_version)
            ),
            "payload": normalized.model_dump(mode="json"),
            "execution_mode": mode,
            "execution_options": execution_options,
            "authorization_manifest_ref": dict(reference),
        }

    @staticmethod
    def _manifest_reference(
        analysis_request: ResearchAnalysisRequest,
    ) -> dict[str, Any]:
        """Return only stable authorization identity, never a source path."""

        manifest = analysis_request.data_manifest
        return {
            "present": manifest is not None,
            "dataset_id": manifest.dataset_id if manifest is not None else "",
            "version": manifest.version if manifest is not None else "",
            "format": manifest.format if manifest is not None else "unknown",
            "checksum_sha256": (
                manifest.checksum_sha256 if manifest is not None else ""
            ),
            "authorized": manifest.authorized if manifest is not None else False,
            "contains_sensitive_data": (
                manifest.contains_sensitive_data
                if manifest is not None
                else False
            ),
        }

    @classmethod
    def _request_from_prepared(
        cls,
        request: AgentRequest,
        prepared: Mapping[str, Any],
    ) -> AgentRequest:
        payload = prepared.get("payload")
        mode = prepared.get("execution_mode")
        if not isinstance(payload, Mapping) or mode not in cls._execution_modes:
            raise RuntimeNodeError(
                "research_analysis_prepare_missing",
                "analysis execution requires a valid prepared checkpoint",
            )
        # Validate the durable payload again before crossing into the internal
        # execution service. Attachments remain on the outer request envelope.
        normalized = ResearchAnalysisRequest.model_validate(dict(payload))
        options = dict(request.options)
        normalized_options: dict[str, Any] = {
            "execute": mode == "local",
            "execution_mode": mode,
            "request": normalized.model_dump(mode="json"),
        }
        execution_options = prepared.get("execution_options")
        if isinstance(execution_options, Mapping):
            for key in (
                "model_direct",
                "model_assist",
                "output_dir",
                "_runtime_error",
            ):
                value = execution_options.get(key)
                if value is not None:
                    normalized_options[key] = value
        options[cls.runtime_option_key] = normalized_options
        return request.model_copy(update={"options": options})

    @staticmethod
    def _current_node_ids(
        run: AgentRun,
    ) -> tuple[str | None, str, str]:
        prepare_node = next(
            (
                node
                for node in run.plan.nodes
                if node.handler_id == "research.analysis.prepare"
            ),
            None,
        )
        execute_node = next(
            node
            for node in run.plan.nodes
            if node.handler_id == "research.analysis.execute"
        )
        verify_node = next(
            node
            for node in run.plan.nodes
            if node.handler_id == "research.analysis.verify"
        )
        return (
            prepare_node.node_id if prepare_node is not None else None,
            execute_node.node_id,
            verify_node.node_id,
        )

    @staticmethod
    def _prepare_node_id(run: AgentRun) -> str | None:
        """Find prepare in current plans; return None for old checkpoints."""

        return next(
            (
                node.node_id
                for node in run.plan.nodes
                if node.handler_id == "research.analysis.prepare"
            ),
            None,
        )

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

    @staticmethod
    def _parse_analysis_result(result: AgentResult) -> ResearchAnalysisResult:
        """Extract the typed analysis payload from an AgentResult envelope.

        The internal-agent boundary currently emits the typed payload in
        ``business_data`` and mirrors it under
        ``structured_result["business_data"]``.  A direct structured payload
        is also accepted for compatible callers, but the analysis marker is
        mandatory and the Pydantic contract remains authoritative.  In
        particular, a generic ``AgentResult`` status of ``completed`` is not
        evidence that the analysis itself executed.
        """

        structured = result.structured_result
        if structured.get("analysis_v2") is not True:
            raise RuntimeNodeError(
                "analysis_result_contract_invalid",
                "research analysis result is missing analysis_v2 marker",
            )

        candidates: list[dict[str, Any]] = []

        def add_candidate(value: Any) -> None:
            if isinstance(value, dict) and value not in candidates:
                candidates.append(value)

        add_candidate(result.business_data)
        add_candidate(structured.get("business_data"))
        add_candidate(structured.get("research_analysis_v2"))

        direct_structured = dict(structured)
        direct_structured.pop("analysis_v2", None)
        add_candidate(direct_structured)

        for payload in candidates:
            try:
                return ResearchAnalysisResult.model_validate(payload)
            except ValueError:
                continue

        raise RuntimeNodeError(
            "analysis_result_contract_invalid",
            "research analysis result is not a valid ResearchAnalysisResult",
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
        result_holder: dict[str, AgentResult] = {}
        request_for_plan = request
        request_for_attempt = request
        restored_result = self._restore_result(run)
        prepared_record = self._prepared_record(run, request)
        _prepare_node_id, execute_node_id, _verify_node_id = (
            self._current_node_ids(run)
        )
        prepare_node_id = self._prepare_node_id(run)
        if prepared_record is None and prepare_node_id is None:
            execute_succeeded = run.nodes[execute_node_id].status in {
                RuntimeNodeStatus.SUCCEEDED,
                RuntimeNodeStatus.SKIPPED,
            }
            if restored_result is None or not execute_succeeded:
                try:
                    prepared_record = self._build_prepared_record(request)
                except ValueError as exc:
                    if restored_result is None:
                        raise RuntimeNodeError(
                            "analysis_prepare_contract_invalid",
                            "research analysis request failed prepare validation",
                        ) from exc
                if prepared_record is not None:
                    control_data = dict(run.control_data)
                    control_data[self.prepared_control_key] = prepared_record
                    run.control_data = control_data
                    if checkpoint_hook is not None:
                        checkpoint_result = checkpoint_hook(run)
                        if inspect.isawaitable(checkpoint_result):
                            await checkpoint_result
        if prepared_record is not None:
            request_for_attempt = self._request_from_prepared(
                request, prepared_record
            )
        if restored_result is not None:
            result_holder["result"] = restored_result
        registry = RuntimeHandlerRegistry()

        async def prepare_handler(
            current: AgentRun, node: RuntimeNode
        ) -> RuntimeObservation:
            try:
                prepared_record = self._build_prepared_record(request)
            except ValueError as exc:
                raise RuntimeNodeError(
                    "analysis_prepare_contract_invalid",
                    "research analysis request failed prepare validation",
                ) from exc
            control_data = dict(current.control_data)
            control_data[self.prepared_control_key] = prepared_record
            current.control_data = control_data
            payload = prepared_record["payload"]
            prepared = ResearchAnalysisRequest.model_validate(payload)
            manifest = prepared.data_manifest
            return RuntimeObservation(
                node_id=node.node_id,
                facts={
                    "phase": "prepare",
                    "analysis_goal": prepared.analysis_goal,
                    "design": prepared.design,
                    "data_manifest_id": (
                        manifest.dataset_id if manifest is not None else ""
                    ),
                    "data_manifest_authorized": (
                        manifest.authorized if manifest is not None else False
                    ),
                    "evidence_count": len(prepared.evidence),
                    "execution_mode": prepared_record["execution_mode"],
                    "authorization_manifest_ref": prepared_record.get(
                        "authorization_manifest_ref"
                    ),
                },
            )

        async def execute_handler(
            _run: AgentRun, _node: RuntimeNode
        ) -> RuntimeObservation:
            nonlocal request_for_attempt
            prepared_record = self._prepared_record(_run, request)
            if prepared_record is None:
                raise RuntimeNodeError(
                    "research_analysis_prepare_missing",
                    "analysis execution requires a prepared checkpoint",
                )
            # Do not use the live request payload here. Only the durable
            # preparation record may cross into InternalAgentExecutionService.
            request_for_attempt = self._request_from_prepared(
                request, prepared_record
            )
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
            if result.status != AgentResultStatus.COMPLETED:
                raise RuntimeNodeError(
                    "analysis_result_status_invalid",
                    "research analysis AgentResult must be completed",
                )
            analysis_result = self._parse_analysis_result(result)
            if analysis_result.status == "needs_review":
                return RuntimeObservation(
                    node_id=_node.node_id,
                    terminal_status=RuntimeNodeStatus.PARTIAL,
                    artifact_ids=[item.artifact_id for item in result.artifacts],
                    facts={
                        "passed": False,
                        "requires_review": True,
                        "replan_required": False,
                        "analysis_status": analysis_result.status,
                        "result_status": result.status.value,
                    },
                    warnings=list(result.warnings[:8]),
                )
            if analysis_result.status != "executed":
                return RuntimeObservation(
                    node_id=_node.node_id,
                    terminal_status=RuntimeNodeStatus.PARTIAL,
                    artifact_ids=[item.artifact_id for item in result.artifacts],
                    facts={
                        "passed": False,
                        "requires_review": False,
                        "replan_required": False,
                        "analysis_status": analysis_result.status,
                        "result_status": result.status.value,
                    },
                    warnings=list(result.warnings[:8]),
                )
            return RuntimeObservation(
                node_id=_node.node_id,
                artifact_ids=[item.artifact_id for item in result.artifacts],
                facts={
                    "passed": True,
                    "result_status": result.status.value,
                    "analysis_status": analysis_result.status,
                    "analysis_result_valid": True,
                    "business_data_present": bool(result.business_data),
                },
            )

        registry.register(
            RuntimeHandlerDescriptor(
                handler_id=self.prepare_handler_id,
                kind="tool",
                permission_scope="research.analysis.prepare",
                side_effect_level="none",
                requires_sandbox=False,
                risk_level="low",
                side_effecting=False,
                replay_safe=True,
                max_timeout_ms=30_000,
            ),
            prepare_handler,
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
            prepare_node_id, execute_node_id, verify_node_id = (
                self._current_node_ids(current)
            )
            if prepare_node_id is not None:
                prepare_state = current.nodes[prepare_node_id]
                if prepare_state.status in {
                    RuntimeNodeStatus.FAILED,
                    RuntimeNodeStatus.BLOCKED,
                }:
                    return RuntimeDecision(
                        action=DecisionAction.FAIL,
                        reason_codes=["analysis_prepare_contract_failed"],
                    )
                if prepare_state.status not in {
                    RuntimeNodeStatus.SUCCEEDED,
                    RuntimeNodeStatus.SKIPPED,
                }:
                    return RuntimeDecision(
                        action=DecisionAction.EXECUTE,
                        node_ids=[prepare_node_id],
                        reason_codes=["analysis_prepare_required"],
                    )
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
            if verify_state.status in {
                RuntimeNodeStatus.FAILED,
                RuntimeNodeStatus.BLOCKED,
            }:
                return RuntimeDecision(
                    action=DecisionAction.FAIL,
                    reason_codes=["analysis_verification_contract_failed"],
                )
            if verify_state.status == RuntimeNodeStatus.PARTIAL:
                verification = verify_state.observation
                if verification is not None:
                    facts = verification.facts
                    if facts.get("requires_review") is True:
                        return RuntimeDecision(
                            action=DecisionAction.REQUEST_APPROVAL,
                            approval_scope="research_analysis_result_review",
                            reason_codes=["analysis_result_needs_review"],
                        )
                    if facts.get("replan_required") is False:
                        return RuntimeDecision(
                            action=DecisionAction.FAIL,
                            reason_codes=[
                                "analysis_result_not_executed",
                                str(facts.get("analysis_status", "unknown")),
                            ],
                        )
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
            nonlocal request_for_plan
            options = dict(request_for_plan.options)
            analysis_options = dict(
                options.get("research_analysis_v2", {})
            )
            analysis_options["runtime_replan_iteration"] = current.iteration
            options["research_analysis_v2"] = analysis_options
            request_for_plan = request_for_plan.model_copy(
                update={"options": options}
            )
            return self.build_plan(
                request_for_plan,
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
