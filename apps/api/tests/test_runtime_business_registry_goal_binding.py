from __future__ import annotations

from app.contracts import AgentRequest
from app.runtime import AgentRunPlan, RuntimeNode
from app.services.runtime_business_registry import RuntimeBusinessRegistry


class _Service:
    agent_id = "GENERAL_QUESTION_V1"
    runtime_option_key = "general_question_runtime"

    def supports(self, agent_id: str, request: AgentRequest) -> bool:
        return agent_id == self.agent_id

    def build_plan(self, request: AgentRequest) -> AgentRunPlan:
        return AgentRunPlan(
            plan_id="goal-binding-test",
            goal="answer the question",
            nodes=[
                RuntimeNode(
                    node_id="observe",
                    node_type="verification",
                    handler_id="general.question.observe",
                )
            ],
        )


def test_registry_binds_bounded_route_context_and_node_capability() -> None:
    request = AgentRequest(
        session_id="session",
        user_id="user",
        options={
            "_routing": {
                "intent": "general_qa",
                "route_mode": "single_agent",
                "route_source": "local_fast",
                "task_subtype": "question",
                "complexity": "medium",
                "route_confidence": 0.92,
                "secret": "must-not-be-copied",
            }
        },
    )

    plan = RuntimeBusinessRegistry([_Service()]).build_plan(
        "GENERAL_QUESTION_V1", request
    )

    assert plan is not None
    assert plan.goal_contract is not None
    assert plan.goal_contract.required_capabilities == [
        "general.question.observe"
    ]
    assert plan.goal_contract.context == {
        "agent_id": "GENERAL_QUESTION_V1",
        "intent": "general_qa",
        "route_mode": "single_agent",
        "route_source": "local_fast",
        "task_subtype": "question",
        "complexity": "medium",
        "route_confidence": 0.92,
    }
    assert "secret" not in plan.goal_contract.context


def test_registry_preserves_explicit_goal_capabilities_and_context() -> None:
    class _ExplicitService(_Service):
        def build_plan(self, request: AgentRequest) -> AgentRunPlan:
            return AgentRunPlan(
                plan_id="explicit-goal-test",
                goal="answer the question",
                goal_contract={
                    "objective": "answer the question",
                    "required_capabilities": ["approved.capability"],
                    "context": {"review_id": "review-1"},
                    "source": "intent_plan",
                },
                nodes=[
                    RuntimeNode(
                        node_id="observe",
                        node_type="verification",
                        handler_id="general.question.observe",
                    )
                ],
            )

    request = AgentRequest(session_id="session", user_id="user")
    plan = RuntimeBusinessRegistry([_ExplicitService()]).build_plan(
        "GENERAL_QUESTION_V1", request
    )

    assert plan is not None
    assert plan.goal_contract is not None
    assert plan.goal_contract.required_capabilities == ["approved.capability"]
    assert plan.goal_contract.context == {
        "review_id": "review-1",
        "agent_id": "GENERAL_QUESTION_V1",
    }
    assert plan.goal_contract.source == "intent_plan"
