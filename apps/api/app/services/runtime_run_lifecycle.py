from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.intent import IntentExecutionPlan
from app.observability.architecture_telemetry import architecture_telemetry
from app.repositories import AgentRunRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeCompatibilitySnapshot,
    RuntimeLaunchSnapshot,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeRunStatus,
    RuntimeStateMachine,
)
from app.services.production_execution_manifest import (
    ExecutionSurfaceError,
    ProductionExecutionManifest,
)


class RuntimeRunLifecycleService:
    """Create, restore, and finalize durable Runtime runs."""

    def __init__(
        self,
        *,
        enabled: bool,
        timeout_ms: int = 120_000,
        max_retries: int = 0,
        manifest: ProductionExecutionManifest | None = None,
    ) -> None:
        self.enabled = enabled
        self.timeout_ms = max(100, min(900_000, timeout_ms))
        self.max_retries = max(0, min(5, max_retries))
        self.manifest = manifest

    def bind_manifest(self, manifest: ProductionExecutionManifest) -> None:
        self.manifest = manifest

    async def start(
        self,
        db: AsyncSession,
        *,
        task_id: str,
        agent_id: str,
        provider: str,
        goal: str,
        intent_plan: IntentExecutionPlan | None = None,
        runtime_plan: AgentRunPlan | None = None,
        request_snapshot: dict[str, Any] | None = None,
        launch_decision: RuntimeLaunchSnapshot | None = None,
        compatibility_snapshot: RuntimeCompatibilitySnapshot | None = None,
    ) -> AgentRun | None:
        if not self.enabled:
            return None
        repository = AgentRunRepository(db)
        existing = await repository.get_for_task(task_id, for_update=True)
        if existing is not None:
            restored = await repository.restore(existing.id)
            if restored is not None:
                restored.control_request = existing.control_request
                restored.control_data = dict(existing.control_data or {})
                needs_snapshot_persist = False
                if restored.launch_decision is None and launch_decision is not None:
                    restored.launch_decision = launch_decision
                    needs_snapshot_persist = True
                if (
                    restored.compatibility_snapshot is None
                    and compatibility_snapshot is not None
                ):
                    restored.compatibility_snapshot = compatibility_snapshot
                    needs_snapshot_persist = True
                if needs_snapshot_persist:
                    await repository.save_checkpoint(restored)
            return restored

        if runtime_plan is None:
            if self.manifest is not None:
                raise ExecutionSurfaceError(
                    "RUNTIME_PLAN_NOT_ACTIVE",
                    "a production Runtime run requires an active plan",
                )
            architecture_telemetry.increment("legacy_plan_creation_count")
            run_plan = self._build_legacy_plan(agent_id, goal)
        else:
            run_plan = runtime_plan
        if self.manifest is not None:
            self.manifest.validate_runtime_plan(
                run_plan,
                caller="RuntimeRunLifecycleService.start",
            )
        run = AgentRun(
            run_id=uuid4().hex,
            task_id=task_id,
            goal=goal.strip()[:8_000] or f"task:{task_id}",
            plan=run_plan,
            request_snapshot=dict(request_snapshot or {}),
            control_data=(
                {"request": dict(request_snapshot or {})}
                if run_plan.plan_id.startswith("legacy-runtime:")
                and request_snapshot
                else {}
            ),
            launch_decision=launch_decision,
            compatibility_snapshot=compatibility_snapshot,
        )
        if runtime_plan is None or run_plan.plan_id.startswith("legacy-runtime:"):
            RuntimeStateMachine.mark_ready(run)
            RuntimeStateMachine.start_node(run, run_plan.nodes[0].node_id)
        await repository.create(run, agent_id=agent_id, provider=provider)
        return run

    @staticmethod
    def _build_legacy_plan(agent_id: str, goal: str) -> AgentRunPlan:
        """Keep the durable control envelope usable around legacy tasks."""

        return AgentRunPlan(
            plan_id=f"legacy-runtime:{agent_id}",
            version="compat-1",
            goal=goal.strip()[:8_000] or f"task:{agent_id}",
            nodes=[
                RuntimeNode(
                    node_id="legacy.execution",
                    node_type="workflow",
                    # The provider adapter is the smallest compatibility
                    # boundary for agents that have not migrated to a
                    # business Runtime plan yet.
                    handler_id="provider.default",
                    target_id=agent_id,
                    timeout_ms=900_000,
                )
            ],
            success_criteria=["legacy_task_terminal_status"],
        )

    async def finalize(
        self,
        db: AsyncSession,
        *,
        task_id: str,
        status: RuntimeRunStatus | str,
        provider: str | None = None,
        metrics_data: dict[str, object] | None = None,
        latency_ms: int | None = None,
        trace_id: str | None = None,
        artifact_ids: Iterable[str] = (),
        error_code: str = "",
        terminal_reason: str = "",
        run: AgentRun | None = None,
    ) -> AgentRun | None:
        if not self.enabled and run is None:
            return None
        repository = AgentRunRepository(db)
        if run is None:
            model = await repository.get_for_task(task_id, for_update=True)
            if model is None:
                return None
            run = await repository.restore(model.id)
            if run is None:
                return None

        target_status = RuntimeRunStatus(status)
        for node_id, node_state in run.nodes.items():
            if node_state.status == RuntimeNodeStatus.RUNNING:
                RuntimeStateMachine.complete_node(
                    run,
                    node_id,
                    status=(
                        RuntimeNodeStatus.SKIPPED
                        if target_status == RuntimeRunStatus.CANCELLED
                        else RuntimeNodeStatus.FAILED
                    ),
                    error_code=error_code or "task_terminal",
                )
            elif node_state.status in {
                RuntimeNodeStatus.PENDING,
                RuntimeNodeStatus.READY,
            }:
                RuntimeStateMachine.block_node(
                    run,
                    node_id,
                    error_code=error_code or "task_terminal",
                )
        run.status = target_status
        checkpoint = await repository.save_checkpoint(
            run,
            provider=provider,
            metrics_data=metrics_data,
            latency_ms=latency_ms,
            trace_id=trace_id,
            terminal_reason=terminal_reason,
        )
        del checkpoint
        return run
