from __future__ import annotations

from dataclasses import dataclass

from app.agents.registry import AgentRegistry
from app.contracts import AgentRequest, InputMode, RouteDecision, RouteStatus


@dataclass(frozen=True, slots=True)
class SessionRouteContext:
    course_id: str = ""
    intent: str = ""
    target_agent_id: str = ""


class TaskRouter:
    """Deterministic local-first router; it never calls a model."""

    def __init__(self, registry: AgentRegistry, threshold: float = 0.75) -> None:
        self.registry = registry
        self.threshold = threshold

    def route(
        self,
        request: AgentRequest,
        input_mode: InputMode,
        context: SessionRouteContext | None = None,
    ) -> RouteDecision:
        course_id = request.course_id.strip().upper() or "UNKNOWN"
        intent = request.intent.value
        route = self._local_route(course_id, intent, input_mode, context)
        if route is not None and route.route_confidence >= self.threshold:
            return route
        if course_id not in {"CT", "AE", "DE", "UNKNOWN"}:
            return RouteDecision(
                route_status=RouteStatus.UNSUPPORTED,
                course_id=course_id,
                intent=intent,
                target_agent_id="",
                route_confidence=1.0,
                route_source="local_fast",
                reason="当前版本仅支持电子信息课程群中的 CT、AE 和 DE。",
                input_mode=input_mode,
            )
        return RouteDecision(
            route_status=RouteStatus.SELECTED,
            course_id=course_id,
            intent=intent,
            target_agent_id="ROUTER_01_FALLBACK_V1",
            route_confidence=0.5,
            route_source="cloud_fallback",
            reason="本地规则无法以足够置信度确定唯一目标 Agent。",
            input_mode=input_mode,
            needs_fallback=True,
        )

    @staticmethod
    def _local_route(
        course_id: str,
        intent: str,
        input_mode: InputMode,
        context: SessionRouteContext | None,
    ) -> RouteDecision | None:
        if (
            course_id == "CT"
            and intent in {"solve_problem", "check_user_solution", "verify_answer"}
        ):
            return TaskRouter._selected(
                course_id, intent, "SOLVER_CT_V1", input_mode, False
            )
        if (
            course_id in {"CT", "AE", "DE"}
            and intent
            in {
                "explain_concept",
                "summarize_knowledge",
                "learning_advice",
                "general_qa",
            }
            and input_mode == InputMode.TEXT
        ):
            return TaskRouter._selected(
                course_id,
                intent,
                "LEARN_01_KNOWLEDGE_QA_V1",
                input_mode,
                True,
            )
        if intent == "follow_up_question" and context and context.target_agent_id:
            target = context.target_agent_id
            if target in AgentRegistry.ROUTING_TARGETS:
                return TaskRouter._selected(
                    context.course_id or course_id,
                    intent,
                    target,
                    input_mode,
                    target == "LEARN_01_KNOWLEDGE_QA_V1",
                    reason="沿用同一会话最近一次已完成任务的课程与 Agent。",
                )
        return None

    @staticmethod
    def _selected(
        course_id: str,
        intent: str,
        target_agent_id: str,
        input_mode: InputMode,
        needs_knowledge: bool,
        reason: str = "命中本地确定性课程与意图规则。",
    ) -> RouteDecision:
        return RouteDecision(
            route_status=RouteStatus.SELECTED,
            course_id=course_id,
            intent=intent,
            target_agent_id=target_agent_id,
            route_confidence=0.95,
            route_source="local_fast",
            reason=reason,
            input_mode=input_mode,
            needs_knowledge=needs_knowledge,
        )
