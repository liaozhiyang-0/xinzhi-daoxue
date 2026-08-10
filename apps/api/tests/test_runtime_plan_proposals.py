from __future__ import annotations

import asyncio

import pytest
from app.core.errors import RuntimeReplanBudgetExceededError
from app.database.base import Base
from app.models import SessionModel, TaskEventModel, TaskModel, TaskStatus
from app.repositories import AgentRunRepository, RuntimePlanProposalRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    PlanExecutor,
    RuntimeBudget,
    RuntimeController,
    RuntimeDecision,
    RuntimeNode,
    RuntimeNodeState,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimePlanBudgetImpact,
    RuntimePlanProposal,
    RuntimePlanProposalEvaluationCase,
    RuntimePlanProposalSemanticExpectation,
    RuntimePlanProposalStatus,
    RuntimePlanProposalSuite,
    RuntimeRunStatus,
    evaluate_runtime_plan_proposal_suite,
)
from app.services.runtime_plan_proposals import RuntimePlanProposalService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def test_runtime_plan_proposal_is_checkpointed_and_applied_after_approval(
    tmp_path,
) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'runtime-plan-proposals.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        run = AgentRun(
            run_id="runtime-plan-proposal-run",
            task_id="runtime-plan-proposal-task",
            goal="adapt a plan after verification",
            plan=AgentRunPlan(
                plan_id="adaptive-plan",
                version="1",
                goal="adapt a plan after verification",
                nodes=[
                    RuntimeNode(
                        node_id="observe",
                        node_type="control",
                        handler_id="runtime.observe",
                    )
                ],
            ),
        )
        proposed_plan = AgentRunPlan(
            plan_id="adaptive-plan",
            version="2",
            goal="adapt a plan after verification",
            nodes=[
                RuntimeNode(
                    node_id="observe",
                    node_type="control",
                    handler_id="runtime.observe",
                ),
                RuntimeNode(
                    node_id="execute.v2",
                    node_type="provider",
                    handler_id="provider.answer.v2",
                    depends_on=["observe"],
                ),
            ],
        )
        run.control_data = {
            "request": {"runtime_replan_iteration": 1},
            "runtime_facts": {"verification": "partial"},
        }

        async with session_factory() as db:
            db.add(
                SessionModel(
                    id="runtime-plan-proposal-session",
                    user_id="runtime-plan-proposal-user",
                    course_id="CT",
                )
            )
            db.add(
                TaskModel(
                    id="runtime-plan-proposal-task",
                    session_id="runtime-plan-proposal-session",
                    user_id="runtime-plan-proposal-user",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="GENERAL_QUESTION_V1",
                    status=TaskStatus.RUNNING,
                    input_content={"text": "adaptive"},
                )
            )
            await db.flush()
            await AgentRunRepository(db).create(
                run,
                agent_id="GENERAL_QUESTION_V1",
                provider="mock",
            )
            await db.commit()

        async with session_factory() as db:
            service = RuntimePlanProposalService(db)
            proposal = await service.create(
                run.task_id,
                run.run_id,
                proposed_plan,
                reason_codes=["verification_requires_new_action"],
                rationale="The verification result requires a provider action.",
            )
            assert proposal.status.value == "pending"
            assert proposal.affected_node_ids == ["execute.v2"]
            assert proposal.budget_impact.model_calls == 1
            assert proposal.state_version > proposal.base_state_version

            repository = AgentRunRepository(db)
            paused = await repository.restore(run.run_id)
            assert paused is not None
            assert paused.status.value == "waiting_approval"
            assert paused.plan.version == "1"
            assert paused.control_data["plan_proposal_id"] == proposal.proposal_id
            task = await db.get(TaskModel, run.task_id)
            assert task is not None
            assert task.status == TaskStatus.WAITING_REVIEW

            proposal_model = await RuntimePlanProposalRepository(db).get(
                proposal.proposal_id
            )
            assert proposal_model is not None
            task = await service.decide(
                run.task_id,
                proposal.proposal_id,
                approved=True,
                expected_state_version=proposal_model.state_version,
            )
            assert task.status == TaskStatus.QUEUED
            applied = await repository.restore(run.run_id)
            assert applied is not None
            assert applied.status.value == "running"
            assert applied.plan.version == "2"
            assert applied.iteration == 1
            assert applied.control_data == {
                "request": {"runtime_replan_iteration": 1},
                "runtime_facts": {"verification": "partial"},
            }
            assert applied.nodes["execute.v2"].status.value == "pending"

            stored = await RuntimePlanProposalRepository(db).get(
                proposal.proposal_id
            )
            assert stored is not None
            assert stored.status == "applied"
            assert stored.applied_at is not None
            events = list(
                (
                    await db.scalars(
                        select(TaskEventModel)
                        .where(TaskEventModel.task_id == run.task_id)
                        .order_by(TaskEventModel.sequence)
                    )
                ).all()
            )
            assert [event.sequence for event in events] == [1, 2]
            assert events[0].event_type == "agent.progress"
            assert events[1].event_type == "plan.rerouted"
            await db.commit()

        await engine.dispose()

    asyncio.run(scenario())


def test_rejected_runtime_plan_proposal_does_not_replace_plan(tmp_path) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'runtime-plan-reject.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        run = AgentRun(
            run_id="runtime-plan-reject-run",
            task_id="runtime-plan-reject-task",
            goal="reject an unsafe adaptive plan",
            plan=AgentRunPlan(
                plan_id="reject-plan",
                version="1",
                goal="reject an unsafe adaptive plan",
                nodes=[
                    RuntimeNode(
                        node_id="observe",
                        node_type="control",
                        handler_id="runtime.observe",
                    )
                ],
            ),
        )
        async with session_factory() as db:
            db.add(
                SessionModel(
                    id="runtime-plan-reject-session",
                    user_id="runtime-plan-reject-user",
                    course_id="CT",
                )
            )
            db.add(
                TaskModel(
                    id=run.task_id,
                    session_id="runtime-plan-reject-session",
                    user_id="runtime-plan-reject-user",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="GENERAL_QUESTION_V1",
                    status=TaskStatus.RUNNING,
                    input_content={"text": "reject"},
                )
            )
            await db.flush()
            await AgentRunRepository(db).create(
                run,
                agent_id="GENERAL_QUESTION_V1",
                provider="mock",
            )
            await db.commit()

        proposed = run.plan.model_copy(update={"version": "2"})
        async with session_factory() as db:
            service = RuntimePlanProposalService(db)
            proposal = await service.create(
                run.task_id,
                run.run_id,
                proposed,
                reason_codes=["manual_review_required"],
                rationale="Review rejected the proposed change.",
            )
            proposal_model = await RuntimePlanProposalRepository(db).get(
                proposal.proposal_id
            )
            assert proposal_model is not None
            task = await service.decide(
                run.task_id,
                proposal.proposal_id,
                approved=False,
                reason="insufficient evidence",
                expected_state_version=proposal_model.state_version,
            )
            assert task.status == TaskStatus.QUEUED
            restored = await AgentRunRepository(db).restore(run.run_id)
            assert restored is not None
            assert restored.plan.version == "1"
            assert restored.status.value == "paused"
            assert restored.control_data == {}
            stored = await RuntimePlanProposalRepository(db).get(
                proposal.proposal_id
            )
            assert stored is not None
            assert stored.status == "rejected"
            await db.commit()

        await engine.dispose()

    asyncio.run(scenario())


def test_runtime_controller_waits_for_pending_plan_proposal() -> None:
    async def scenario() -> None:
        run = AgentRun(
            run_id="controller-plan-proposal-run",
            task_id="controller-plan-proposal-task",
            goal="wait for plan approval",
            plan=AgentRunPlan(
                plan_id="controller-plan",
                version="1",
                goal="wait for plan approval",
                nodes=[
                    RuntimeNode(
                        node_id="verify",
                        node_type="verification",
                        handler_id="runtime.verify",
                    )
                ],
            ),
        )
        proposed_plan = run.plan.model_copy(update={"version": "2"})
        calls: list[str] = []

        async def decide(_run: AgentRun) -> RuntimeDecision:
            calls.append("decide")
            return RuntimeDecision(
                action=DecisionAction.REPLAN,
                reason_codes=["verification_requires_replan"],
            )

        async def replan(
            _run: AgentRun, _decision: RuntimeDecision
        ) -> AgentRunPlan:
            calls.append("replan")
            return proposed_plan

        async def proposal(
            current: AgentRun,
            _decision: RuntimeDecision,
            plan: AgentRunPlan,
        ) -> RuntimePlanProposal:
            calls.append("proposal")
            return RuntimePlanProposal(
                proposal_id="pending-controller-proposal",
                task_id=current.task_id,
                run_id=current.run_id,
                base_iteration=current.iteration - 1,
                target_iteration=current.iteration,
                base_state_version=current.state_version,
                state_version=current.state_version,
                base_plan_id=current.plan.plan_id,
                base_plan_version=current.plan.version,
                proposed_plan=plan,
                reason_codes=["verification_requires_replan"],
                rationale="A review gate is required before plan replacement.",
                budget_impact=RuntimePlanBudgetImpact.from_plan(plan),
                status=RuntimePlanProposalStatus.PENDING,
            )

        controller = RuntimeController(
            PlanExecutor({}),
            decide,
            replan_provider=replan,
            plan_proposal_provider=proposal,
        )
        result = await controller.run(run)
        assert result.status == RuntimeRunStatus.WAITING_APPROVAL
        assert result.plan.version == "1"
        assert result.control_data == {
            "plan_proposal_id": "pending-controller-proposal",
            "plan_proposal_status": "pending",
        }
        assert calls == ["decide", "replan", "proposal"]

    asyncio.run(scenario())


def test_plan_proposal_quality_gate_checks_budget_and_affected_nodes() -> None:
    base_run = AgentRun(
        run_id="proposal-eval-run",
        task_id="proposal-eval-task",
        goal="evaluate an adaptive proposal",
        plan=AgentRunPlan(
            plan_id="proposal-eval-plan",
            version="1",
            goal="evaluate an adaptive proposal",
            nodes=[
                RuntimeNode(
                    node_id="verify",
                    node_type="verification",
                    handler_id="runtime.verify",
                )
            ],
        ),
    )
    proposed = base_run.plan.model_copy(
        update={
            "version": "2",
            "nodes": [
                *base_run.plan.nodes,
                RuntimeNode(
                    node_id="execute",
                    node_type="provider",
                    handler_id="provider.answer",
                    depends_on=["verify"],
                ),
            ],
        }
    )
    proposal = RuntimePlanProposal(
        proposal_id="proposal-eval-1",
        task_id=base_run.task_id,
        run_id=base_run.run_id,
        base_iteration=0,
        target_iteration=1,
        base_state_version=1,
        state_version=2,
        base_plan_id=base_run.plan.plan_id,
        base_plan_version=base_run.plan.version,
        proposed_plan=proposed,
        reason_codes=["verification_requires_replan"],
        rationale="The verification result requires a provider action.",
        affected_node_ids=["execute"],
        budget_impact=RuntimePlanBudgetImpact(model_calls=1),
        status=RuntimePlanProposalStatus.PENDING,
    )
    passed = evaluate_runtime_plan_proposal_suite(
        RuntimePlanProposalSuite(
            suite_id="proposal-eval-suite",
            cases=[
                RuntimePlanProposalEvaluationCase(
                    case_id="valid",
                    base_run=base_run,
                    proposal=proposal,
                )
            ],
        )
    )
    assert passed.canary_eligible is True
    assert passed.results[0].passed is True

    invalid = proposal.model_copy(
        update={"budget_impact": RuntimePlanBudgetImpact(model_calls=0)}
    )
    failed = evaluate_runtime_plan_proposal_suite(
        RuntimePlanProposalSuite(
            suite_id="proposal-eval-suite-invalid",
            cases=[
                RuntimePlanProposalEvaluationCase(
                    case_id="invalid-budget",
                    base_run=base_run,
                    proposal=invalid,
                )
            ],
        )
    )
    assert failed.canary_eligible is False
    assert "budget_impact_not_conservative" in (
        failed.results[0].failed_checks
    )


def test_plan_proposal_budget_exhaustion_has_stable_error_code() -> None:
    base_run = AgentRun(
        run_id="proposal-budget-run",
        task_id="proposal-budget-task",
        goal="avoid an over-budget replan",
        plan=AgentRunPlan(
            plan_id="proposal-budget-plan",
            version="1",
            goal="avoid an over-budget replan",
            nodes=[
                RuntimeNode(
                    node_id="verify",
                    node_type="verification",
                    handler_id="runtime.verify",
                )
            ],
        ),
        budget=RuntimeBudget(max_subagent_runs=0),
    )
    proposed = base_run.plan.model_copy(
        update={
            "version": "2",
            "nodes": [
                *base_run.plan.nodes,
                RuntimeNode(
                    node_id="execute",
                    node_type="subagent",
                    handler_id="subagent.answer",
                    depends_on=["verify"],
                ),
            ],
        }
    )

    with pytest.raises(
        RuntimeReplanBudgetExceededError,
        match="proposed plan exceeds remaining Runtime budget",
    ) as error:
        RuntimePlanProposalService._assert_budget(base_run, proposed)

    assert error.value.code == "runtime_replan_budget_exhausted"


def test_plan_proposal_semantic_gate_requires_failure_alignment() -> None:
    base_run = AgentRun(
        run_id="semantic-proposal-run",
        task_id="semantic-proposal-task",
        goal="recover from verification failure",
        plan=AgentRunPlan(
            plan_id="semantic-proposal-plan",
            version="1",
            goal="recover from verification failure",
            nodes=[
                RuntimeNode(
                    node_id="verify",
                    node_type="verification",
                    handler_id="runtime.verify",
                )
            ],
        ),
    )
    failed_verification = RuntimeObservation(
        node_id="verify",
        terminal_status=RuntimeNodeStatus.PARTIAL,
        facts={"passed": False, "replan_required": True},
    )
    base_run.nodes["verify"] = RuntimeNodeState(
        node_id="verify",
        status=RuntimeNodeStatus.PARTIAL,
        observation=failed_verification,
    )
    base_run.observations.append(failed_verification)
    base_run.last_decision = RuntimeDecision(
        action=DecisionAction.REPLAN,
        reason_codes=["verification_requires_recovery"],
    )
    proposed_plan = base_run.plan.model_copy(
        update={
            "version": "2",
            "nodes": [
                *base_run.plan.nodes,
                RuntimeNode(
                    node_id="execute.recovery",
                    node_type="provider",
                    handler_id="provider.recovery",
                    depends_on=["verify"],
                ),
            ],
        }
    )
    proposal = RuntimePlanProposal(
        proposal_id="semantic-proposal-1",
        task_id=base_run.task_id,
        run_id=base_run.run_id,
        base_iteration=0,
        target_iteration=1,
        base_state_version=1,
        state_version=2,
        base_plan_id=base_run.plan.plan_id,
        base_plan_version=base_run.plan.version,
        proposed_plan=proposed_plan,
        reason_codes=["verification_requires_recovery"],
        rationale="The failed verification requires a recovery action.",
        affected_node_ids=["execute.recovery"],
        budget_impact=RuntimePlanBudgetImpact(model_calls=1),
        status=RuntimePlanProposalStatus.PENDING,
    )
    expectation = RuntimePlanProposalSemanticExpectation(
        verification_node_ids=["verify"],
        verification_reason_codes=["verification_requires_recovery"],
    )
    passed = evaluate_runtime_plan_proposal_suite(
        RuntimePlanProposalSuite(
            suite_id="semantic-proposal-suite",
            require_semantic_alignment=True,
            cases=[
                RuntimePlanProposalEvaluationCase(
                    case_id="semantic-valid",
                    base_run=base_run,
                    proposal=proposal,
                    semantic_expectation=expectation,
                )
            ],
        )
    )
    assert passed.canary_eligible is True
    assert passed.results[0].semantic_failures == []

    unrelated = proposal.model_copy(
        update={
            "reason_codes": ["unrelated_failure"],
            "affected_node_ids": ["execute.recovery"],
            "proposed_plan": proposed_plan.model_copy(
                update={
                    "nodes": [
                        *base_run.plan.nodes,
                        RuntimeNode(
                            node_id="execute.recovery",
                            node_type="provider",
                            handler_id="provider.recovery",
                        ),
                    ]
                }
            ),
        }
    )
    failed = evaluate_runtime_plan_proposal_suite(
        RuntimePlanProposalSuite(
            suite_id="semantic-proposal-suite-invalid",
            require_semantic_alignment=True,
            cases=[
                RuntimePlanProposalEvaluationCase(
                    case_id="semantic-invalid",
                    base_run=base_run,
                    proposal=unrelated,
                    semantic_expectation=expectation,
                )
            ],
        )
    )
    assert failed.canary_eligible is False
    assert "proposal_reason_not_aligned_with_verification" in (
        failed.results[0].semantic_failures
    )
    assert "proposal_does_not_touch_verification_node" in (
        failed.results[0].semantic_failures
    )
