from __future__ import annotations

import asyncio
import json
import re

from app.agents.internal.contracts import AcademicSearchPlan
from app.agents.internal.hub import InternalAgentHub
from app.contracts.external_retrieval import ExternalRetrievalResult
from app.core.config import Settings


class AcademicSearchPlannerService:
    """Turn a natural-language paper request into bounded search variants."""

    agent_id = "ACADEMIC_SEARCH_PLANNER_LOCAL_V1"

    def __init__(self, hub: InternalAgentHub, settings: Settings) -> None:
        self.hub = hub
        self.settings = settings

    async def plan(
        self,
        query: str,
        *,
        request_id: str = "",
        feedback: dict[str, object] | None = None,
    ) -> tuple[AcademicSearchPlan | None, str | None]:
        if not query.strip():
            return None, "academic search planning skipped: empty query"
        payload: dict[str, object] = {
            "user_query": query[:2000],
            "task": (
                "Refine the academic search plan using the previous-round feedback."
                if feedback
                else "Generate a compact, high-recall academic search plan."
            ),
            "constraints": (
                "If the user asks for high citation count or highly cited papers, "
                "set citation_preference to prefer_high; use required only when "
                "the user makes it mandatory. Preserve the requested minimum count."
            ),
        }
        if feedback:
            payload["feedback"] = feedback
        try:
            async with asyncio.timeout(
                self.settings.external_retrieval_planning_timeout_seconds
            ):
                result = await self.hub.run_text(
                    self.agent_id,
                    input_text=json.dumps(payload, ensure_ascii=False),
                    request_id=request_id or None,
                    max_tokens=self.settings.external_retrieval_planning_max_tokens,
                    extra_options={"_allow_route_fallback": False},
                )
            plan = AcademicSearchPlan.model_validate(result.structured_result)
        except TimeoutError:
            return (
                None,
                "academic search planning timed out; using the original query",
            )
        except Exception:
            return (
                None,
                "academic search planning unavailable; using the original query",
            )

        queries = list(
            dict.fromkeys(
                value.strip() for value in plan.search_queries if value.strip()
            )
        )
        if not queries:
            return (
                None,
                "academic search planning returned no queries; "
                "using the original query",
            )
        updates: dict[str, object] = {"search_queries": queries[:6]}
        requested_minimum = _requested_minimum(query)
        if requested_minimum is not None:
            updates["minimum_results"] = max(
                plan.minimum_results, min(requested_minimum, 20)
            )
        if (
            plan.citation_preference == "not_requested"
            and _requests_high_citation(query)
        ):
            updates["citation_preference"] = "prefer_high"
        return plan.model_copy(update=updates), None

    async def refine(
        self,
        query: str,
        plan: AcademicSearchPlan,
        result: ExternalRetrievalResult,
        *,
        round_number: int,
        request_id: str = "",
    ) -> tuple[AcademicSearchPlan | None, str | None]:
        feedback = {
            "round": round_number,
            "previous_queries": plan.search_queries,
            "topic_summary": plan.topic_summary,
            "minimum_results": plan.minimum_results,
            "citation_preference": plan.citation_preference,
            "approved_titles": [item.title for item in result.items[:8]],
            "citation_counts": [
                item.citation_count for item in result.items[:8]
            ],
            "warnings": result.warnings[:12],
            "provider_status": result.provider_status,
            "instruction": (
                "Generate genuinely different database queries. Address missing "
                "papers, provider failures, abstract gaps, and citation preference."
            ),
        }
        return await self.plan(query, request_id=request_id, feedback=feedback)


def requested_minimum(query: str) -> int | None:
    """Return the explicit paper-count requirement from the user's query."""

    return _requested_minimum(query)


_MINIMUM_PATTERNS = (
    re.compile(r"(?:至少|不少于|最少)\s*(\d+)\s*(?:篇|个|項|项)?"),
    re.compile(r"(?:at\s+least|minimum\s+of)\s*(\d+)\b", re.IGNORECASE),
)


def _requested_minimum(query: str) -> int | None:
    for pattern in _MINIMUM_PATTERNS:
        match = pattern.search(query)
        if match:
            return int(match.group(1))
    return None


def _requests_high_citation(query: str) -> bool:
    normalized = query.casefold()
    return any(
        token in normalized
        for token in (
            "引用率",
            "被引",
            "高引用",
            "引用高",
            "highly cited",
            "most cited",
        )
    )
