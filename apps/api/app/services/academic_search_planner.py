from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta

from app.agents.internal.contracts import AcademicSearchPlan
from app.agents.internal.hub import InternalAgentHub
from app.contracts.external_retrieval import ExternalRetrievalResult
from app.core.config import Settings
from app.services.external_research_answer import normalize_academic_search_query


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
        research_intent: dict[str, object] | None = None,
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
        if research_intent:
            payload["research_intent"] = research_intent
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
            fallback = _deterministic_search_plan(query)
            return (
                fallback,
                "academic search planning timed out; using deterministic variants",
            )
        except Exception:
            fallback = _deterministic_search_plan(query)
            return (
                fallback,
                "academic search planning unavailable; using deterministic variants",
            )

        queries = list(
            dict.fromkeys(
                value.strip() for value in plan.search_queries if value.strip()
            )
        )
        if not queries:
            fallback = _deterministic_search_plan(query)
            return (
                fallback,
                "academic search planning returned no queries; "
                "using deterministic variants",
            )
        research_questions = (
            research_intent.get("research_questions")
            if research_intent
            else None
        )
        if isinstance(research_questions, list):
            queries.extend(
                item.strip()
                for item in research_questions
                if isinstance(item, str) and item.strip()
            )
            queries = list(dict.fromkeys(queries))
        queries = _stabilize_queries(query, queries)
        updates: dict[str, object] = {"search_queries": queries[:6]}
        if _has_relative_time_request(query):
            freshness_days = relative_freshness_days(query)
            if research_intent:
                raw_freshness_days = research_intent.get("freshness_days")
                if isinstance(raw_freshness_days, int):
                    freshness_days = raw_freshness_days
            updates["search_queries"] = _repair_relative_time_ranges(
                queries[:6],
                freshness_days=freshness_days,
            )
        requested_minimum = _requested_minimum(query)
        if requested_minimum is not None:
            updates["minimum_results"] = max(
                plan.minimum_results, min(requested_minimum, 20)
            )
        else:
            # A planner model may over-specify a count even when the user did
            # not ask for one. Keep the default retrieval target small so a
            # broad question does not trigger extra provider rounds. Only an
            # explicit "at least N" request may raise it.
            updates["minimum_results"] = 2
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


def _deterministic_search_plan(query: str) -> AcademicSearchPlan:
    """Build a bounded high-recall plan when the planner model is unavailable.

    The retrieval path must not collapse to the user's full natural-language
    sentence: broad frontier questions commonly contain several independent
    concepts (for example, multimodality and agents) that academic indexes
    rank poorly when sent as one unexpanded string.
    """

    normalized = normalize_academic_search_query(query)
    queries = _stabilize_queries(query, [normalized])[:2]
    years = sorted(set(re.findall(r"20\d{2}", query)))
    if len(years) >= 2:
        year_filter = "(" + " OR ".join(years) + ")"
        queries = [f"{item} {year_filter}" for item in queries]
    return AcademicSearchPlan(
        topic_summary=query[:300],
        search_queries=queries[:6],
        minimum_results=max(2, min(20, _requested_minimum(query) or 2)),
        citation_preference=(
            "prefer_high" if _requests_high_citation(query) else "not_requested"
        ),
    )


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


def _stabilize_queries(query: str, queries: list[str]) -> list[str]:
    """Remove planner noise and add bounded variants for broad AI searches."""

    normalized = " ".join(query.casefold().split())
    explicit_sources = any(
        term in normalized for term in ("conference", "workshop", "symposium", "会议")
    )
    cleaned: list[str] = []
    for value in queries:
        candidate = " ".join(value.split())
        if not explicit_sources:
            candidate = re.sub(
                r"\b(?:conference|workshop|symposium)\b", " ", candidate, flags=re.I
            )
        candidate = re.sub(r"\s+", " ", candidate).strip(" ,;()")
        if candidate and candidate.casefold() not in {
            item.casefold() for item in cleaned
        }:
            cleaned.append(candidate)

    ai_topic = any(
        term in normalized
        for term in (
            "人工智能",
            "机器学习",
            "深度学习",
            "生成式人工智能",
            "大模型",
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "generative ai",
            "large language model",
        )
    )
    frontier_request = any(
        term in normalized
        for term in (
            "代表性进展",
            "关键进展",
            "发展趋势",
            "研究现状",
            "frontier",
            "advances",
        )
    )
    if (ai_topic and frontier_request) or _is_broad_ai_frontier_query(normalized):
        deterministic = [
            "generative AI multimodal models vision-language models",
            "AI agents agentic systems large language models tool use",
            "multimodal large language models visual grounding",
            "agentic AI autonomous agents planning reasoning tool use",
        ]
        # Do not append model-produced Boolean syntax here. It is often
        # malformed (for example, an unmatched parenthesis) and causes
        # Crossref/OpenAlex to search a different topic than the user asked.
        cleaned = deterministic
    return list(dict.fromkeys(cleaned)) or [query.strip()]


def _is_broad_ai_frontier_query(normalized: str) -> bool:
    """Recognize broad Chinese/English AI frontier questions deterministically."""

    ai_terms = (
        "\u4eba\u5de5\u667a\u80fd",
        "\u673a\u5668\u5b66\u4e60",
        "\u6df1\u5ea6\u5b66\u4e60",
        "\u751f\u6210\u5f0f\u4eba\u5de5\u667a\u80fd",
        "generative ai",
        "artificial intelligence",
        "large language model",
    )
    multimodal_terms = ("\u591a\u6a21\u6001", "multimodal", "vision-language")
    agent_terms = ("\u667a\u80fd\u4f53", "\u667a\u80fd\u4ee3\u7406", "agent", "agentic")
    frontier_terms = (
        "\u4ee3\u8868\u6027\u8fdb\u5c55",
        "\u5173\u952e\u8fdb\u5c55",
        "\u53d1\u5c55\u8d8b\u52bf",
        "\u7814\u7a76\u73b0\u72b6",
        "frontier",
        "advances",
        "progress",
    )
    return (
        any(term in normalized for term in ai_terms)
        and any(term in normalized for term in multimodal_terms)
        and any(term in normalized for term in agent_terms)
        and any(term in normalized for term in frontier_terms)
    )


_RELATIVE_TIME_TERMS = (
    "近三年",
    "近两年",
    "近一年",
    "近几年",
    "近年",
    "最近",
    "近期",
    "最近几年",
    "last year",
    "last two years",
    "last three years",
    "recent years",
)
_YEAR_RANGE_PATTERN = re.compile(r"20\d{2}\s*(?:\.\.|-|~|至)\s*20\d{2}")


def _has_relative_time_request(query: str) -> bool:
    normalized = query.casefold()
    return any(term in normalized for term in _RELATIVE_TIME_TERMS) and not re.search(
        r"20\d{2}", normalized
    )


def relative_freshness_days(query: str) -> int:
    """Translate a relative year request into a bounded retrieval window."""

    match = re.search(
        r"近\s*(\d+|[一二三四五六七八九十几]+)\s*年", query.casefold()
    )
    if not match:
        return 1095
    value = match.group(1)
    if value.isdigit():
        years = int(value)
    else:
        years = {
            "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
        }.get(value, 3)
    return max(365, min(years, 10) * 365)


def _repair_relative_time_ranges(
    queries: list[str], *, freshness_days: int
) -> list[str]:
    today = datetime.now(UTC).date()
    start_year = (today - timedelta(days=max(1, freshness_days))).year
    year_range = f"{start_year}..{today.year}"
    repaired: list[str] = []
    for query in queries:
        if _YEAR_RANGE_PATTERN.search(query):
            query = _YEAR_RANGE_PATTERN.sub(year_range, query, count=1)
        elif str(today.year) not in query:
            query = f"{query} AND ({year_range})"
        repaired.append(query)
    return repaired
