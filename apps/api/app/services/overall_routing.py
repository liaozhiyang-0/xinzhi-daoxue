from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from app.agents.internal import InternalAgentHub
from app.agents.internal.contracts import OverallRouteDecision
from app.agents.router import TaskRouter
from app.contracts import AgentRequest, RouteDecision
from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class OverallRoutingOutcome:
    decision: RouteDecision
    used: bool
    latency_ms: int
    metadata: dict[str, Any]


class OverallRoutingService:
    """Deprecated compatibility wrapper for the former second-pass route.

    The default control path is now Planner/TaskRouter.  This service remains
    callable only when ``overall_routing_enabled`` is explicitly enabled for
    rollback or an older deployment.
    """

    deprecated = True

    agent_id = "OVERALL_ROUTER_LOCAL_V1"

    def __init__(
        self,
        hub: InternalAgentHub,
        task_router: TaskRouter,
        settings: Settings,
    ) -> None:
        self.hub = hub
        self.task_router = task_router
        self.settings = settings

    async def route(
        self, request: AgentRequest, current: RouteDecision
    ) -> OverallRoutingOutcome:
        started = perf_counter()
        if self._skip_for_high_confidence(current):
            return self._fallback(current, started, "high_confidence_local_route")
        if not self._enabled():
            return self._fallback(current, started, "disabled")
        candidates = self.task_router.overall_route_candidates(request, current)
        prompt = self._prompt(request, current, candidates)
        try:
            async with asyncio.timeout(self.settings.overall_routing_timeout_seconds):
                result = await self.hub.run_text(
                    self.agent_id,
                    input_text=prompt,
                    request_id=str(request.options.get("request_id", request.task_id)),
                    max_tokens=self.settings.overall_routing_max_tokens,
                    extra_options={"_allow_route_fallback": False},
                )
            payload = OverallRouteDecision.model_validate(result.structured_result)
            decision = self.task_router.apply_overall_route(
                request,
                current,
                target_agent_id=payload.target_agent_id,
                intent=payload.intent,
                course_id=payload.course_id,
                confidence=payload.confidence,
                reason=payload.reason,
                reason_codes=payload.reason_codes,
                task_subtype=payload.task_subtype,
            )
            if decision is None:
                return self._fallback(current, started, "invalid_target")
            return OverallRoutingOutcome(
                decision=decision,
                used=True,
                latency_ms=self._elapsed_ms(started),
                metadata={
                    "status": "completed",
                    "agent_id": self.agent_id,
                    "model": result.model,
                    "provider": result.provider,
                    "elapsed_ms": result.elapsed_ms,
                    "model_calls": 1,
                    "input_tokens": result.prompt_tokens,
                    "output_tokens": result.completion_tokens,
                },
            )
        except TimeoutError:
            return self._fallback(current, started, "timeout")
        except (ValidationError, ValueError, KeyError, RuntimeError) as exc:
            return self._fallback(current, started, type(exc).__name__)
        except Exception as exc:  # provider-specific errors are a route fallback
            return self._fallback(current, started, type(exc).__name__)

    def _enabled(self) -> bool:
        return bool(
            self.settings.overall_routing_enabled
            and self.settings.app_env != "test"
            and self.hub.list_agents()
            and self.hub_available()
        )

    def _skip_for_high_confidence(self, current: RouteDecision) -> bool:
        """Avoid paying for a second router pass when the local route is decisive."""

        return not self.task_router.overall_refinement_allowed(current)

    def hub_available(self) -> bool:
        return any(
            item["agent_id"] == self.agent_id
            and bool(item["enabled"])
            and bool(item["configured"])
            for item in self.hub.list_agents()
        )

    def _fallback(
        self, current: RouteDecision, started: float, reason: str
    ) -> OverallRoutingOutcome:
        return OverallRoutingOutcome(
            decision=current,
            used=False,
            latency_ms=self._elapsed_ms(started),
            metadata={
                "status": "fallback",
                "agent_id": self.agent_id,
                "fallback_reason": reason,
                "model_calls": 0,
            },
        )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, int((perf_counter() - started) * 1000))

    @staticmethod
    def _prompt(
        request: AgentRequest,
        current: RouteDecision,
        candidates: list[dict[str, Any]],
    ) -> str:
        raw_input = OverallRoutingService._raw_input(request)
        return "\n\n".join(
            [
                "原始用户输入：\n" + raw_input[:8000],
                f"用户显式课程：{request.course_id}\n用户显式意图：{request.intent.value}",
                "当前规则路由（仅作参考）：\n"
                + json.dumps(current.model_dump(mode="json"), ensure_ascii=False),
                "备选路由路径（只能从这些 target_agent_id 中选择一个）：\n"
                + json.dumps(candidates, ensure_ascii=False),
            ]
        )[:18_000]

    @staticmethod
    def _raw_input(request: AgentRequest) -> str:
        values: list[str] = []
        for key in (
            "text",
            "question",
            "query",
            "prompt",
            "problem",
            "writing_task",
            "source_text",
            "data_description",
            "analysis_goal",
        ):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                values.append(f"{key}: {value.strip()}")
        if request.attachments:
            values.append(
                "attachments: "
                + ", ".join(item.filename for item in request.attachments[:5])
            )
        return "\n".join(values) or "(empty input)"
