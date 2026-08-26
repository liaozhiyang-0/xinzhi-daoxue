"""Boundary around the durable Agent Runtime.

This module deliberately contains no routing, retrieval, presentation, or
Task status policy. It owns only Runtime lifecycle decisions so business
Runtime implementations remain independent from task transport concerns.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentResultStatus,
    IntentExecutionPlan,
    RouteDecision,
)
from app.core.errors import NotConfiguredError
from app.observability.architecture_telemetry import architecture_telemetry
from app.providers.base import AgentProvider
from app.repositories import AgentRunRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    PlanProposalProvider,
    RuntimeCompatibilitySnapshot,
    RuntimeDecision,
    RuntimeLaunchSnapshot,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
    RuntimeStateMachine,
)
from app.services.production_execution_manifest import (
    ExecutionSurfaceError,
    LegacyExecutionForbidden,
    ProductionExecutionManifest,
)
from app.services.research_analysis_runtime import ResearchAnalysisRuntimeService
from app.services.runtime_business_registry import (
    RuntimeBusinessRegistry,
    RuntimeBusinessService,
)
from app.services.runtime_launch_policy import (
    RuntimeLaunchDecision,
    RuntimeLaunchMode,
)
from app.services.runtime_request_preparation import (
    RuntimeRequestPreparation,
    RuntimeRequestPreparationService,
)
from app.services.runtime_run_lifecycle import RuntimeRunLifecycleService


class RuntimeResumeInvariantError(RuntimeError):
    """Raised when durable compatibility state no longer matches a resume."""


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RuntimeTaskHandoff:
    """Decide whether a Runtime result owns the remainder of the Task."""

    result: AgentResult | None
    bypass_legacy_execution: bool
    legacy_fallback: bool = False
    runtime_status: str = ""
    fallback_reason: str = ""


class RuntimeExecutionBoundary:
    """Single entry point for Runtime lifecycle and business execution."""

    RESUMABLE_STATUSES = frozenset(
        {
            # A process restart or an approved replan can leave the durable
            # Run in RUNNING while its Task is queued for the next worker.
            RuntimeRunStatus.RUNNING.value,
            RuntimeRunStatus.PAUSED.value,
            RuntimeRunStatus.WAITING_INPUT.value,
            RuntimeRunStatus.WAITING_APPROVAL.value,
        }
    )

    def __init__(
        self,
        lifecycle: RuntimeRunLifecycleService,
        research_analysis: ResearchAnalysisRuntimeService | None,
        business_services: Iterable[RuntimeBusinessService] | None = None,
        request_preparation: RuntimeRequestPreparationService | None = None,
        legacy_provider: AgentProvider | None = None,
        manifest: ProductionExecutionManifest | None = None,
    ) -> None:
        self.lifecycle = lifecycle
        self.research_analysis = research_analysis
        self.request_preparation = request_preparation
        self.legacy_provider = legacy_provider
        self.manifest = manifest
        services = list(business_services or [])
        if research_analysis is not None and research_analysis not in services:
            services.insert(0, research_analysis)
        self.business_registry = RuntimeBusinessRegistry(services)

    def bind_manifest(self, manifest: ProductionExecutionManifest) -> None:
        """Bind the startup source of truth before any task can execute."""

        manifest.validate_bootstrap()
        self.manifest = manifest

    def _validate_execution_surface(
        self,
        *,
        request: AgentRequest,
        plan: AgentRunPlan,
        caller: str,
    ) -> None:
        if (
            self.manifest is None
            or self.manifest.development_compatibility_enabled
        ):
            return
        self.manifest.validate_runtime_plan(plan, caller=caller)
        raw_plan = request.options.get("_canonical_plan")
        if isinstance(raw_plan, dict):
            from app.contracts.planner import CanonicalPlan

            try:
                canonical = CanonicalPlan.model_validate(raw_plan)
            except ValueError as exc:
                raise ExecutionSurfaceError(
                    "CANONICAL_PLAN_INVALID",
                    "request contains an invalid CanonicalPlan",
                ) from exc
            self.manifest.validate_canonical_plan(canonical, caller=caller)

    @classmethod
    def is_resumable(cls, status: str) -> bool:
        return status in cls.RESUMABLE_STATUSES

    @staticmethod
    async def restore_request_payload(
        db: AsyncSession,
        *,
        runtime_id: str | None,
        fallback: dict[str, Any],
    ) -> tuple[AgentRun | None, dict[str, Any]]:
        """Restore the immutable request snapshot used by a Runtime run."""

        if not runtime_id:
            return None, fallback
        snapshot = await AgentRunRepository(db).restore(runtime_id)
        if snapshot is None or not snapshot.request_snapshot:
            return snapshot, fallback
        return snapshot, dict(snapshot.request_snapshot)

    def build_plan(
        self, agent_id: str, request: AgentRequest
    ) -> AgentRunPlan | None:
        return self.business_registry.build_plan(agent_id, request)

    def runtime_option_key(self, agent_id: str) -> str | None:
        return self.business_registry.runtime_option_key(agent_id)

    def runtime_option_key_for_request(
        self, agent_id: str, request: AgentRequest
    ) -> str | None:
        """Return the option key of the Runtime service selected by a request.

        A direct business Runtime is still the only key advertised for default
        launch configuration. An explicitly opted-in wildcard Goal Runtime,
        however, must drive the request launch decision even when the routed
        Agent also has a direct business adapter. Otherwise the Task boundary
        would silently fall back to Legacy before the generic plan is reached.
        """

        service = self.business_registry.resolve(agent_id, request)
        option_key = getattr(service, "runtime_option_key", None)
        if isinstance(option_key, str) and option_key:
            return option_key
        # ``supports`` intentionally requires the execution option to be
        # enabled. During launch resolution that option is not present yet,
        # so a direct business adapter would otherwise look unavailable and
        # be sent to Legacy before the candidate can inject its option.
        return self.business_registry.runtime_option_key(agent_id)

    def runtime_plan_version(self, agent_id: str) -> str | None:
        return self.business_registry.runtime_plan_version(agent_id)

    @staticmethod
    def handoff_result(
        runtime_result: AgentResult | None,
        *,
        decision: RuntimeLaunchDecision,
        run: AgentRun | None = None,
    ) -> RuntimeTaskHandoff:
        """Make Runtime/legacy ownership explicit after Runtime execution."""

        if runtime_result is not None:
            runtime_status = (
                run.status.value
                if run is not None
                else runtime_result.status.value
            )
            runtime_completed = (
                (run is None or run.status == RuntimeRunStatus.COMPLETED)
                and runtime_result.status == AgentResultStatus.COMPLETED
            )
            if not runtime_completed:
                reason = f"runtime_execution_{runtime_status}"
                failed_result = runtime_result.model_copy(
                    update={
                        "status": AgentResultStatus.FAILED,
                        "fallback_used": True,
                        "fallback_reason": reason,
                    }
                )
                if decision.requires_runtime:
                    raise NotConfiguredError(
                        "default Runtime execution did not complete "
                        f"(status={runtime_status})"
                    )
                return RuntimeTaskHandoff(
                    result=failed_result,
                    bypass_legacy_execution=False,
                    legacy_fallback=decision.mode == RuntimeLaunchMode.CANARY,
                    runtime_status=runtime_status,
                    fallback_reason=reason,
                )
            return RuntimeTaskHandoff(
                result=runtime_result,
                bypass_legacy_execution=True,
                runtime_status=RuntimeRunStatus.COMPLETED.value,
            )
        if decision.requires_runtime:
            raise NotConfiguredError(
                "default Runtime launch did not resolve a business service"
            )
        return RuntimeTaskHandoff(
            result=None,
            bypass_legacy_execution=False,
            legacy_fallback=decision.mode == RuntimeLaunchMode.CANARY,
            runtime_status=(
                "missing" if decision.mode == RuntimeLaunchMode.CANARY else ""
            ),
            fallback_reason=(
                "runtime_result_missing"
                if decision.mode == RuntimeLaunchMode.CANARY
                else ""
            ),
        )

    @staticmethod
    def validate_resume_invariants(
        run: AgentRun,
        *,
        task_agent_id: str,
        request: AgentRequest,
        execution_plan: Any,
    ) -> None:
        """Fail closed if a checkpointed compatibility envelope drifted."""

        snapshot = run.compatibility_snapshot
        if snapshot is None:
            # Runs created before compatibility metadata was introduced are
            # upgraded by the lifecycle path without rejecting valid work.
            return
        expected_agent_id = snapshot.agent_id
        if task_agent_id != expected_agent_id:
            raise RuntimeResumeInvariantError(
                "runtime resume agent differs from compatibility snapshot"
            )
        launch = run.launch_decision
        if launch is not None and launch.agent_id != expected_agent_id:
            raise RuntimeResumeInvariantError(
                "runtime launch decision differs from compatibility snapshot"
            )
        if (
            execution_plan is not None
            and snapshot.execution_plan_agent_id
            and execution_plan.agent_id != snapshot.execution_plan_agent_id
        ):
            raise RuntimeResumeInvariantError(
                "runtime execution plan differs from compatibility snapshot"
            )
        raw_routing = request.options.get("_routing")
        if not isinstance(raw_routing, dict):
            raise RuntimeResumeInvariantError(
                "runtime resume is missing checkpointed routing envelope"
            )
        route_agent_id = raw_routing.get("agent_id")
        if isinstance(route_agent_id, str) and route_agent_id != expected_agent_id:
            raise RuntimeResumeInvariantError(
                "runtime routing envelope differs from compatibility snapshot"
            )
        route_revision = raw_routing.get("route_revision")
        if (
            isinstance(route_revision, int)
            and route_revision != snapshot.route_revision
        ):
            raise RuntimeResumeInvariantError(
                "runtime route revision differs from compatibility snapshot"
            )
        RuntimeExecutionBoundary._validate_capability_checks(
            "route",
            snapshot.route_capability_checks,
            raw_routing.get("availability"),
        )
        raw_execution_plan = request.options.get("_execution_plan")
        RuntimeExecutionBoundary._validate_capability_checks(
            "execution plan",
            snapshot.execution_plan_capability_checks,
            raw_execution_plan.get("availability_checks")
            if isinstance(raw_execution_plan, dict)
            else None,
        )

    @staticmethod
    def _validate_capability_checks(
        label: str,
        expected: dict[str, bool],
        actual: Any,
    ) -> None:
        """Reject resumed envelopes whose capability contract was altered."""

        if not expected:
            return
        if not isinstance(actual, dict):
            raise RuntimeResumeInvariantError(
                f"runtime resume is missing {label} capability checks"
            )
        normalized = {
            key: value
            for key, value in actual.items()
            if isinstance(key, str) and isinstance(value, bool)
        }
        if normalized != expected:
            raise RuntimeResumeInvariantError(
                f"runtime {label} capabilities differ from compatibility snapshot"
            )

    async def prepare_request(
        self,
        db: AsyncSession,
        *,
        request: AgentRequest,
        decision: RouteDecision,
        agent_id: str,
        session_id: str,
        user_id: str,
        current_message_id: str | None,
        course_id: str,
        fallback_task_family: str,
        runtime_resume: bool,
    ) -> RuntimeRequestPreparation:
        """Prepare the resumable request envelope before Runtime execution."""

        if self.request_preparation is None:
            raise RuntimeError("Runtime request preparation is not configured")
        return await self.request_preparation.prepare(
            db,
            request=request,
            decision=decision,
            agent_id=agent_id,
            session_id=session_id,
            user_id=user_id,
            current_message_id=current_message_id,
            course_id=course_id,
            fallback_task_family=fallback_task_family,
            runtime_resume=runtime_resume,
        )

    def prepare_request_for_launch(
        self,
        agent_id: str,
        request: AgentRequest,
        mode: RuntimeLaunchMode,
        *,
        runtime_resume: bool = False,
    ) -> AgentRequest:
        if runtime_resume:
            # A resumed Run already persisted the request after all launch
            # compatibility preparation.  Re-applying the default-mode
            # option injection would change the checkpoint identity.
            return request
        if mode in {RuntimeLaunchMode.DEFAULT, RuntimeLaunchMode.CANARY}:
            # A registered Runtime candidate is allowed to launch without an
            # implementation-specific option in the public task payload. The
            # launch policy has already performed the release decision; now
            # materialize the service's bounded execution option so its
            # ``supports`` contract can resolve the same Runtime plan.
            return self.business_registry.prepare_default_request(agent_id, request)
        return request

    async def start_or_restore(
        self,
        db: AsyncSession,
        *,
        task_id: str,
        agent_id: str,
        provider: str,
        goal: str,
        intent_plan: IntentExecutionPlan | None,
        runtime_plan: AgentRunPlan | None,
        request: AgentRequest,
        launch_decision: RuntimeLaunchSnapshot | None = None,
        compatibility_snapshot: RuntimeCompatibilitySnapshot | None = None,
    ) -> AgentRun | None:
        if (
            self.manifest is not None
            and runtime_plan is not None
            and not self.manifest.development_compatibility_enabled
        ):
            self.manifest.validate_runtime_plan(
                runtime_plan,
                caller="RuntimeExecutionBoundary.start_or_restore",
            )
        return await self.lifecycle.start(
            db,
            task_id=task_id,
            agent_id=agent_id,
            provider=provider,
            goal=goal,
            intent_plan=intent_plan,
            runtime_plan=runtime_plan,
            request_snapshot=request.model_dump(mode="json"),
            launch_decision=launch_decision,
            compatibility_snapshot=compatibility_snapshot,
        )

    async def execute(
        self,
        agent_id: str,
        request: AgentRequest,
        run: AgentRun,
        *,
        context: Any = None,
        checkpoint_hook: Callable[[AgentRun], Any] | None = None,
        event_hook: Callable[[str, AgentRun, str], Any] | None = None,
        control_provider: Callable[[AgentRun], Any] | None = None,
        decision_event_hook: Callable[[AgentRun, RuntimeDecision], Any]
        | None = None,
        plan_proposal_provider: PlanProposalProvider | None = None,
    ) -> AgentResult | None:
        """Execute a registered business Runtime, if one supports the request."""

        self._validate_execution_surface(
            request=request,
            plan=run.plan,
            caller="RuntimeExecutionBoundary.execute",
        )

        service = self.business_registry.resolve(agent_id, request)
        if service is None:
            if (
                self.legacy_provider is not None
                and run.plan.plan_id.startswith("legacy-runtime:")
            ):
                if (
                    self.manifest is not None
                    and not self.manifest.development_compatibility_enabled
                ):
                    architecture_telemetry.increment(
                        "legacy_runtime_invocation_count"
                    )
                    options = request.options
                    logger.error(
                        "LEGACY_EXECUTION_ATTEMPT component=%s caller=%s "
                        "task_id=%s trace_id=%s build_id=%s "
                        "runtime_generation=%s",
                        run.plan.plan_id,
                        "RuntimeExecutionBoundary.execute",
                        options.get("task_id") or options.get("_task_id") or run.run_id,
                        options.get("trace_id") or options.get("_trace_id") or "",
                        self.manifest.build_id,
                        self.manifest.runtime_generation,
                    )
                    raise LegacyExecutionForbidden(
                        run.plan.plan_id,
                        caller="RuntimeExecutionBoundary.execute",
                    )
                architecture_telemetry.increment("legacy_runtime_invocation_count")
                result = await self.legacy_provider.run(
                    agent_id,
                    request,
                    stream=False,
                )
                node_id = run.plan.nodes[0].node_id
                RuntimeStateMachine.complete_node(
                    run,
                    node_id,
                    status=RuntimeNodeStatus.SUCCEEDED,
                    observation=RuntimeObservation(
                        node_id=node_id,
                        terminal_status=RuntimeNodeStatus.SUCCEEDED,
                        artifact_ids=[
                            item.artifact_id for item in result.artifacts
                        ],
                        facts={
                            "agent_id": result.agent_id,
                            "provider": result.provider,
                            "result_status": result.status.value,
                            "structured_result": result.structured_result,
                        },
                        warnings=list(result.warnings[:8]),
                    ),
                )
                if checkpoint_hook is not None:
                    checkpoint = checkpoint_hook(run)
                    if inspect.isawaitable(checkpoint):
                        await checkpoint
                return result
            return None
        result = await service.run(
            request,
            run,
            context=context,
            checkpoint_hook=checkpoint_hook,
            event_hook=event_hook,
            control_provider=control_provider,
            decision_event_hook=decision_event_hook,
            plan_proposal_provider=plan_proposal_provider,
        )
        return result

    async def finalize(self, db: AsyncSession, **kwargs: Any) -> AgentRun | None:
        """Persist terminal state without exposing lifecycle details to callers."""

        return await self.lifecycle.finalize(db, **kwargs)
