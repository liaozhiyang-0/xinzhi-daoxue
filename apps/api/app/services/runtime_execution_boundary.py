"""Boundary between the durable Agent Runtime and the legacy TaskRunner.

This module deliberately contains no routing, retrieval, presentation, or
Task status policy. It owns only Runtime lifecycle decisions so business
Runtime implementations can be moved out of TaskRunner incrementally.
"""

from __future__ import annotations

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
from app.repositories import AgentRunRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    PlanProposalProvider,
    RuntimeCompatibilitySnapshot,
    RuntimeDecision,
    RuntimeLaunchSnapshot,
    RuntimeRunStatus,
)
from app.services.research_analysis_runtime import ResearchAnalysisRuntimeService
from app.services.runtime_business_registry import (
    RuntimeBusinessRegistry,
    RuntimeBusinessService,
)
from app.services.runtime_compatibility_preparation import (
    RuntimeCompatibilityPreparation,
    RuntimeCompatibilityPreparationService,
)
from app.services.runtime_launch_policy import (
    RuntimeLaunchDecision,
    RuntimeLaunchMode,
)
from app.services.runtime_run_lifecycle import RuntimeRunLifecycleService


class RuntimeResumeInvariantError(RuntimeError):
    """Raised when durable compatibility state no longer matches a resume."""


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
        compatibility_preparation: RuntimeCompatibilityPreparationService
        | None = None,
    ) -> None:
        self.lifecycle = lifecycle
        self.research_analysis = research_analysis
        self.compatibility_preparation = compatibility_preparation
        services = list(business_services or [])
        if research_analysis is not None and research_analysis not in services:
            services.insert(0, research_analysis)
        self.business_registry = RuntimeBusinessRegistry(services)

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
                if run is not None:
                    RuntimeExecutionBoundary._record_handoff_failure(
                        run,
                        runtime_status=runtime_status,
                        reason=reason,
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
    def _record_handoff_failure(
        run: AgentRun, *, runtime_status: str, reason: str
    ) -> None:
        control_data = dict(run.control_data)
        control_data["runtime_handoff"] = {
            "status": "legacy_fallback",
            "runtime_status": runtime_status,
            "bypass_legacy_execution": False,
            "fallback_reason": reason,
        }
        run.control_data = control_data

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

    async def prepare_compatibility(
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
    ) -> RuntimeCompatibilityPreparation:
        """Prepare the resumable request envelope before Runtime execution."""

        if self.compatibility_preparation is None:
            raise RuntimeError("Runtime compatibility preparation is not configured")
        return await self.compatibility_preparation.prepare(
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
        if runtime_resume or mode != RuntimeLaunchMode.DEFAULT:
            # A resumed Run already persisted the request after all launch
            # compatibility preparation.  Re-applying the default-mode
            # option injection would change the checkpoint identity.
            return request
        return self.business_registry.prepare_default_request(agent_id, request)

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

        service = self.business_registry.resolve(agent_id, request)
        if service is None:
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
        if result is not None and run.status != RuntimeRunStatus.COMPLETED:
            reason = f"runtime_execution_{run.status.value}"
            self._record_handoff_failure(
                run,
                runtime_status=run.status.value,
                reason=reason,
            )
            result = result.model_copy(
                update={
                    "status": AgentResultStatus.FAILED,
                    "fallback_used": True,
                    "fallback_reason": reason,
                }
            )
        return result

    async def finalize(self, db: AsyncSession, **kwargs: Any) -> AgentRun | None:
        """Persist terminal state without exposing lifecycle details to callers."""

        run = kwargs.get("run")
        if (
            isinstance(run, AgentRun)
            and run.control_data.get("runtime_handoff", {}).get("status")
            == "legacy_fallback"
            and kwargs.get("status")
            in {RuntimeRunStatus.COMPLETED, RuntimeRunStatus.COMPLETED.value}
        ):
            kwargs["status"] = RuntimeRunStatus.FAILED
            kwargs["error_code"] = kwargs.get("error_code", "") or (
                "runtime_handoff_failed"
            )
            kwargs["terminal_reason"] = kwargs.get("terminal_reason", "") or (
                "runtime failed; legacy fallback was used"
            )
        return await self.lifecycle.finalize(db, **kwargs)
