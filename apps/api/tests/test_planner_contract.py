from app.contracts import AgentRequest, Intent, RouteDecision, RouteStatus
from app.core.config import Settings
from app.runtime import RuntimeGoal
from app.services.canonical_plan_adapter import CanonicalPlanAdapter
from app.services.intent_plan import IntentPlanCompiler
from app.services.planner import PlannerService


def _request() -> AgentRequest:
    return AgentRequest(
        task_id="task-planner-contract",
        session_id="session-planner-contract",
        user_id="user-planner-contract",
        intent=Intent.EXPLAIN_CONCEPT,
        course_id="DSP",
        canonical_input={"text": "解释采样定理"},
        options={
            "request_id": "request-planner-contract",
            "trace_id": "trace-planner-contract",
        },
    )


def _route() -> RouteDecision:
    return RouteDecision(
        agent_id="LEARN_01_KNOWLEDGE_QA_V1",
        scene="learning",
        course_id="DSP",
        intent=Intent.EXPLAIN_CONCEPT.value,
        route_status=RouteStatus.SELECTED,
        reason="contract fixture",
        retrieval_required=True,
        provider_required=False,
        route_confidence=0.91,
        route_revision=3,
        capabilities=["knowledge.answer"],
        selected_skills=["knowledge-grounding"],
        selected_tools=["retrieval.local"],
    )


def test_planner_snapshot_and_canonical_plan_are_serializable() -> None:
    request = _request()
    route = _route()
    compiler = IntentPlanCompiler()
    intent_plan = compiler.compile(request, route)
    output = PlannerService(compiler).build(
        request,
        route,
        settings=Settings(planner_shadow_enabled=True),
        intent_plan=intent_plan,
    )

    restored = type(output.snapshot).model_validate(output.snapshot.model_dump())

    assert restored == output.snapshot
    assert restored.mode == "shadow"
    assert restored.route_match is True
    assert restored.plan_match is True
    assert restored.lineage.context_snapshot_id
    assert restored.lineage.registry_snapshot_id
    assert restored.model_calls == 0


def test_canonical_adapter_closes_intent_and_runtime_plan_boundary() -> None:
    request = _request()
    route = _route()
    intent_plan = IntentPlanCompiler().compile(request, route)
    canonical = CanonicalPlanAdapter.from_intent_plan(intent_plan, route)

    restored_intent = CanonicalPlanAdapter.to_intent_plan(canonical)
    runtime_plan = CanonicalPlanAdapter.to_runtime_plan(canonical)
    restored_canonical = CanonicalPlanAdapter.from_agent_run_plan(runtime_plan)

    assert restored_intent.goal == intent_plan.goal
    assert [node.node_id for node in restored_intent.nodes] == [
        node.node_id for node in intent_plan.nodes
    ]
    assert runtime_plan.goal_contract is not None
    assert runtime_plan.goal_contract.source == "canonical_plan"
    assert [node.node_id for node in restored_canonical.nodes] == [
        node.node_id for node in canonical.nodes
    ]


def test_runtime_goal_adapter_preserves_parallel_phases() -> None:
    canonical = CanonicalPlanAdapter.from_runtime_goal(
        RuntimeGoal(
            objective="parallel goal",
            required_capabilities=["retrieve", "classify", "compose"],
            parallel_groups=[["retrieve", "classify"], ["compose"]],
        ),
        plan_id="canonical-parallel-goal",
    )

    retrieve, classify, compose = canonical.nodes
    assert retrieve.parallel_group == "goal.phase.1"
    assert classify.parallel_group == "goal.phase.1"
    assert retrieve.depends_on == []
    assert classify.depends_on == []
    assert compose.depends_on == [retrieve.node_id, classify.node_id]
    assert canonical.budget.max_parallelism == 2


def test_takeover_requires_explicit_flag_and_allowlist() -> None:
    request = _request().model_copy(
        update={"options": {"_routing": {"agent_id": _route().agent_id}}}
    )

    assert PlannerService.takeover_allowed(request, Settings()) is False
    assert (
        PlannerService.takeover_allowed(
            request,
            Settings(
                planner_takeover_enabled=True,
                planner_canary_agent_ids=_route().agent_id,
            ),
        )
        is True
    )
