from __future__ import annotations

import asyncio

import pytest
from app.contracts import AgentEventType
from app.database.base import Base
from app.models import SessionModel, TaskModel
from app.repositories import AgentRunRepository
from app.runtime import (
    AgentRun,
    AgentRunPlan,
    DecisionAction,
    PlanExecutor,
    RuntimeBudget,
    RuntimeController,
    RuntimeDecision,
    RuntimeEffectStatus,
    RuntimeGoal,
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeNode,
    RuntimeNodeError,
    RuntimeNodeStatus,
    RuntimeObservation,
    RuntimeRunStatus,
    RuntimeStateMachine,
    to_task_event,
)
from app.services.event_service import append_task_event
from app.services.intent_plan import IntentPlanCompiler
from app.services.runtime_run_lifecycle import RuntimeRunLifecycleService
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def plan() -> AgentRunPlan:
    return AgentRunPlan(
        plan_id="plan-runtime-test",
        goal="检索并审核证据",
        nodes=[
            RuntimeNode(
                node_id="retrieve",
                node_type="retrieval",
                handler_id="external.retrieval",
            ),
            RuntimeNode(
                node_id="review",
                node_type="agent",
                handler_id="paper.review",
                depends_on=["retrieve"],
            ),
        ],
    )


def test_runtime_plan_materializes_a_structured_goal_contract() -> None:
    runtime_plan = AgentRunPlan(
        plan_id="plan-goal-contract",
        goal="answer with evidence",
        success_criteria=["answer the question"],
        nodes=[
            RuntimeNode(
                node_id="answer",
                node_type="agent",
                handler_id="agent.answer",
            )
        ],
    )

    assert isinstance(runtime_plan.goal_contract, RuntimeGoal)
    assert runtime_plan.goal_contract.objective == "answer with evidence"
    assert runtime_plan.goal_contract.success_criteria == [
        "answer the question"
    ]

    run = AgentRun(
        run_id="run-goal-contract",
        task_id="task-goal-contract",
        goal=runtime_plan.goal,
        plan=runtime_plan,
    )
    assert run.goal_contract == runtime_plan.goal_contract


def test_plan_rejects_dependency_cycle() -> None:
    with pytest.raises(ValueError, match="dependency cycle"):
        AgentRunPlan(
            plan_id="cycle",
            goal="invalid",
            nodes=[
                RuntimeNode(
                    node_id="a", node_type="agent", handler_id="a", depends_on=["b"]
                ),
                RuntimeNode(
                    node_id="b", node_type="agent", handler_id="b", depends_on=["a"]
                ),
            ],
        )


def test_state_machine_advances_dependencies_and_completes_run() -> None:
    run = AgentRun(run_id="run-1", task_id="task-1", goal="goal", plan=plan())
    assert RuntimeStateMachine.ready_nodes(run) == ["retrieve"]
    RuntimeStateMachine.mark_ready(run)
    assert run.nodes["retrieve"].status == RuntimeNodeStatus.READY
    RuntimeStateMachine.start_node(run, "retrieve")
    RuntimeStateMachine.complete_node(
        run,
        "retrieve",
        status=RuntimeNodeStatus.SUCCEEDED,
        observation=RuntimeObservation(
            node_id="retrieve", artifact_ids=["evidence-1"]
        ),
    )
    RuntimeStateMachine.mark_ready(run)
    assert run.nodes["review"].status == RuntimeNodeStatus.READY
    RuntimeStateMachine.start_node(run, "review")
    RuntimeStateMachine.complete_node(run, "review", status=RuntimeNodeStatus.SUCCEEDED)
    assert run.status == RuntimeRunStatus.COMPLETED


def test_decision_can_pause_for_input_or_approval() -> None:
    run = AgentRun(run_id="run-2", task_id="task-2", goal="goal", plan=plan())
    RuntimeStateMachine.apply_decision(
        run,
        RuntimeDecision(
            action=DecisionAction.ASK_USER,
            user_prompt="请补充检索时间范围",
        ),
    )
    assert run.status == RuntimeRunStatus.WAITING_INPUT
    RuntimeStateMachine.apply_decision(
        run,
        RuntimeDecision(
            action=DecisionAction.REQUEST_APPROVAL,
            approval_scope="允许使用外部检索",
        ),
    )
    assert run.status == RuntimeRunStatus.WAITING_APPROVAL

    RuntimeStateMachine.apply_decision(
        run,
        RuntimeDecision(
            action=DecisionAction.PAUSE,
            reason_codes=["user_requested_pause"],
        ),
    )
    assert run.status == RuntimeRunStatus.PAUSED


def test_plan_executor_runs_dependencies_and_retries_failed_node() -> None:
    run_plan = AgentRunPlan(
        plan_id="plan-executor-test",
        goal="执行并重试",
        max_parallelism=2,
        nodes=[
            RuntimeNode(
                node_id="first",
                node_type="tool",
                handler_id="first.handler",
            ),
            RuntimeNode(
                node_id="second",
                node_type="tool",
                handler_id="second.handler",
                depends_on=["first"],
                max_retries=1,
            ),
        ],
    )
    run = AgentRun(
        run_id="run-executor",
        task_id="task-executor",
        goal="执行并重试",
        plan=run_plan,
    )
    calls: list[str] = []

    def first_handler(_run: AgentRun, _node: RuntimeNode) -> RuntimeObservation:
        calls.append("first")
        return RuntimeObservation(node_id="first", facts={"ok": True})

    attempts = 0

    def second_handler(_run: AgentRun, _node: RuntimeNode) -> RuntimeObservation:
        nonlocal attempts
        attempts += 1
        calls.append(f"second-{attempts}")
        if attempts == 1:
            raise RuntimeNodeError("temporary_failure")
        return RuntimeObservation(node_id="second", facts={"ok": True})

    asyncio.run(
        PlanExecutor(
            {"first.handler": first_handler, "second.handler": second_handler}
        ).execute(run)
    )
    assert calls == ["first", "second-1", "second-2"]
    assert run.status == RuntimeRunStatus.COMPLETED


def test_plan_executor_enforces_call_budget_before_handler_invocation() -> None:
    run_plan = AgentRunPlan(
        plan_id="plan-budget-test",
        goal="验证预算",
        nodes=[
            RuntimeNode(
                node_id="tool",
                node_type="tool",
                handler_id="tool.handler",
            )
        ],
    )
    run = AgentRun(
        run_id="run-budget",
        task_id="task-budget",
        goal="验证预算",
        plan=run_plan,
        budget=RuntimeBudget(max_tool_calls=0),
    )
    calls: list[str] = []

    def handler(_run: AgentRun, _node: RuntimeNode) -> RuntimeObservation:
        calls.append("called")
        return RuntimeObservation(node_id="tool")

    asyncio.run(PlanExecutor({"tool.handler": handler}).execute(run))
    assert calls == []
    assert run.budget.tool_calls == 0
    assert run.nodes["tool"].error_code == "tool_call_budget_exceeded"
    assert run.status == RuntimeRunStatus.FAILED


def test_runtime_handler_registry_enforces_registration_policy() -> None:
    registry = RuntimeHandlerRegistry()
    registry.register(
        RuntimeHandlerDescriptor(
            handler_id="bounded.handler",
            kind="tool",
            max_timeout_ms=100,
        ),
        lambda _run, _node: RuntimeObservation(node_id="bounded"),
    )
    run = AgentRun(
        run_id="run-handler-policy",
        task_id="task-handler-policy",
        goal="验证 handler registry",
        plan=AgentRunPlan(
            plan_id="plan-handler-policy",
            goal="验证 handler registry",
            nodes=[
                RuntimeNode(
                    node_id="bounded",
                    node_type="tool",
                    handler_id="bounded.handler",
                    timeout_ms=200,
                )
            ],
        ),
    )
    asyncio.run(PlanExecutor(registry).execute(run))
    assert run.nodes["bounded"].error_code == "handler_timeout_policy_exceeded"
    assert run.status == RuntimeRunStatus.FAILED


def test_runtime_handler_requires_approval_before_invocation() -> None:
    registry = RuntimeHandlerRegistry()
    calls: list[str] = []

    def handler(_run: AgentRun, _node: RuntimeNode) -> RuntimeObservation:
        calls.append("called")
        return RuntimeObservation(node_id="approved")

    registry.register(
        RuntimeHandlerDescriptor(
            handler_id="approved.handler",
            kind="provider",
            requires_approval=True,
        ),
        handler,
    )
    run = AgentRun(
        run_id="run-approval",
        task_id="task-approval",
        goal="approval",
        plan=AgentRunPlan(
            plan_id="plan-approval",
            goal="approval",
            nodes=[
                RuntimeNode(
                    node_id="approved",
                    node_type="provider",
                    handler_id="approved.handler",
                )
            ],
        ),
    )

    asyncio.run(PlanExecutor(registry).execute(run))
    assert calls == []
    assert run.status == RuntimeRunStatus.WAITING_APPROVAL
    assert run.nodes["approved"].status == RuntimeNodeStatus.READY

    run.control_data = {"approved": True}
    asyncio.run(PlanExecutor(registry).execute(run))
    assert calls == ["called"]
    assert run.status == RuntimeRunStatus.COMPLETED


def test_runtime_recovery_does_not_repeat_non_replay_safe_side_effect() -> None:
    registry = RuntimeHandlerRegistry()
    calls: list[str] = []

    def handler(_run: AgentRun, _node: RuntimeNode) -> RuntimeObservation:
        calls.append("called")
        return RuntimeObservation(node_id="effect")

    registry.register(
        RuntimeHandlerDescriptor(
            handler_id="effect.handler",
            kind="tool",
            side_effecting=True,
            replay_safe=False,
        ),
        handler,
    )
    run = AgentRun(
        run_id="run-effect-recovery",
        task_id="task-effect-recovery",
        goal="effect recovery",
        plan=AgentRunPlan(
            plan_id="plan-effect-recovery",
            goal="effect recovery",
            nodes=[
                RuntimeNode(
                    node_id="effect",
                    node_type="tool",
                    handler_id="effect.handler",
                )
            ],
        ),
    )
    RuntimeStateMachine.mark_ready(run)
    RuntimeStateMachine.start_node(run, "effect")
    execution_key = run.nodes["effect"].execution_key

    asyncio.run(PlanExecutor(registry).execute(run))

    assert calls == []
    assert run.status == RuntimeRunStatus.PAUSED
    assert run.nodes["effect"].execution_key == execution_key
    assert run.nodes["effect"].effect_status == RuntimeEffectStatus.UNKNOWN
    assert (
        run.nodes["effect"].error_code
        == "in_flight_execution_requires_reconciliation"
    )


def test_runtime_recovery_replays_safe_handler_with_stable_execution_key() -> None:
    registry = RuntimeHandlerRegistry()
    keys: list[str] = []

    def handler(run: AgentRun, node: RuntimeNode) -> RuntimeObservation:
        keys.append(run.nodes[node.node_id].execution_key)
        return RuntimeObservation(node_id=node.node_id)

    registry.register(
        RuntimeHandlerDescriptor(
            handler_id="safe.handler",
            kind="tool",
            replay_safe=True,
        ),
        handler,
    )
    run = AgentRun(
        run_id="run-safe-recovery",
        task_id="task-safe-recovery",
        goal="safe recovery",
        plan=AgentRunPlan(
            plan_id="plan-safe-recovery",
            goal="safe recovery",
            nodes=[
                RuntimeNode(
                    node_id="safe",
                    node_type="tool",
                    handler_id="safe.handler",
                )
            ],
        ),
    )
    RuntimeStateMachine.mark_ready(run)
    RuntimeStateMachine.start_node(run, "safe")
    execution_key = run.nodes["safe"].execution_key

    asyncio.run(PlanExecutor(registry).execute(run))

    assert keys == [execution_key]
    assert run.status == RuntimeRunStatus.COMPLETED
    assert run.nodes["safe"].effect_status == RuntimeEffectStatus.COMPLETED


def test_plan_executor_blocks_dependents_after_terminal_failure() -> None:
    run_plan = AgentRunPlan(
        plan_id="plan-blocking-test",
        goal="验证失败传播",
        nodes=[
            RuntimeNode(
                node_id="first",
                node_type="tool",
                handler_id="first.handler",
            ),
            RuntimeNode(
                node_id="second",
                node_type="tool",
                handler_id="second.handler",
                depends_on=["first"],
            ),
        ],
    )
    run = AgentRun(
        run_id="run-blocking",
        task_id="task-blocking",
        goal="验证失败传播",
        plan=run_plan,
    )

    def failing_handler(_run: AgentRun, _node: RuntimeNode) -> RuntimeObservation:
        raise RuntimeNodeError("upstream_failure")

    asyncio.run(PlanExecutor({"first.handler": failing_handler}).execute(run))
    assert run.nodes["first"].status == RuntimeNodeStatus.FAILED
    assert run.nodes["second"].status == RuntimeNodeStatus.BLOCKED
    assert run.status == RuntimeRunStatus.FAILED


def test_runtime_event_bridge_preserves_task_event_contract() -> None:
    run = AgentRun(
        run_id="run-events",
        task_id="task-events",
        goal="goal",
        plan=plan(),
    )
    event_type, data = to_task_event("node_started", run, "retrieve")
    assert event_type.value == "plan.node_started"
    assert data["runtime_run_id"] == "run-events"
    assert data["handler_id"] == "external.retrieval"


def test_runtime_controller_executes_selected_nodes_and_verifies() -> None:
    run = AgentRun(
        run_id="run-controller",
        task_id="task-controller",
        goal="goal",
        plan=plan(),
    )
    decisions = iter(
        [
            RuntimeDecision(
                action=DecisionAction.EXECUTE,
                node_ids=["retrieve"],
            ),
            RuntimeDecision(
                action=DecisionAction.EXECUTE,
                node_ids=["review"],
            ),
        ]
    )
    verified: list[str] = []

    def decide(_run: AgentRun) -> RuntimeDecision:
        return next(decisions)

    def verify(current: AgentRun) -> RuntimeObservation:
        verified.append(current.nodes["retrieve"].status.value)
        return RuntimeObservation(
            node_id="verification",
            facts={"retrieval_status": current.nodes["retrieve"].status.value},
        )

    def retrieve(_run: AgentRun, _node: RuntimeNode) -> RuntimeObservation:
        return RuntimeObservation(node_id="retrieve", facts={"count": 1})

    def review(_run: AgentRun, _node: RuntimeNode) -> RuntimeObservation:
        return RuntimeObservation(node_id="review", facts={"approved": True})

    asyncio.run(
        RuntimeController(
            PlanExecutor(
                {
                    "external.retrieval": retrieve,
                    "paper.review": review,
                }
            ),
            decide,
            verifier=verify,
        ).run(run)
    )
    assert run.status == RuntimeRunStatus.COMPLETED
    assert verified == ["pending", "succeeded"]
    assert run.nodes["review"].status == RuntimeNodeStatus.SUCCEEDED


def test_runtime_controller_replans_and_can_pause_for_input() -> None:
    initial_plan = AgentRunPlan(
        plan_id="plan-initial",
        goal="goal",
        nodes=[RuntimeNode(node_id="old", node_type="tool", handler_id="old")],
    )
    replacement_plan = AgentRunPlan(
        plan_id="plan-replanned",
        version="2",
        goal="goal",
        nodes=[RuntimeNode(node_id="new", node_type="tool", handler_id="new")],
    )
    run = AgentRun(
        run_id="run-replan",
        task_id="task-replan",
        goal="goal",
        plan=initial_plan,
    )
    decisions = iter(
        [
            RuntimeDecision(
                action=DecisionAction.REPLAN,
                reason_codes=["insufficient_evidence"],
            ),
            RuntimeDecision(action=DecisionAction.EXECUTE, node_ids=["new"]),
        ]
    )

    def new_handler(_run: AgentRun, _node: RuntimeNode) -> RuntimeObservation:
        return RuntimeObservation(node_id="new", facts={"ok": True})

    asyncio.run(
        RuntimeController(
            PlanExecutor({"new": new_handler}),
            lambda _run: next(decisions),
            replan_provider=lambda _run, _decision: replacement_plan,
        ).run(run)
    )
    assert run.iteration == 1
    assert run.plan.plan_id == "plan-replanned"
    assert run.status == RuntimeRunStatus.COMPLETED

    paused = AgentRun(
        run_id="run-paused",
        task_id="task-paused",
        goal="goal",
        plan=plan(),
    )
    asyncio.run(
        RuntimeController(
            PlanExecutor({}),
            lambda _run: RuntimeDecision(
                action=DecisionAction.ASK_USER,
                user_prompt="Please provide the missing scope.",
            ),
        ).run(paused)
    )
    assert paused.status == RuntimeRunStatus.WAITING_INPUT


    externally_paused = AgentRun(
        run_id="run-external-pause",
        task_id="task-external-pause",
        goal="goal",
        plan=plan(),
    )
    asyncio.run(
        RuntimeController(
            PlanExecutor({}),
            lambda _run: RuntimeDecision(
                action=DecisionAction.EXECUTE,
                node_ids=["retrieve"],
            ),
            control_provider=lambda _run: RuntimeDecision(
                action=DecisionAction.PAUSE,
                reason_codes=["pause_requested"],
            ),
        ).run(externally_paused)
    )
    assert externally_paused.status == RuntimeRunStatus.PAUSED


def test_plan_executor_emits_ordered_events_and_enforces_timeout() -> None:
    run_plan = AgentRunPlan(
        plan_id="plan-events-test",
        goal="验证事件与超时",
        nodes=[
            RuntimeNode(
                node_id="slow",
                node_type="tool",
                handler_id="slow.handler",
                timeout_ms=100,
            ),
        ],
    )
    run = AgentRun(
        run_id="run-events",
        task_id="task-events",
        goal="验证事件与超时",
        plan=run_plan,
    )
    events: list[str] = []

    async def slow_handler(
        _run: AgentRun, _node: RuntimeNode
    ) -> RuntimeObservation:
        await asyncio.sleep(0.2)
        return RuntimeObservation(node_id="slow")

    def record_event(event: str, _run: AgentRun, node_id: str) -> None:
        events.append(f"{event}:{node_id}")

    asyncio.run(
        PlanExecutor(
            {"slow.handler": slow_handler}, event_hook=record_event
        ).execute(run)
    )
    assert events == [
        "node_started:slow",
        "node_failed:slow",
    ]
    assert run.nodes["slow"].error_code == "TimeoutError"
    assert run.status == RuntimeRunStatus.FAILED


def test_intent_plan_adapter_creates_executable_runtime_handlers() -> None:
    from app.contracts import AgentRequest, Intent, RouteDecision, RouteStatus

    request = AgentRequest(
        session_id="session-runtime",
        user_id="user-runtime",
        course_id="UNKNOWN",
        intent=Intent.ACADEMIC_SEARCH,
        canonical_input={"text": "研究柔性电子"},
    )
    decision = RouteDecision(
        agent_id="RESEARCH_01_ACADEMIC_SEARCH_V1",
        scene="research",
        course_id="UNKNOWN",
        intent="academic_search",
        route_status=RouteStatus.SELECTED,
        reason="test",
        retrieval_required=True,
        provider_required=False,
    )
    legacy = IntentPlanCompiler().compile(request, decision)
    runtime = IntentPlanCompiler.to_runtime_plan(legacy)
    assert runtime.plan_id == legacy.plan_id
    assert runtime.nodes[0].handler_id == "workflow.external_retrieval"
    assert runtime.nodes[2].depends_on == ["research.review"]
    assert runtime.goal_contract is not None
    assert runtime.goal_contract.source == "intent_plan"
    assert "external_retrieval" in runtime.goal_contract.required_capabilities


def test_agent_run_repository_restores_latest_checkpoint(tmp_path) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'runtime.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            session.add(
                SessionModel(
                    id="session-persist",
                    user_id="user-persist",
                    course_id="CT",
                )
            )
            session.add(
                TaskModel(
                    id="task-persist",
                    session_id="session-persist",
                    user_id="user-persist",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="RUNTIME_TEST",
                    input_content={"text": "persist"},
                )
            )
            await session.commit()

            run = AgentRun(
                run_id="run-persist",
                task_id="task-persist",
                goal="persist runtime state",
                plan=plan(),
            )
            repository = AgentRunRepository(session)
            await repository.create(
                run,
                agent_id="RUNTIME_TEST",
                provider="mock",
            )
            RuntimeStateMachine.mark_ready(run)
            RuntimeStateMachine.start_node(run, "retrieve")
            RuntimeStateMachine.complete_node(
                run,
                "retrieve",
                status=RuntimeNodeStatus.SUCCEEDED,
                observation=RuntimeObservation(
                    node_id="retrieve", artifact_ids=["evidence-1"]
                ),
            )
            await repository.save_checkpoint(run)
            await session.commit()

            restored = await repository.restore("run-persist")
            assert restored is not None
            assert restored.state_version == 2
            assert restored.nodes["retrieve"].status == RuntimeNodeStatus.SUCCEEDED
            assert restored.nodes["retrieve"].observation is not None

        await engine.dispose()

    asyncio.run(scenario())


def test_agent_run_repository_correlates_checkpoints_to_task_events(tmp_path) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'runtime-event-correlation.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            session.add(
                SessionModel(
                    id="session-event-correlation",
                    user_id="user-event-correlation",
                    course_id="CT",
                )
            )
            session.add(
                TaskModel(
                    id="task-event-correlation",
                    session_id="session-event-correlation",
                    user_id="user-event-correlation",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="RUNTIME_TEST",
                    input_content={"text": "event correlation"},
                )
            )
            await session.commit()

            await append_task_event(
                session,
                "task-event-correlation",
                AgentEventType.TASK_CREATED,
                agent_id="RUNTIME_TEST",
            )
            run = AgentRun(
                run_id="run-event-correlation",
                task_id="task-event-correlation",
                goal="correlate runtime checkpoints",
                plan=AgentRunPlan(
                    plan_id="event-correlation-plan",
                    goal="correlate runtime checkpoints",
                    nodes=[
                        RuntimeNode(
                            node_id="observe",
                            node_type="tool",
                            handler_id="observe.handler",
                        )
                    ],
                ),
            )
            repository = AgentRunRepository(session)
            await repository.create(
                run,
                agent_id="RUNTIME_TEST",
                provider="mock",
            )
            checkpoints = await repository.list_checkpoints(run.run_id)
            assert checkpoints[0].event_sequence == 1

            await append_task_event(
                session,
                "task-event-correlation",
                AgentEventType.AGENT_PROGRESS,
                agent_id="RUNTIME_TEST",
                data={"runtime_event": "checkpoint_test"},
            )
            await repository.save_checkpoint(run)
            await session.commit()

            checkpoints = await repository.list_checkpoints(run.run_id)
            assert [item.event_sequence for item in checkpoints] == [1, 2]
            restored = await repository.restore(run.run_id)
            assert restored is not None
            assert restored.run_id == run.run_id
            restored_checkpoints = await repository.list_checkpoints(run.run_id)
            assert restored_checkpoints[-1].event_sequence == 2

        await engine.dispose()

    asyncio.run(scenario())


def test_agent_run_repository_persists_replanned_nodes(tmp_path) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'runtime-replan.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            session.add(
                SessionModel(
                    id="session-replan-persist",
                    user_id="user-replan-persist",
                    course_id="CT",
                )
            )
            session.add(
                TaskModel(
                    id="task-replan-persist",
                    session_id="session-replan-persist",
                    user_id="user-replan-persist",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="RUNTIME_TEST",
                    input_content={"text": "replan"},
                )
            )
            await session.commit()

            run = AgentRun(
                run_id="run-replan-persist",
                task_id="task-replan-persist",
                goal="persist a new plan",
                plan=plan(),
            )
            repository = AgentRunRepository(session)
            await repository.create(
                run,
                agent_id="RUNTIME_TEST",
                provider="mock",
            )
            replacement = AgentRunPlan(
                plan_id="plan-runtime-replanned",
                version="2",
                goal=run.goal,
                nodes=[
                    RuntimeNode(
                        node_id="observe.replan.1",
                        node_type="verification",
                        handler_id="observe.handler",
                    ),
                    RuntimeNode(
                        node_id="act.replan.1",
                        node_type="subagent",
                        handler_id="subagent.handler",
                        depends_on=["observe.replan.1"],
                    ),
                ],
            )
            RuntimeStateMachine.replace_plan(run, replacement)
            await repository.save_checkpoint(run)
            await session.commit()

            restored = await repository.restore(run.run_id)
            assert restored is not None
            assert restored.plan.plan_id == "plan-runtime-replanned"
            assert set(restored.nodes) == {
                "observe.replan.1",
                "act.replan.1",
            }

        await engine.dispose()

    asyncio.run(scenario())


def test_runtime_lifecycle_wraps_legacy_task_without_duplicate_execution(
    tmp_path,
) -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'lifecycle.db'}"
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            session.add(
                SessionModel(
                    id="session-lifecycle",
                    user_id="user-lifecycle",
                    course_id="CT",
                )
            )
            session.add(
                TaskModel(
                    id="task-lifecycle",
                    session_id="session-lifecycle",
                    user_id="user-lifecycle",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="RUNTIME_TEST",
                    input_content={"text": "lifecycle"},
                )
            )
            await session.flush()
            lifecycle = RuntimeRunLifecycleService(enabled=True)
            run = await lifecycle.start(
                session,
                task_id="task-lifecycle",
                agent_id="RUNTIME_TEST",
                provider="mock",
                goal="run legacy workflow",
                request_snapshot={
                    "task_id": "task-lifecycle",
                    "canonical_input": {"text": "persisted runtime request"},
                    "options": {"route_revision": 2},
                },
            )
            assert run is not None
            assert run.nodes["legacy.execution"].status == RuntimeNodeStatus.RUNNING
            assert run.request_snapshot["canonical_input"] == {
                "text": "persisted runtime request"
            }
            repository = AgentRunRepository(session)
            await repository.request_control(
                run.run_id,
                "pause",
                control_data={"requested_by": "test"},
            )
            controlled = await repository.get(run.run_id)
            assert controlled is not None
            assert controlled.control_request == "pause"
            assert controlled.control_data == {"requested_by": "test"}
            await repository.clear_control(run.run_id)
            await lifecycle.finalize(
                session,
                task_id="task-lifecycle",
                status=RuntimeRunStatus.COMPLETED,
                provider="mock",
                artifact_ids=["artifact-1"],
                run=run,
            )
            await session.commit()

            restored = await AgentRunRepository(session).restore(run.run_id)
            assert restored is not None
            assert restored.request_snapshot["options"] == {"route_revision": 2}
            assert restored.status == RuntimeRunStatus.COMPLETED
            observation = restored.nodes["legacy.execution"].observation
            assert observation is not None
            assert observation.artifact_ids == ["artifact-1"]

        await engine.dispose()

    asyncio.run(scenario())
