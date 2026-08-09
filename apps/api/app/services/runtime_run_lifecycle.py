from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.intent import IntentExecutionPlan
from app.repositories import AgentRunRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeCompatibilitySnapshot,
    RuntimeLaunchSnapshot,
    RuntimeNode,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
    RuntimeStateMachine,
)


class RuntimeRunLifecycleService:
    """Persist a compatibility Runtime envelope around the legacy TaskRunner."""

    def __init__(
        self,
        *,
        enabled: bool,
        timeout_ms: int = 120_000,
        max_retries: int = 0,
    ) -> None:
        self.enabled = enabled
        self.timeout_ms = max(100, min(900_000, timeout_ms))
        self.max_retries = max(0, min(5, max_retries))

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

        run_plan = runtime_plan or self._build_plan(agent_id, goal, intent_plan)
        run = AgentRun(
            run_id=uuid4().hex,
            task_id=task_id,
            goal=goal.strip()[:8_000] or f"task:{task_id}",
            plan=run_plan,
            request_snapshot=dict(request_snapshot or {}),
            launch_decision=launch_decision,
            compatibility_snapshot=compatibility_snapshot,
        )
        if runtime_plan is None:
            RuntimeStateMachine.mark_ready(run)
            RuntimeStateMachine.start_node(run, run_plan.nodes[0].node_id)
        await repository.create(run, agent_id=agent_id, provider=provider)
        return run

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
        compatibility_plan = (
            len(run.plan.nodes) == 1
            and run.plan.nodes[0].node_id == "legacy.execution"
        )
        if compatibility_plan and run.nodes["legacy.execution"].status == (
            RuntimeNodeStatus.RUNNING
        ):
            node_id = "legacy.execution"
            node_status = {
                RuntimeRunStatus.COMPLETED: RuntimeNodeStatus.SUCCEEDED,
                RuntimeRunStatus.FAILED: RuntimeNodeStatus.FAILED,
                RuntimeRunStatus.CANCELLED: RuntimeNodeStatus.SKIPPED,
            }.get(target_status, RuntimeNodeStatus.FAILED)
            RuntimeStateMachine.complete_node(
                run,
                node_id,
                status=node_status,
                observation=RuntimeObservation(
                    node_id=node_id,
                    artifact_ids=list(artifact_ids),
                    facts={
                        "execution_mode": "legacy_task_runner_shadow",
                        "task_status": target_status.value,
                    },
                    errors=[error_code] if error_code else [],
                ),
                error_code=error_code,
            )
        elif not compatibility_plan:
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

    @staticmethod
    def _build_plan(
        agent_id: str,
        goal: str,
        intent_plan: IntentExecutionPlan | None,
    ) -> AgentRunPlan:
        del intent_plan
        return AgentRunPlan(
            plan_id=f"legacy-runtime:{agent_id}",
            version="compat-1",
            goal=goal.strip()[:8_000] or f"task:{agent_id}",
            nodes=[
                RuntimeNode(
                    node_id="legacy.execution",
                    node_type="workflow",
                    handler_id=f"legacy.task_runner.{agent_id}",
                    timeout_ms=900_000,
                )
            ],
            success_criteria=["legacy_task_terminal_status"],
        )
