from __future__ import annotations

from typing import cast
from uuid import uuid4

from app.contracts import AgentRequest, RouteDecision
from app.contracts.intent import IntentExecutionPlan, IntentRouteMode, PlanNode
from app.runtime import AgentRunPlan, RuntimeGoal, RuntimeNode


class IntentPlanCompiler:
    """Compile a route into a bounded, inspectable execution plan."""

    def compile(
        self, request: AgentRequest, decision: RouteDecision
    ) -> IntentExecutionPlan:
        recognition = decision.intent_recognition
        intent = str(recognition.get("intent") or decision.intent)
        capabilities = list(recognition.get("capabilities") or decision.capabilities)
        tools = list(recognition.get("selected_tools") or decision.selected_tools)
        skills = list(recognition.get("selected_skills") or decision.selected_skills)
        mode = str(
            recognition.get("route_mode") or decision.route_mode or "single_agent"
        )
        nodes: list[PlanNode] = []

        if intent == "academic_search":
            nodes = [
                PlanNode(
                    node_id="research.retrieve",
                    node_type="retrieval",
                    target_id="external_retrieval",
                    parallel_group="research_sources",
                    timeout_ms=60000,
                ),
                PlanNode(
                    node_id="research.review",
                    node_type="agent",
                    target_id="ACADEMIC_PAPER_REVIEW_LOCAL_V1",
                    depends_on=["research.retrieve"],
                    timeout_ms=30000,
                ),
                PlanNode(
                    node_id="research.compose",
                    node_type="agent",
                    target_id="RESEARCH_FRONTIER_BRIEF_LOCAL_V1",
                    depends_on=["research.review"],
                    timeout_ms=60000,
                ),
            ]
            success = [
                "answer the user question",
                "use reviewed evidence when available",
            ]
            max_parallelism = 4
        elif decision.agent_id:
            nodes = [
                PlanNode(
                    node_id="primary.agent",
                    node_type="agent",
                    target_id=decision.agent_id,
                    timeout_ms=60000,
                )
            ]
            success = ["produce a structured answer"]
            max_parallelism = 1
        else:
            success = ["return a safe local fallback"]
            max_parallelism = 1

        safe_mode = cast(
            IntentRouteMode,
            mode
            if mode in {"fast", "single_agent", "workflow", "clarify"}
            else "single_agent",
        )
        return IntentExecutionPlan(
            plan_id=f"plan_{uuid4().hex}",
            mode=safe_mode,
            goal=str(
                request.canonical_input.get("text")
                or request.canonical_input.get("question")
                or ""
            ),
            nodes=nodes,
            capabilities=capabilities,
            selected_tools=tools,
            selected_skills=skills,
            success_criteria=success,
            fallback_targets=[decision.fallback_instruction]
            if decision.fallback_instruction
            else [],
            max_parallelism=max_parallelism,
            confidence=decision.route_confidence,
        )

    @staticmethod
    def to_runtime_plan(
        plan: IntentExecutionPlan, *, handler_prefix: str = "workflow"
    ) -> AgentRunPlan:
        """Convert the legacy plan contract into executable Runtime nodes.

        The adapter does not execute anything or alter the legacy request
        shape. It gives the migration layer one canonical mapping from the
        existing plan vocabulary to registered Runtime handlers.
        """

        return AgentRunPlan(
            plan_id=plan.plan_id,
            version=plan.version,
            goal=plan.goal or "runtime task",
            goal_contract=RuntimeGoal(
                objective=plan.goal or "runtime task",
                success_criteria=list(plan.success_criteria),
                constraints={
                    "route_mode": plan.mode,
                    "fallback_targets": list(plan.fallback_targets),
                },
                required_capabilities=[
                    *plan.capabilities,
                    *plan.selected_tools,
                    *plan.selected_skills,
                    *[
                        node.target_id
                        for node in plan.nodes
                        if node.target_id
                    ],
                ],
                context={"confidence": plan.confidence},
                source="intent_plan",
            ),
            nodes=[
                RuntimeNode(
                    node_id=node.node_id,
                    node_type=node.node_type,
                    handler_id=f"{handler_prefix}.{node.target_id}",
                    depends_on=list(node.depends_on),
                    parallel_group=node.parallel_group,
                    timeout_ms=node.timeout_ms,
                    max_retries=node.max_retries,
                    optional=node.optional,
                )
                for node in plan.nodes
            ],
            success_criteria=list(plan.success_criteria),
            max_parallelism=plan.max_parallelism,
        )
