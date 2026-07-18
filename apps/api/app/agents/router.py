from __future__ import annotations

import json

from app.agents.registry import AgentDefinition, AgentRegistry, RoutingRule
from app.contracts.agent import AgentRequest
from app.contracts.routing import RouteDecision, RouteStatus
from app.core.config import Settings
from app.core.errors import AgentInputNotSupportedError, RouteInvalidTargetError


class TaskRouter:
    """Fast deterministic routes with bounded, validated cloud fallback hooks."""

    def __init__(
        self, registry: AgentRegistry, settings: Settings | None = None
    ) -> None:
        self.registry = registry
        self.settings = settings or Settings()

    def route(self, request: AgentRequest) -> RouteDecision:
        intent = request.intent.value
        course_id = request.course_id.upper()
        input_type = self._input_type(request)
        confidence = request.options.get("route_confidence", 1.0)
        use_fast_route = not (
            intent == "unknown"
            or (
                isinstance(confidence, (int, float))
                and not isinstance(confidence, bool)
                and confidence < 0.75
            )
        )
        if use_fast_route:
            for rule in self.registry.routing_rules:
                if course_id in rule.course_ids and intent in rule.intents:
                    decision = self._decision_for_rule(rule, request)
                    if decision.route_status == RouteStatus.SELECTED:
                        self._ensure_supported(decision.agent_id, input_type)
                    return decision

        cloud_router = self.registry.get("ROUTER_01_FALLBACK_V1")
        if self.registry.is_runtime_available(cloud_router.agent_id, self.settings):
            return RouteDecision(
                agent_id=cloud_router.agent_id,
                scene=cloud_router.scene,
                course_id=course_id,
                intent=intent,
                route_status=RouteStatus.SELECTED,
                reason="no deterministic match; selected one-pass cloud router",
                retrieval_required=False,
                provider_required=True,
                route_source="cloud_fallback",
                route_confidence=0.5,
            )
        return RouteDecision(
            agent_id="UNRESOLVED",
            scene=request.scene.value,
            course_id=course_id,
            intent=intent,
            route_status=RouteStatus.UNRESOLVED,
            reason=f"no configured route for course_id={course_id}, intent={intent}",
            retrieval_required=False,
            provider_required=False,
            route_source="local_degraded",
            route_confidence=0.0,
        )

    @staticmethod
    def _input_type(request: AgentRequest) -> str:
        has_text = any(
            isinstance(request.canonical_input.get(key), str)
            and bool(request.canonical_input[key].strip())
            for key in ("text", "question", "problem", "query", "prompt")
        )
        if len(request.attachments) > 1:
            raise AgentInputNotSupportedError("任务输入仅支持单张图片")
        if request.attachments and request.attachments[0].content_type not in {
            "image/png",
            "image/jpeg",
        }:
            raise AgentInputNotSupportedError("任务输入不支持 PDF 或非图片附件")
        if has_text and request.attachments:
            return "text_and_single_image"
        if request.attachments:
            return "single_image"
        if has_text:
            return "text"
        raise AgentInputNotSupportedError("任务输入不能为空")

    def _ensure_supported(self, agent_id: str, input_type: str) -> None:
        if input_type not in self.registry.get(agent_id).supports:
            raise AgentInputNotSupportedError(
                "目标 Agent 不支持当前输入类型",
                details={"agent_id": agent_id, "input_type": input_type},
            )

    def _decision_for_rule(
        self, rule: RoutingRule, request: AgentRequest
    ) -> RouteDecision:
        primary = self.registry.get(rule.agent_id)
        selected = primary
        fallback_used = False
        source = "local_fast"

        if (
            not primary.route_when_unconfigured
            and not self.registry.is_runtime_available(primary.agent_id, self.settings)
        ):
            fallback = self.registry.resolve_fallback(primary.agent_id)
            if fallback and (
                fallback.route_when_unconfigured
                or self.registry.is_runtime_available(fallback.agent_id, self.settings)
            ):
                selected = fallback
                fallback_used = True
                source = "local_degraded"
            else:
                return RouteDecision(
                    agent_id="UNRESOLVED",
                    scene=rule.scene,
                    course_id=request.course_id.upper(),
                    intent=request.intent.value,
                    route_status=RouteStatus.UNRESOLVED,
                    reason=f"configured agent unavailable: {primary.agent_id}",
                    retrieval_required=False,
                    provider_required=False,
                    route_source="local_degraded",
                    route_confidence=0.0,
                    original_agent_id=primary.agent_id,
                )

        return RouteDecision(
            agent_id=selected.agent_id,
            scene=rule.scene,
            course_id=request.course_id.upper(),
            intent=request.intent.value,
            route_status=RouteStatus.SELECTED,
            reason=(
                f"fallback from {primary.agent_id} to {selected.agent_id}"
                if fallback_used
                else (
                    "matched configured route "
                    f"course_id={request.course_id.upper()}, "
                    f"intent={request.intent.value}"
                )
            ),
            retrieval_required=rule.retrieval_required,
            provider_required=selected.provider == "xingchen",
            route_source=source,
            route_confidence=0.9 if fallback_used else 0.98,
            fallback_used=fallback_used,
            original_agent_id=primary.agent_id if fallback_used else None,
            fallback_instruction=(
                primary.fallback.instruction_prefix if fallback_used else ""
            ),
        )

    def validate_cloud_target(
        self,
        target_agent_id: str,
        request: AgentRequest,
        *,
        source_agent_id: str = "ROUTER_01_FALLBACK_V1",
    ) -> AgentDefinition:
        if target_agent_id == source_agent_id:
            raise RouteInvalidTargetError("云端调度不得路由回自身")
        try:
            target = self.registry.get(target_agent_id)
        except KeyError as exc:
            raise RouteInvalidTargetError("云端调度返回未注册 Agent") from exc
        if not target.enabled:
            raise RouteInvalidTargetError("云端调度返回未启用 Agent")
        if target.mode == "routing_only":
            raise RouteInvalidTargetError("云端调度目标不得再次进入调度 Agent")
        if request.course_id.upper() not in target.course_ids:
            raise RouteInvalidTargetError("云端调度目标不支持当前课程")
        has_text = any(
            isinstance(value, str) and bool(value.strip())
            for value in request.canonical_input.values()
        )
        if len(request.attachments) > 1:
            raise RouteInvalidTargetError("云端调度目标不支持多附件输入")
        input_type = (
            "text_and_single_image"
            if has_text and request.attachments
            else "single_image"
            if request.attachments
            else "text"
            if has_text
            else "empty"
        )
        if input_type not in target.supports:
            raise RouteInvalidTargetError("云端调度目标不支持当前输入类型")
        if target.provider == "xingchen" and not self.registry.is_runtime_available(
            target.agent_id, self.settings
        ):
            raise RouteInvalidTargetError("云端调度目标当前不可运行")
        return target

    def route_cloud_response(self, answer: str, request: AgentRequest) -> RouteDecision:
        try:
            payload = json.loads(answer)
            target_id = payload["target_agent_id"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RouteInvalidTargetError(
                "云端调度响应必须包含 target_agent_id JSON"
            ) from exc
        if not isinstance(target_id, str):
            raise RouteInvalidTargetError("云端调度 target_agent_id 必须是字符串")
        target = self.validate_cloud_target(target_id, request)
        confidence = payload.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            confidence = 0.5
        return RouteDecision(
            agent_id=target.agent_id,
            scene=target.scene,
            course_id=request.course_id.upper(),
            intent=request.intent.value,
            route_status=RouteStatus.SELECTED,
            reason="validated one-pass cloud dispatch target",
            retrieval_required=target.mode != "routing_only",
            provider_required=target.provider == "xingchen",
            route_source="cloud_fallback",
            route_confidence=max(0.0, min(1.0, float(confidence))),
            fallback_used=True,
            original_agent_id="ROUTER_01_FALLBACK_V1",
        )
