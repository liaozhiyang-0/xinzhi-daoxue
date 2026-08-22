from app.contracts import AgentRequest, AgentResult, Intent, RouteDecision, RouteStatus
from app.contracts.intent import IntentExecutionPlan, PlanNode
from app.runtime import AgentRunPlan, RuntimeGoal, RuntimeNode


def test_phase_b_legacy_contracts_round_trip_without_planner() -> None:
    request = AgentRequest(
        task_id="task-phase-b-baseline",
        session_id="session-phase-b-baseline",
        user_id="user-phase-b-baseline",
        intent=Intent.EXPLAIN_CONCEPT,
        canonical_input={"text": "解释采样定理"},
    )
    route = RouteDecision(
        agent_id="LEARN_01_KNOWLEDGE_QA_V1",
        scene="learning",
        course_id="DSP",
        intent=Intent.EXPLAIN_CONCEPT.value,
        route_status=RouteStatus.SELECTED,
        reason="baseline",
        retrieval_required=True,
        provider_required=False,
        route_revision=1,
        route_trace=[{"stage": "local_route", "agent_id": "LEARN_01_KNOWLEDGE_QA_V1"}],
    )
    intent_plan = IntentExecutionPlan(
        plan_id="plan-phase-b-baseline",
        goal=request.input_text(),
        nodes=[
            PlanNode(
                node_id="primary.agent",
                node_type="agent",
                target_id=route.agent_id,
            )
        ],
        success_criteria=["produce a structured answer"],
    )
    runtime_plan = AgentRunPlan(
        plan_id="run-plan-phase-b-baseline",
        goal=intent_plan.goal,
        goal_contract=RuntimeGoal(
            objective=intent_plan.goal,
            required_capabilities=["knowledge.answer"],
        ),
        nodes=[
            RuntimeNode(
                node_id="knowledge.answer",
                node_type="agent",
                handler_id="agent.LEARN_01_KNOWLEDGE_QA_V1",
            )
        ],
    )
    result = AgentResult(
        agent_id=route.agent_id,
        provider="local",
        answer="baseline",
        task_id=request.task_id,
        trace_id="trace-phase-b-baseline",
    )

    assert AgentRequest.model_validate(request.model_dump()) == request
    assert RouteDecision.model_validate(route.model_dump()) == route
    assert IntentExecutionPlan.model_validate(intent_plan.model_dump()) == intent_plan
    assert AgentRunPlan.model_validate(runtime_plan.model_dump()) == runtime_plan
    assert AgentResult.model_validate(result.model_dump()) == result
