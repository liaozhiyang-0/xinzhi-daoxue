"""Durable proposal and approval boundary for adaptive Runtime plans."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentEventType
from app.core.errors import (
    ConflictError,
    NotFoundError,
    RuntimeReplanBudgetExceededError,
)
from app.models import AgentPlanProposalModel, TaskModel, TaskStatus
from app.repositories import AgentRunRepository, RuntimePlanProposalRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    RuntimeNodeStatus,
    RuntimePlanBudgetImpact,
    RuntimePlanProposal,
    RuntimePlanProposalStatus,
    RuntimeRunStatus,
    RuntimeStateMachine,
)
from app.services.event_service import append_task_event


class RuntimePlanProposalService:
    """Persist and apply a plan replacement with optimistic concurrency."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        task_id: str,
        runtime_run_id: str,
        proposed_plan: AgentRunPlan,
        *,
        reason_codes: Iterable[str],
        rationale: str,
        approval_required: bool = True,
        expected_state_version: int | None = None,
        target_iteration: int | None = None,
    ) -> RuntimePlanProposal:
        task = await self._task(task_id)
        runtime_repository = AgentRunRepository(self.db)
        runtime_model = await runtime_repository.get(
            runtime_run_id, for_update=True
        )
        if runtime_model is None or runtime_model.task_id != task.id:
            raise NotFoundError("Runtime run not found")
        run = await runtime_repository.restore(runtime_model.id)
        if run is None:
            raise ConflictError("Runtime checkpoint is missing")
        self._assert_current_version(
            run,
            runtime_model.state_version,
            expected_state_version,
        )
        self._assert_no_running_nodes(run)
        self._assert_budget(run, proposed_plan)
        next_iteration = (
            target_iteration if target_iteration is not None else run.iteration + 1
        )
        if next_iteration <= run.iteration:
            raise ConflictError("plan proposal target iteration is not ahead")
        if next_iteration >= run.budget.max_iterations:
            raise RuntimeReplanBudgetExceededError(
                "Runtime replan budget exhausted",
                details={
                    "iteration": run.iteration,
                    "max_iterations": run.budget.max_iterations,
                },
            )

        reasons = _bounded_reasons(reason_codes)
        proposal = RuntimePlanProposal(
            proposal_id=uuid4().hex,
            task_id=task.id,
            run_id=run.run_id,
            base_iteration=run.iteration,
            target_iteration=next_iteration,
            base_state_version=run.state_version,
            state_version=run.state_version,
            base_plan_id=run.plan.plan_id,
            base_plan_version=run.plan.version,
            proposed_plan=proposed_plan,
            reason_codes=reasons,
            rationale=rationale,
            affected_node_ids=_affected_nodes(run.plan, proposed_plan),
            budget_impact=RuntimePlanBudgetImpact.from_plan(proposed_plan),
            approval_required=approval_required,
            status=(
                RuntimePlanProposalStatus.PENDING
                if approval_required
                else RuntimePlanProposalStatus.APPROVED
            ),
        )
        proposal_repository = RuntimePlanProposalRepository(self.db)
        model = await proposal_repository.create(proposal)
        if approval_required:
            control_data = dict(run.control_data)
            control_data["plan_proposal_id"] = proposal.proposal_id
            control_data["plan_proposal_status"] = "pending"
            run.control_data = control_data
            run.control_request = ""
            run.status = RuntimeRunStatus.WAITING_APPROVAL
            await runtime_repository.save_checkpoint(run)
            model.state_version = run.state_version
            task.status = TaskStatus.WAITING_REVIEW
            await append_task_event(
                self.db,
                task.id,
                AgentEventType.AGENT_PROGRESS,
                agent_id=task.agent_id,
                data={
                    "stage_id": "runtime_plan_proposal",
                    "status": "approval_required",
                    "runtime_run_id": run.run_id,
                    "proposal_id": proposal.proposal_id,
                    "base_plan_id": proposal.base_plan_id,
                    "base_plan_version": proposal.base_plan_version,
                    "affected_node_ids": proposal.affected_node_ids,
                    "reason_codes": proposal.reason_codes,
                    "budget_impact": proposal.budget_impact.model_dump(
                        mode="json"
                    ),
                    "state_version": run.state_version,
                },
            )
        else:
            await self._apply(
                task,
                model,
                run,
                runtime_repository,
                decision_reason="auto_apply_not_required",
            )
        await self.db.commit()
        proposal.state_version = model.state_version
        proposal.status = RuntimePlanProposalStatus(model.status)
        proposal.decided_at = model.decided_at
        proposal.applied_at = model.applied_at
        return proposal

    async def decide(
        self,
        task_id: str,
        proposal_id: str,
        *,
        approved: bool,
        reason: str = "",
        expected_state_version: int | None = None,
    ) -> TaskModel:
        task = await self._task(task_id, for_update=True)
        if task.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }:
            raise ConflictError("terminal tasks cannot decide a plan proposal")
        proposal_repository = RuntimePlanProposalRepository(self.db)
        proposal_model = await proposal_repository.get(
            proposal_id, for_update=True
        )
        if proposal_model is None or proposal_model.task_id != task.id:
            raise NotFoundError("plan proposal not found")
        if proposal_model.status != RuntimePlanProposalStatus.PENDING.value:
            raise ConflictError(
                "plan proposal is no longer pending",
                details={"status": proposal_model.status},
            )

        runtime_repository = AgentRunRepository(self.db)
        runtime_model = await runtime_repository.get(
            proposal_model.run_id, for_update=True
        )
        if runtime_model is None:
            raise ConflictError("Runtime run for plan proposal is missing")
        pending_gate_marker = (
            runtime_model.status == RuntimeRunStatus.WAITING_APPROVAL.value
            and (runtime_model.control_data or {}).get("plan_proposal_id")
            == proposal_model.id
        )
        proposal_checkpoint_drift = pending_gate_marker and (
            runtime_model.state_version >= proposal_model.state_version
        )
        stale_review_read = (
            pending_gate_marker
            and expected_state_version is not None
            and expected_state_version + 1 == runtime_model.state_version
            and proposal_model.state_version == runtime_model.state_version
        )
        if expected_state_version is not None and (
            runtime_model.state_version != expected_state_version
        ):
            if not (
                (
                    proposal_checkpoint_drift
                    and expected_state_version == proposal_model.state_version
                )
                or stale_review_read
            ):
                raise ConflictError(
                    "Runtime state version has changed",
                    details={
                        "expected_state_version": expected_state_version,
                        "actual_state_version": runtime_model.state_version,
                    },
                )
        run = await runtime_repository.restore(runtime_model.id)
        if run is None:
            raise ConflictError("Runtime checkpoint is missing")
        self._assert_current_version(run, runtime_model.state_version, None)
        if run.state_version != proposal_model.state_version:
            if not proposal_checkpoint_drift:
                raise ConflictError(
                    "plan proposal checkpoint is stale",
                    details={
                        "proposal_state_version": proposal_model.state_version,
                        "runtime_state_version": run.state_version,
                    },
                )
            # A controller suspension checkpoint may be written immediately
            # after proposal creation. Treat that single, marked snapshot as
            # part of the same proposal transaction and advance its CAS token.
            proposal_model.state_version = run.state_version
        if not approved:
            await self._reject(
                task,
                proposal_model,
                run,
                runtime_repository,
                reason=reason,
            )
        else:
            proposed_plan = AgentRunPlan.model_validate(
                proposal_model.proposed_plan_data
            )
            self._assert_proposal_base(run, proposal_model)
            self._assert_budget(run, proposed_plan)
            await self._apply(
                task,
                proposal_model,
                run,
                runtime_repository,
                decision_reason=reason or "approved",
            )
        await self.db.commit()
        return task

    async def list(self, task_id: str) -> list[RuntimePlanProposal]:
        await self._task(task_id)
        models = await RuntimePlanProposalRepository(self.db).list_for_task(
            task_id
        )
        return [RuntimePlanProposalRepository.to_contract(item) for item in models]

    async def _apply(
        self,
        task: TaskModel,
        proposal_model: AgentPlanProposalModel,
        run: AgentRun,
        runtime_repository: AgentRunRepository,
        *,
        decision_reason: str,
    ) -> None:
        self._assert_no_running_nodes(run)
        if run.iteration >= run.budget.max_iterations - 1:
            if run.iteration != proposal_model.target_iteration:
                raise RuntimeReplanBudgetExceededError(
                    "Runtime replan budget exhausted",
                    details={
                        "iteration": run.iteration,
                        "max_iterations": run.budget.max_iterations,
                    },
                )
        proposed_plan = AgentRunPlan.model_validate(
            proposal_model.proposed_plan_data
        )
        self._assert_proposal_base(run, proposal_model)
        if run.iteration > proposal_model.target_iteration:
            raise ConflictError("Runtime iteration has advanced")
        run.iteration = proposal_model.target_iteration
        RuntimeStateMachine.replace_plan(run, proposed_plan)
        run.control_request = ""
        control_data = dict(run.control_data)
        if control_data.get("plan_proposal_id") == proposal_model.id:
            control_data.pop("plan_proposal_id", None)
            control_data.pop("plan_proposal_status", None)
        run.control_data = control_data
        run.completed_at = None
        await runtime_repository.save_checkpoint(run)
        now = datetime.now(UTC)
        proposal_model.status = RuntimePlanProposalStatus.APPLIED.value
        proposal_model.state_version = run.state_version
        proposal_model.decided_at = proposal_model.decided_at or now
        proposal_model.applied_at = now
        proposal_model.decision_reason = decision_reason
        task.status = TaskStatus.QUEUED
        task.updated_at = now
        await append_task_event(
            self.db,
            task.id,
            AgentEventType.PLAN_REROUTED,
            agent_id=task.agent_id,
            data={
                "stage_id": "runtime_plan_proposal",
                "status": "applied",
                "runtime_run_id": run.run_id,
                "proposal_id": proposal_model.id,
                "plan_id": run.plan.plan_id,
                "plan_version": run.plan.version,
                "iteration": run.iteration,
                "reason_codes": list(proposal_model.reason_codes or []),
                "affected_node_ids": list(
                    proposal_model.affected_node_ids or []
                ),
                "budget_impact": dict(
                    proposal_model.budget_impact_data or {}
                ),
                "state_version": run.state_version,
            },
        )

    async def _reject(
        self,
        task: TaskModel,
        proposal_model: AgentPlanProposalModel,
        run: AgentRun,
        runtime_repository: AgentRunRepository,
        *,
        reason: str,
    ) -> None:
        control_data = dict(run.control_data)
        if control_data.get("plan_proposal_id") == proposal_model.id:
            control_data.pop("plan_proposal_id", None)
            control_data.pop("plan_proposal_status", None)
        run.control_data = control_data
        run.control_request = ""
        run.status = RuntimeRunStatus.PAUSED
        await runtime_repository.save_checkpoint(run)
        now = datetime.now(UTC)
        proposal_model.status = RuntimePlanProposalStatus.REJECTED.value
        proposal_model.decided_at = now
        proposal_model.decision_reason = reason or "rejected"
        task.status = TaskStatus.QUEUED
        task.updated_at = now
        await append_task_event(
            self.db,
            task.id,
            AgentEventType.AGENT_PROGRESS,
            agent_id=task.agent_id,
            data={
                "stage_id": "runtime_plan_proposal",
                "status": "rejected",
                "runtime_run_id": run.run_id,
                "proposal_id": proposal_model.id,
                "reason": proposal_model.decision_reason,
                "state_version": run.state_version,
            },
        )

    async def _task(
        self, task_id: str, *, for_update: bool = False
    ) -> TaskModel:
        from app.repositories import TaskRepository

        task = await TaskRepository(self.db).get(task_id, for_update=for_update)
        if task is None:
            raise NotFoundError("task not found", details={"task_id": task_id})
        return task

    @staticmethod
    def _assert_current_version(
        run: AgentRun,
        model_state_version: int,
        expected_state_version: int | None,
    ) -> None:
        if run.state_version != model_state_version:
            raise ConflictError("Runtime checkpoint is stale")
        if (
            expected_state_version is not None
            and run.state_version != expected_state_version
        ):
            raise ConflictError(
                "Runtime state version has changed",
                details={
                    "expected_state_version": expected_state_version,
                    "actual_state_version": run.state_version,
                },
            )

    @staticmethod
    def _assert_no_running_nodes(run: AgentRun) -> None:
        if any(
            state.status == RuntimeNodeStatus.RUNNING
            for state in run.nodes.values()
        ):
            raise ConflictError("cannot propose a plan while a node is running")

    @staticmethod
    def _assert_budget(run: AgentRun, plan: AgentRunPlan) -> None:
        impact = RuntimePlanBudgetImpact.from_plan(plan)
        remaining = (
            run.budget.max_model_calls - run.budget.model_calls,
            run.budget.max_tool_calls - run.budget.tool_calls,
            run.budget.max_subagent_runs - run.budget.subagent_runs,
        )
        requested = (
            impact.model_calls,
            impact.tool_calls,
            impact.subagent_runs,
        )
        if any(
            value > limit
            for value, limit in zip(requested, remaining, strict=True)
        ):
            raise RuntimeReplanBudgetExceededError(
                "proposed plan exceeds remaining Runtime budget",
                details={
                    "requested": impact.model_dump(mode="json"),
                    "remaining": {
                        "model_calls": remaining[0],
                        "tool_calls": remaining[1],
                        "subagent_runs": remaining[2],
                    },
                },
            )

    @staticmethod
    def _assert_proposal_base(
        run: AgentRun, proposal_model: AgentPlanProposalModel
    ) -> None:
        if (
            run.plan.plan_id != proposal_model.base_plan_id
            or run.plan.version != proposal_model.base_plan_version
            or run.state_version < proposal_model.base_state_version
        ):
            raise ConflictError("plan proposal base has changed")


def _bounded_reasons(values: Iterable[str]) -> list[str]:
    reasons = [value.strip() for value in values if value.strip()]
    if not reasons:
        raise ConflictError("plan proposal requires a reason")
    if len(reasons) > 16:
        raise ConflictError("plan proposal has too many reason codes")
    return reasons


def _affected_nodes(
    previous: AgentRunPlan, proposed: AgentRunPlan
) -> list[str]:
    previous_by_id = {node.node_id: node for node in previous.nodes}
    proposed_by_id = {node.node_id: node for node in proposed.nodes}
    changed = {
        node_id
        for node_id in previous_by_id.keys() | proposed_by_id.keys()
        if (
            previous_by_id.get(node_id) is None
            or proposed_by_id.get(node_id) is None
            or previous_by_id[node_id].model_dump(mode="json")
            != proposed_by_id[node_id].model_dump(mode="json")
        )
    }
    return sorted(changed)
