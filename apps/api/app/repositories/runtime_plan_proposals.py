from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentPlanProposalModel
from app.runtime import RuntimePlanProposal, RuntimePlanProposalStatus


class RuntimePlanProposalRepository:
    """Persistence boundary for versioned Runtime plan proposals."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, proposal: RuntimePlanProposal
    ) -> AgentPlanProposalModel:
        model = AgentPlanProposalModel(
            id=proposal.proposal_id,
            task_id=proposal.task_id,
            run_id=proposal.run_id,
            base_iteration=proposal.base_iteration,
            target_iteration=proposal.target_iteration,
            base_state_version=proposal.base_state_version,
            state_version=proposal.state_version,
            base_plan_id=proposal.base_plan_id,
            base_plan_version=proposal.base_plan_version,
            proposed_plan_data=proposal.proposed_plan.model_dump(mode="json"),
            reason_codes=list(proposal.reason_codes),
            rationale=proposal.rationale,
            affected_node_ids=list(proposal.affected_node_ids),
            budget_impact_data=proposal.budget_impact.model_dump(mode="json"),
            approval_required=proposal.approval_required,
            status=proposal.status.value,
            decision_reason=proposal.decision_reason,
            created_at=proposal.created_at,
            decided_at=proposal.decided_at,
            applied_at=proposal.applied_at,
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def get(
        self, proposal_id: str, *, for_update: bool = False
    ) -> AgentPlanProposalModel | None:
        query = select(AgentPlanProposalModel).where(
            AgentPlanProposalModel.id == proposal_id
        )
        if for_update:
            query = query.with_for_update()
        return cast(
            AgentPlanProposalModel | None,
            await self.session.scalar(query),
        )

    async def list_for_task(
        self, task_id: str, *, status: RuntimePlanProposalStatus | None = None
    ) -> list[AgentPlanProposalModel]:
        query = select(AgentPlanProposalModel).where(
            AgentPlanProposalModel.task_id == task_id
        )
        if status is not None:
            query = query.where(
                AgentPlanProposalModel.status == status.value
            )
        query = query.order_by(AgentPlanProposalModel.created_at.desc())
        result = await self.session.scalars(query)
        return list(result.all())

    async def list_for_run(
        self, run_id: str
    ) -> list[AgentPlanProposalModel]:
        result = await self.session.scalars(
            select(AgentPlanProposalModel)
            .where(AgentPlanProposalModel.run_id == run_id)
            .order_by(AgentPlanProposalModel.created_at.desc())
        )
        return list(result.all())

    @staticmethod
    def to_contract(model: AgentPlanProposalModel) -> RuntimePlanProposal:
        return RuntimePlanProposal(
            proposal_id=model.id,
            task_id=model.task_id,
            run_id=model.run_id,
            base_iteration=model.base_iteration,
            target_iteration=model.target_iteration,
            base_state_version=model.base_state_version,
            state_version=model.state_version,
            base_plan_id=model.base_plan_id,
            base_plan_version=model.base_plan_version,
            proposed_plan=model.proposed_plan_data,
            reason_codes=list(model.reason_codes or []),
            rationale=model.rationale,
            affected_node_ids=list(model.affected_node_ids or []),
            budget_impact=model.budget_impact_data,
            approval_required=model.approval_required,
            status=RuntimePlanProposalStatus(model.status),
            decision_reason=model.decision_reason,
            created_at=model.created_at,
            decided_at=model.decided_at,
            applied_at=model.applied_at,
        )
